
import logging
from typing import Optional, Annotated
from uuid import UUID
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from auth.auth_utils import AuthUtils
from auth.auth_repository import AuthRepository
from models.auth_models import UserSession, UserInDB

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

class AuthorizationError(HTTPException):
    def __init__(self, detail: str = "Access denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )

def get_auth_repository(request: Request) -> AuthRepository:
    return request.app.state.auth_repo

async def get_token_payload(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)]
) -> Optional[dict]:
    if not credentials:
        return None
    
    token = credentials.credentials
    payload = AuthUtils.verify_token(token)
    
    if not payload:
        raise AuthenticationError("Invalid or expired token")
    
    if AuthUtils.is_token_expired(payload):
        raise AuthenticationError("Token has expired")
    
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")
    
    return payload

async def get_current_user(
    payload: Annotated[Optional[dict], Depends(get_token_payload)],
    auth_repo: Annotated[AuthRepository, Depends(get_auth_repository)]
) -> UserSession:
    if not payload:
        raise AuthenticationError("Authentication required")
    
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token: missing user ID")
    
    try:
        user = await auth_repo.get_user_by_id(UUID(user_id))
        if not user:
            raise AuthenticationError("User not found")
        
        if not user.is_active:
            raise AuthenticationError("User account is deactivated")
        
        return UserSession(
            user_id=user.id,
            email=user.email,
            user_name=user.user_name,
            is_active=user.is_active,
            permissions=[]
        )
    
    except ValueError:
        raise AuthenticationError("Invalid user ID format")
    except Exception as e:
        logger.error(f"Failed to get current user: {e}")
        raise AuthenticationError("Authentication failed")

async def get_current_active_user(
    current_user: Annotated[UserSession, Depends(get_current_user)]
) -> UserSession:
    if not current_user.is_active:
        raise AuthenticationError("User account is inactive")
    return current_user

async def get_current_verified_user(
    current_user: Annotated[UserSession, Depends(get_current_user)],
    auth_repo: Annotated[AuthRepository, Depends(get_auth_repository)]
) -> UserSession:
    if not current_user.is_active:
        raise AuthenticationError("User account is inactive")

    try:
        user = await auth_repo.get_user_by_id(UUID(current_user.user_id))
        if not user or not user.is_verified:
            raise AuthenticationError("Email verification required")
        return current_user
    except Exception as e:
        logger.error(f"Failed to check user verification: {e}")
        raise AuthenticationError("Verification check failed")

async def get_optional_current_user(
    payload: Annotated[Optional[dict], Depends(get_token_payload)],
    auth_repo: Annotated[AuthRepository, Depends(get_auth_repository)]
) -> Optional[UserSession]:
    if not payload:
        return None
    
    try:
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        user = await auth_repo.get_user_by_id(UUID(user_id))
        if not user or not user.is_active:
            return None
        
        return UserSession(
            user_id=user.id,
            email=user.email,
            user_name=user.user_name,
            is_active=user.is_active,
            permissions=[]
        )
    
    except Exception as e:
        logger.warning(f"Optional auth failed: {e}")
        return None

def require_permissions(*required_permissions: str):
    def permission_checker(
        current_user: Annotated[UserSession, Depends(get_current_active_user)]
    ) -> UserSession:
        if not all(perm in current_user.permissions for perm in required_permissions):
            missing_perms = [p for p in required_permissions if p not in current_user.permissions]
            raise AuthorizationError(f"Missing required permissions: {', '.join(missing_perms)}")
        return current_user
    return permission_checker

def require_admin():
    return require_permissions("admin")

def require_moderator():
    def moderator_checker(
        current_user: Annotated[UserSession, Depends(get_current_active_user)]
    ) -> UserSession:
        if not any(perm in current_user.permissions for perm in ["admin", "moderator"]):
            raise AuthorizationError("Moderator access required")
        return current_user
    return moderator_checker

class RateLimiter:
    
    def __init__(self, max_attempts: int = 5, window_minutes: int = 15):
        self.max_attempts = max_attempts
        self.window_minutes = window_minutes
        self.attempts = {}
    
    def check_rate_limit(self, identifier: str) -> bool:
        import time
        now = time.time()
        window_start = now - (self.window_minutes * 60)
        
        if identifier in self.attempts:
            self.attempts[identifier] = [
                attempt for attempt in self.attempts[identifier] 
                if attempt > window_start
            ]
        
        current_attempts = len(self.attempts.get(identifier, []))
        return current_attempts < self.max_attempts
    
    def record_attempt(self, identifier: str) -> None:
        import time
        if identifier not in self.attempts:
            self.attempts[identifier] = []
        self.attempts[identifier].append(time.time())

login_rate_limiter = RateLimiter(max_attempts=5, window_minutes=15)
registration_rate_limiter = RateLimiter(max_attempts=3, window_minutes=60)

def check_login_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    if not login_rate_limiter.check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )

def record_failed_login(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    login_rate_limiter.record_attempt(client_ip)

def check_registration_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    if not registration_rate_limiter.check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later."
        )

CurrentUser = Annotated[UserSession, Depends(get_current_user)]
CurrentActiveUser = Annotated[UserSession, Depends(get_current_active_user)]
CurrentVerifiedUser = Annotated[UserSession, Depends(get_current_verified_user)]
OptionalCurrentUser = Annotated[Optional[UserSession], Depends(get_optional_current_user)]