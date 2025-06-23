
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime

class UserRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")
    user_name: Optional[str] = Field(None, max_length=100, description="Display name")
    
    @validator('password')
    def validate_password_strength(cls, v):
        from auth.auth_utils import PasswordValidator
        is_valid, errors = PasswordValidator.validate_password(v)
        if not is_valid:
            raise ValueError(f"Password validation failed: {', '.join(errors)}")
        return v

class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")

class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Valid refresh token")

class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    
    @validator('new_password')
    def validate_password_strength(cls, v):
        from auth.auth_utils import PasswordValidator
        is_valid, errors = PasswordValidator.validate_password(v)
        if not is_valid:
            raise ValueError(f"Password validation failed: {', '.join(errors)}")
        return v

class PasswordResetRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address for password reset")

class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    
    @validator('new_password')
    def validate_password_strength(cls, v):
        from auth.auth_utils import PasswordValidator
        is_valid, errors = PasswordValidator.validate_password(v)
        if not is_valid:
            raise ValueError(f"Password validation failed: {', '.join(errors)}")
        return v

class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")

class AccessTokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")

class UserProfileResponse(BaseModel):
    id: str = Field(..., description="User ID")
    email: Optional[str] = Field(None, description="User email")
    user_name: Optional[str] = Field(None, description="Display name")
    is_active: bool = Field(..., description="Whether user is active")
    is_verified: bool = Field(..., description="Whether email is verified")
    created_at: datetime = Field(..., description="Account creation date")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    created_by_oauth: bool = Field(default=False, description="Created via OAuth")
    oauth_provider: Optional[str] = Field(None, description="OAuth provider")

class UserRegistrationResponse(BaseModel):
    user_id: str = Field(..., description="Created user ID")
    email: str = Field(..., description="User email")
    user_name: Optional[str] = Field(None, description="Display name")
    message: str = Field(..., description="Registration status message")

class OAuthUserInfo(BaseModel):
    oauth_id: str = Field(..., description="OAuth provider user ID")
    email: Optional[str] = Field(None, description="Email from OAuth provider")
    user_name: Optional[str] = Field(None, description="Name from OAuth provider")
    provider: str = Field(..., description="OAuth provider name (google, github, etc.)")
    avatar_url: Optional[str] = Field(None, description="Profile picture URL")

class UserInDB(BaseModel):
    id: str
    email: Optional[str]
    user_name: Optional[str]
    password_hash: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]
    created_by_oauth: bool
    oauth_provider: Optional[str]
    oauth_id: Optional[str]

class RefreshTokenInDB(BaseModel):
    id: str
    user_id: str
    token_hash: str
    expires_at: datetime
    is_revoked: bool
    created_at: datetime
    last_used_at: Optional[datetime]

class AuthErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Specific error code")

class UserSession(BaseModel):
    user_id: str
    email: Optional[str]
    user_name: Optional[str]
    is_active: bool
    permissions: list[str] = Field(default_factory=list)
    
    class Config:
        from_attributes = True

class TokenClaims(BaseModel):
    sub: str
    email: Optional[str] = None
    user_name: Optional[str] = None
    type: str
    iat: int
    exp: int
    jti: Optional[str] = None

class APIKeyRequest(BaseModel):
    name: str = Field(..., max_length=100, description="API key name/description")
    expires_days: Optional[int] = Field(None, ge=1, le=365, description="Expiration in days")

class APIKeyResponse(BaseModel):
    key_id: str = Field(..., description="API key ID")
    name: str = Field(..., description="API key name")
    key: str = Field(..., description="The actual API key (only shown once)")
    expires_at: Optional[datetime] = Field(None, description="Expiration date")
    created_at: datetime = Field(..., description="Creation date")

class APIKeyInfo(BaseModel):
    key_id: str = Field(..., description="API key ID")
    name: str = Field(..., description="API key name")
    expires_at: Optional[datetime] = Field(None, description="Expiration date")
    created_at: datetime = Field(..., description="Creation date")
    last_used: Optional[datetime] = Field(None, description="Last used timestamp")
    is_active: bool = Field(..., description="Whether key is active")