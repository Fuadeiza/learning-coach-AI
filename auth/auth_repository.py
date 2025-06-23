
import logging
import json
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone
from asyncpg import Pool

from auth.auth_utils import AuthUtils
from models.auth_models import UserInDB, RefreshTokenInDB, OAuthUserInfo
from utils.cache import cached, cache_invalidate, CacheConfig

logger = logging.getLogger(__name__)

class AuthRepository:
    def __init__(self, db_pool: Pool):
        self.pool = db_pool
        self.logger = logging.getLogger(self.__class__.__name__)

    def _ensure_uuid(self, value) -> UUID:
        if isinstance(value, UUID):
            return value
        elif isinstance(value, str):
            return UUID(value)
        else:
            return UUID(str(value))

    async def create_user_with_password(self, email: str, password: str, user_name: Optional[str] = None) -> UUID:
        self.logger.info(f"Creating user with email: {email}")
        try:
            password_hash = AuthUtils.hash_password(password)
            
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    user_id = await connection.fetchval(
                        """INSERT INTO users (email, user_name, password_hash, is_active, is_verified, created_by_oauth) 
                        VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
                        email,
                        user_name,
                        password_hash,
                        True,
                        False,
                        False
                    )
                    user_uuid = self._ensure_uuid(user_id)
                    self.logger.info(f"Successfully created user with ID: {user_uuid}")
                    return user_uuid
        except Exception as e:
            self.logger.error(f"Failed to create user: {e}")
            raise

    async def create_oauth_user(self, oauth_info: OAuthUserInfo) -> UUID:
        self.logger.info(f"Creating OAuth user: {oauth_info.provider}:{oauth_info.oauth_id}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    user_id = await connection.fetchval(
                        """INSERT INTO users (email, user_name, is_active, is_verified, created_by_oauth, oauth_provider, oauth_id) 
                        VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id""",
                        oauth_info.email,
                        oauth_info.user_name,
                        True,
                        True,
                        True,
                        oauth_info.provider,
                        oauth_info.oauth_id
                    )
                    user_uuid = self._ensure_uuid(user_id)
                    self.logger.info(f"Successfully created OAuth user with ID: {user_uuid}")
                    return user_uuid
        except Exception as e:
            self.logger.error(f"Failed to create OAuth user: {e}")
            raise

    @cached(ttl=CacheConfig.USER_CACHE_TTL, key_prefix="auth_user_by_email")
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        self.logger.debug(f"Fetching user by email: {email}")
        try:
            async with self.pool.acquire() as connection:
                user = await connection.fetchrow(
                    """SELECT id, email, user_name, password_hash, is_active, is_verified, 
                    created_at, last_login, created_by_oauth, oauth_provider, oauth_id
                    FROM users WHERE email = $1""",
                    email
                )
                if user:
                    user_dict = dict(user)
                    user_dict['id'] = str(user_dict['id'])
                    self.logger.debug(f"Found user with ID: {user_dict['id']}")
                    return UserInDB(**user_dict)
                else:
                    self.logger.debug(f"No user found with email: {email}")
                    return None
        except Exception as e:
            self.logger.error(f"Failed to fetch user by email {email}: {e}")
            raise

    @cached(ttl=CacheConfig.USER_CACHE_TTL, key_prefix="auth_user_by_id")
    async def get_user_by_id(self, user_id: UUID) -> Optional[UserInDB]:
        self.logger.debug(f"Fetching user by ID: {user_id}")
        try:
            async with self.pool.acquire() as connection:
                user = await connection.fetchrow(
                    """SELECT id, email, user_name, password_hash, is_active, is_verified, 
                    created_at, last_login, created_by_oauth, oauth_provider, oauth_id
                    FROM users WHERE id = $1""",
                    user_id
                )
                if user:
                    user_dict = dict(user)
                    user_dict['id'] = str(user_dict['id'])
                    self.logger.debug(f"Found user: {user_dict['id']}")
                    return UserInDB(**user_dict)
                else:
                    self.logger.debug(f"No user found with ID: {user_id}")
                    return None
        except Exception as e:
            self.logger.error(f"Failed to fetch user by ID {user_id}: {e}")
            raise

    async def get_user_by_oauth(self, provider: str, oauth_id: str) -> Optional[UserInDB]:
        self.logger.debug(f"Fetching OAuth user: {provider}:{oauth_id}")
        try:
            async with self.pool.acquire() as connection:
                user = await connection.fetchrow(
                    """SELECT id, email, user_name, password_hash, is_active, is_verified, 
                    created_at, last_login, created_by_oauth, oauth_provider, oauth_id
                    FROM users WHERE oauth_provider = $1 AND oauth_id = $2""",
                    provider,
                    oauth_id
                )
                if user:
                    user_dict = dict(user)
                    user_dict['id'] = str(user_dict['id'])
                    self.logger.debug(f"Found OAuth user: {user_dict['id']}")
                    return UserInDB(**user_dict)
                else:
                    self.logger.debug(f"No OAuth user found: {provider}:{oauth_id}")
                    return None
        except Exception as e:
            self.logger.error(f"Failed to fetch OAuth user {provider}:{oauth_id}: {e}")
            raise

    async def update_last_login(self, user_id: UUID) -> None:
        self.logger.debug(f"Updating last login for user: {user_id}")
        try:
            async with self.pool.acquire() as connection:
                await connection.execute(
                    "UPDATE users SET last_login = NOW() WHERE id = $1",
                    user_id
                )
                self.logger.debug(f"Updated last login for user: {user_id}")
        except Exception as e:
            self.logger.error(f"Failed to update last login for user {user_id}: {e}")
            raise

    async def update_password(self, user_id: UUID, new_password: str) -> None:
        self.logger.info(f"Updating password for user: {user_id}")
        try:
            password_hash = AuthUtils.hash_password(new_password)
            async with self.pool.acquire() as connection:
                await connection.execute(
                    "UPDATE users SET password_hash = $1 WHERE id = $2",
                    password_hash,
                    user_id
                )
                self.logger.info(f"Successfully updated password for user: {user_id}")
        except Exception as e:
            self.logger.error(f"Failed to update password for user {user_id}: {e}")
            raise

    async def deactivate_user(self, user_id: UUID) -> None: 
        self.logger.info(f"Deactivating user: {user_id}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    await connection.execute(
                        "UPDATE users SET is_active = FALSE WHERE id = $1",
                        user_id
                    )
                    await connection.execute(
                        "UPDATE refresh_tokens SET is_revoked = TRUE WHERE user_id = $1",
                        user_id
                    )
                    self.logger.info(f"Successfully deactivated user: {user_id}")
        except Exception as e:
            self.logger.error(f"Failed to deactivate user {user_id}: {e}")
            raise

    async def verify_email(self, user_id: UUID) -> None:
        self.logger.info(f"Verifying email for user: {user_id}")
        try:
            async with self.pool.acquire() as connection:
                await connection.execute(
                    "UPDATE users SET is_verified = TRUE WHERE id = $1",
                    user_id
                )
                self.logger.info(f"Successfully verified email for user: {user_id}")
        except Exception as e:
            self.logger.error(f"Failed to verify email for user {user_id}: {e}")
            raise

    async def store_refresh_token(self, user_id: UUID, token: str, expires_at: datetime) -> UUID:
        self.logger.debug(f"Storing refresh token for user: {user_id}")
        try:
            token_hash = AuthUtils.hash_token(token)
            async with self.pool.acquire() as connection:
                token_id = await connection.fetchval(
                    """INSERT INTO refresh_tokens (user_id, token_hash, expires_at) 
                    VALUES ($1, $2, $3) RETURNING id""",
                    user_id,
                    token_hash,
                    expires_at
                )
                token_uuid = self._ensure_uuid(token_id)
                self.logger.debug(f"Stored refresh token with ID: {token_uuid}")
                return token_uuid
        except Exception as e:
            self.logger.error(f"Failed to store refresh token: {e}")
            raise

    async def get_refresh_token(self, token: str) -> Optional[RefreshTokenInDB]:
        try:
            token_hash = AuthUtils.hash_token(token)
            async with self.pool.acquire() as connection:
                token_data = await connection.fetchrow(
                    """SELECT id, user_id, token_hash, expires_at, is_revoked, created_at, last_used_at 
                    FROM refresh_tokens WHERE token_hash = $1""",
                    token_hash
                )
                if token_data:
                    token_dict = dict(token_data)
                    token_dict['id'] = str(token_dict['id'])
                    token_dict['user_id'] = str(token_dict['user_id'])
                    return RefreshTokenInDB(**token_dict)
                return None
        except Exception as e:
            self.logger.error(f"Failed to get refresh token: {e}")
            raise

    async def update_refresh_token_usage(self, token: str) -> None:
        try:
            token_hash = AuthUtils.hash_token(token)
            async with self.pool.acquire() as connection:
                await connection.execute(
                    "UPDATE refresh_tokens SET last_used_at = NOW() WHERE token_hash = $1",
                    token_hash
                )
        except Exception as e:
            self.logger.error(f"Failed to update refresh token usage: {e}")
            raise

    async def revoke_refresh_token(self, token: str) -> None:
        try:
            token_hash = AuthUtils.hash_token(token)
            async with self.pool.acquire() as connection:
                await connection.execute(
                    "UPDATE refresh_tokens SET is_revoked = TRUE WHERE token_hash = $1",
                    token_hash
                )
                self.logger.info("Revoked refresh token")
        except Exception as e:
            self.logger.error(f"Failed to revoke refresh token: {e}")
            raise

    async def revoke_all_user_tokens(self, user_id: UUID) -> None:
        try:
            async with self.pool.acquire() as connection:
                result = await connection.execute(
                    "UPDATE refresh_tokens SET is_revoked = TRUE WHERE user_id = $1 AND is_revoked = FALSE",
                    user_id
                )
                self.logger.info(f"Revoked all tokens for user {user_id}")
        except Exception as e:
            self.logger.error(f"Failed to revoke all tokens for user {user_id}: {e}")
            raise

    async def cleanup_expired_tokens(self) -> int:
        try:
            async with self.pool.acquire() as connection:
                result = await connection.execute(
                    "DELETE FROM refresh_tokens WHERE expires_at < NOW()"
                )
                count = int(result.split()[-1]) if result.split()[-1].isdigit() else 0
                self.logger.info(f"Cleaned up {count} expired refresh tokens")
                return count
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired tokens: {e}")
            raise

    async def get_user_active_sessions_count(self, user_id: UUID) -> int:
        try:
            async with self.pool.acquire() as connection:
                count = await connection.fetchval(
                    """SELECT COUNT(*) FROM refresh_tokens 
                    WHERE user_id = $1 AND is_revoked = FALSE AND expires_at > NOW()""",
                    user_id
                )
                return count or 0
        except Exception as e:
            self.logger.error(f"Failed to get active sessions count for user {user_id}: {e}")
            raise