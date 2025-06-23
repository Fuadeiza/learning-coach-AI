
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError

from auth.auth_repository import AuthRepository
from auth.auth_utils import AuthUtils, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
from auth.auth_dependencies import (
    get_auth_repository, CurrentUser, CurrentActiveUser,
    check_login_rate_limit, check_registration_rate_limit, record_failed_login,
    AuthenticationError
)
from models.auth_models import (
    UserRegisterRequest, UserLoginRequest, RefreshTokenRequest,
    TokenResponse, AccessTokenResponse, UserProfileResponse, UserRegistrationResponse,
    PasswordChangeRequest, AuthErrorResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserRegistrationResponse)
async def register_user(
    request: Request,
    user_data: UserRegisterRequest,
    auth_repo: Annotated[AuthRepository, Depends(get_auth_repository)]
):
    
    check_registration_rate_limit(request)
    
    try:
        existing_user = await auth_repo.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already registered"
            )
        
        user_id = await auth_repo.create_user_with_password(
            email=user_data.email,
            password=user_data.password,
            user_name=user_data.user_name
        )
        
        logger.info(f"Successfully registered new user: {user_id}")
        
        return UserRegistrationResponse(
            user_id=str(user_id),
            email=user_data.email,
            user_name=user_data.user_name,
            message="User registered successfully. Please verify your email address."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed for {user_data.email}: {e}")
        if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already registered"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/login", response_model=TokenResponse)
async def login_user(
    request: Request,
    login_data: UserLoginRequest,
    auth_repo: Annotated[AuthRepository, Depends(get_auth_repository)]
):
    
    check_login_rate_limit(request)
    
    try:
        user = await auth_repo.get_user_by_email(login_data.email)
        
        if not user or not user.password_hash:
            record_failed_login(request)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        if not AuthUtils.verify_password(login_data.password, user.password_hash):
            record_failed_login(request)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is deactivated"
            )
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        token_data = {
            "sub": user.id,
            "email": user.email,
            "user_name": user.user_name
        }
        
        access_token = AuthUtils.create_access_token(
            data=token_data, 
            expires_delta=access_token_expires
        )
        refresh_token = AuthUtils.create_refresh_token(
            data=token_data,
            expires_delta=refresh_token_expires
        )
        
        refresh_expires_at = datetime.now(timezone.utc) + refresh_token_expires
        await auth_repo.store_refresh_token(
            user_id=UUID(user.id),
            token=refresh_token,
            expires_at=refresh_expires_at
        )
        
        await auth_repo.update_last_login(UUID(user.id))
        
        logger.info(f"User {user.id} logged in successfully")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed for {login_data.email}: {e}")
        record_failed_login(request)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_access_token(
    refresh_data: RefreshTokenRequest,
    auth_repo: Annotated[AuthRepository, Depends(get_auth_repository)]
):
    
    try:
        payload = AuthUtils.verify_token(refresh_data.refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        token_record = await auth_repo.get_refresh_token(refresh_data.refresh_token)
        if not token_record or token_record.is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is invalid or revoked"
            )
        
        if token_record.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired"
            )
        
        user = await auth_repo.get_user_by_id(UUID(token_record.user_id))
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User is not active"
            )
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        token_data = {
            "sub": user.id,
            "email": user.email,
            "user_name": user.user_name
        }
        
        access_token = AuthUtils.create_access_token(
            data=token_data,
            expires_delta=access_token_expires
        )
        
        await auth_repo.update_refresh_token_usage(refresh_data.refresh_token)
        
        logger.info(f"Access token refreshed for user {user.id}")
        
        return AccessTokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )

@router.post("/logout")
async def logout_user(
    refresh_data: RefreshTokenRequest,
    current_user: CurrentUser,
    auth_repo: Annotated[AuthRepository, Depends(get_auth_repository)]
):
    
    try:
        await auth_repo.revoke_refresh_token(refresh_data.refresh_token)
        
        logger.info(f"User {current_user.user_id} logged out")
        
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        logger.error(f"Logout failed for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )

@router.post("/logout-all")
async def logout_all_sessions(
    current_user: CurrentActiveUser,
    auth_repo: Annotated[AuthRepository, Depends(get_auth_repository)]
):
    
    try:
        await auth_repo.revoke_all_user_tokens(UUID(current_user.user_id))
        
        logger.info(f"User {current_user.user_id} logged out from all sessions")
        
        return {"message": "Successfully logged out from all sessions"}
        
    except Exception as e:
        logger.error(f"Logout all failed for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout from all sessions failed"
        )

@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    current_user: CurrentUser,
    auth_repo: Annotated[AuthRepository, Depends(get_auth_repository)]
):
    
    try:
        user = await auth_repo.get_user_by_id(UUID(current_user.user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserProfileResponse(
            id=user.id,
            email=user.email,
            user_name=user.user_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login=user.last_login,
            created_by_oauth=user.created_by_oauth,
            oauth_provider=user.oauth_provider
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve profile"
        )

@router.post("/change-password")
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: CurrentActiveUser,
    auth_repo: Annotated[AuthRepository, Depends(get_auth_repository)]
):
    
    try:
        user = await auth_repo.get_user_by_id(UUID(current_user.user_id))
        if not user or not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password change not available for this account"
            )
        
        if not AuthUtils.verify_password(password_data.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        await auth_repo.update_password(UUID(user.id), password_data.new_password)
        
        await auth_repo.revoke_all_user_tokens(UUID(user.id))
        
        logger.info(f"Password changed for user {user.id}")
        
        return {"message": "Password changed successfully. Please log in again."}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change failed for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )

@router.get("/sessions")
async def get_active_sessions(
    current_user: CurrentActiveUser,
    auth_repo: Annotated[AuthRepository, Depends(get_auth_repository)]
):
    
    try:
        session_count = await auth_repo.get_user_active_sessions_count(UUID(current_user.user_id))
        
        return {
            "user_id": current_user.user_id,
            "active_sessions": session_count
        }
        
    except Exception as e:
        logger.error(f"Failed to get session count for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session information"
        )

@router.post("/verify-token")
async def verify_token_endpoint(
    current_user: CurrentUser
):
    return {
        "valid": True,
        "user_id": current_user.user_id,
        "email": current_user.email,
        "user_name": current_user.user_name
    }

@router.post("/admin/cleanup-tokens")
async def cleanup_expired_tokens(
    current_user: CurrentActiveUser,
    auth_repo: Annotated[AuthRepository, Depends(get_auth_repository)]
):
    
    # TODO: Add admin permission check
    # if "admin" not in current_user.permissions:
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        deleted_count = await auth_repo.cleanup_expired_tokens()
        
        logger.info(f"Cleaned up {deleted_count} expired tokens")
        
        return {
            "message": f"Successfully cleaned up {deleted_count} expired tokens"
        }
        
    except Exception as e:
        logger.error(f"Token cleanup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token cleanup failed"
        )