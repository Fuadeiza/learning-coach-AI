
import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt
import logging

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

class AuthUtils:
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh",
            "jti": secrets.token_urlsafe(32)
        })
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            return None
    
    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
    
    @staticmethod
    def generate_secure_token() -> str:
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def is_token_expired(token_payload: Dict[str, Any]) -> bool:
        exp = token_payload.get("exp")
        if not exp:
            return True
        
        try:
            exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
            return datetime.now(timezone.utc) > exp_datetime
        except (ValueError, TypeError):
            return True
    
    @staticmethod
    def extract_user_id_from_token(token: str) -> Optional[str]:
        payload = AuthUtils.verify_token(token)
        if payload:
            return payload.get("sub")
        return None

class PasswordValidator:
    
    MIN_LENGTH = 8
    MAX_LENGTH = 128
    
    @staticmethod
    def validate_password(password: str) -> tuple[bool, list[str]]:
        errors = []
        
        if len(password) < PasswordValidator.MIN_LENGTH:
            errors.append(f"Password must be at least {PasswordValidator.MIN_LENGTH} characters long")
        
        if len(password) > PasswordValidator.MAX_LENGTH:
            errors.append(f"Password must be no more than {PasswordValidator.MAX_LENGTH} characters long")
        
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain at least one special character")
        
        weak_patterns = [
            # "password", "123456", "qwerty", "abc123", "admin", "guest",
            # "welcome", "login", "test", "user", "root"
        ]
        
        password_lower = password.lower()
        for pattern in weak_patterns:
            if pattern in password_lower:
                errors.append(f"Password contains common weak pattern: {pattern}")
                break
        
        return len(errors) == 0, errors

def validate_auth_config():
    issues = []
    
    if SECRET_KEY == "your-super-secret-key-change-this-in-production":
        issues.append("JWT_SECRET_KEY is using default value - CHANGE THIS IN PRODUCTION!")
    
    if len(SECRET_KEY) < 32:
        issues.append("JWT_SECRET_KEY should be at least 32 characters long")
    
    if ACCESS_TOKEN_EXPIRE_MINUTES < 5:
        issues.append("ACCESS_TOKEN_EXPIRE_MINUTES is very short - consider increasing")
    
    if ACCESS_TOKEN_EXPIRE_MINUTES > 1440:  # 24 hours
        issues.append("ACCESS_TOKEN_EXPIRE_MINUTES is very long - consider decreasing for security")
    
    if REFRESH_TOKEN_EXPIRE_DAYS < 1:
        issues.append("REFRESH_TOKEN_EXPIRE_DAYS is very short")
    
    if REFRESH_TOKEN_EXPIRE_DAYS > 30:
        issues.append("REFRESH_TOKEN_EXPIRE_DAYS is very long - consider decreasing for security")
    
    return issues

if __name__ == "__main__":
    issues = validate_auth_config()
    if issues:
        print("Authentication configuration issues:")
        for issue in issues:
            print(f"  ⚠️  {issue}")
    else:
        print("✅ Authentication configuration looks good!")