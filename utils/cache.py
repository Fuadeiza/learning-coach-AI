import asyncio
import json
import logging
import pickle
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, Optional, Union, Callable, List
from uuid import UUID
import hashlib

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class CacheConfig:
    """Cache configuration settings"""
    
    # Cache TTL settings (in seconds)
    USER_CACHE_TTL = 300  # 5 minutes
    QUESTION_CACHE_TTL = 1800  # 30 minutes
    ANALYTICS_CACHE_TTL = 600  # 10 minutes
    ACHIEVEMENTS_CACHE_TTL = 300  # 5 minutes
    PROGRESS_CACHE_TTL = 180  # 3 minutes
    SESSION_CACHE_TTL = 120  # 2 minutes
    LEADERBOARD_CACHE_TTL = 900  # 15 minutes
    
    # Memory cache settings
    MAX_MEMORY_CACHE_SIZE = 1000
    MEMORY_CACHE_TTL = 300  # 5 minutes
    
    # Redis settings
    REDIS_URL = "redis://localhost:6379"
    REDIS_DB = 0
    REDIS_KEY_PREFIX = "learning_coach:"


class InMemoryCache:
    """Simple in-memory LRU cache with TTL"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict] = {}
        self._access_order: List[str] = []
        
    def _is_expired(self, cache_entry: Dict) -> bool:
        """Check if cache entry is expired"""
        return datetime.now() > cache_entry['expires_at']
    
    def _evict_expired(self):
        """Remove expired entries"""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now > entry['expires_at']
        ]
        for key in expired_keys:
            self._cache.pop(key, None)
            if key in self._access_order:
                self._access_order.remove(key)
    
    def _evict_lru(self):
        """Evict least recently used entries if cache is full"""
        while len(self._cache) >= self.max_size and self._access_order:
            lru_key = self._access_order.pop(0)
            self._cache.pop(lru_key, None)
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        self._evict_expired()
        
        if key not in self._cache:
            return None
            
        entry = self._cache[key]
        if self._is_expired(entry):
            self._cache.pop(key)
            if key in self._access_order:
                self._access_order.remove(key)
            return None
        
        # Update access order
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        
        return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache"""
        self._evict_expired()
        self._evict_lru()
        
        expires_at = datetime.now() + timedelta(seconds=ttl or self.default_ttl)
        
        self._cache[key] = {
            'value': value,
            'expires_at': expires_at,
            'created_at': datetime.now()
        }
        
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
    
    def delete(self, key: str) -> None:
        """Delete key from cache"""
        self._cache.pop(key, None)
        if key in self._access_order:
            self._access_order.remove(key)
    
    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()
        self._access_order.clear()
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        self._evict_expired()
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'hit_rate': getattr(self, '_hit_count', 0) / max(getattr(self, '_total_requests', 1), 1)
        }


class RedisCache:
    """Redis-based cache implementation"""
    
    def __init__(self, redis_url: str = CacheConfig.REDIS_URL, db: int = CacheConfig.REDIS_DB):
        self.redis_url = redis_url
        self.db = db
        self._redis: Optional[redis.Redis] = None
        self.connected = False
        
    async def connect(self):
        """Connect to Redis"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, falling back to memory cache")
            return False
            
        try:
            self._redis = redis.from_url(self.redis_url, db=self.db, decode_responses=False)
            await self._redis.ping()
            self.connected = True
            logger.info("Connected to Redis cache")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self._redis:
            await self._redis.aclose()
            self.connected = False
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for Redis storage"""
        try:
            # Try JSON first for simple types (with datetime handling)
            if isinstance(value, (dict, list, str, int, float, bool, type(None))):
                return json.dumps(value, default=self._json_serializer).encode('utf-8')
            else:
                # Use pickle for complex objects
                return pickle.dumps(value)
        except Exception:
            return pickle.dumps(value)
    
    def _json_serializer(self, obj):
        """Custom JSON serializer for datetime and other objects"""
        from datetime import datetime, date
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif hasattr(obj, 'hex'):  # UUID objects
            return str(obj)
        return str(obj)
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from Redis"""
        try:
            # Try JSON first
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fall back to pickle
            return pickle.loads(data)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis"""
        if not self.connected or not self._redis:
            return None
            
        try:
            data = await self._redis.get(f"{CacheConfig.REDIS_KEY_PREFIX}{key}")
            if data is None:
                return None
            return self._deserialize(data)
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in Redis"""
        if not self.connected or not self._redis:
            return False
            
        try:
            data = self._serialize(value)
            redis_key = f"{CacheConfig.REDIS_KEY_PREFIX}{key}"
            
            if ttl:
                await self._redis.setex(redis_key, ttl, data)
            else:
                await self._redis.set(redis_key, data)
            return True
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        if not self.connected or not self._redis:
            return False
            
        try:
            result = await self._redis.delete(f"{CacheConfig.REDIS_KEY_PREFIX}{key}")
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        if not self.connected or not self._redis:
            return 0
            
        try:
            keys = await self._redis.keys(f"{CacheConfig.REDIS_KEY_PREFIX}{pattern}")
            if keys:
                return await self._redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis clear pattern error for {pattern}: {e}")
            return 0


class HybridCache:
    """Hybrid cache using both memory and Redis"""
    
    def __init__(self):
        self.memory_cache = InMemoryCache(
            max_size=CacheConfig.MAX_MEMORY_CACHE_SIZE,
            default_ttl=CacheConfig.MEMORY_CACHE_TTL
        )
        self.redis_cache = RedisCache()
        self._stats = {
            'memory_hits': 0,
            'redis_hits': 0,
            'misses': 0,
            'sets': 0
        }
    
    async def initialize(self):
        """Initialize the cache system"""
        await self.redis_cache.connect()
    
    async def close(self):
        """Close cache connections"""
        await self.redis_cache.disconnect()
    
    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a consistent cache key"""
        key_parts = [prefix]
        
        # Add positional arguments
        for arg in args:
            if isinstance(arg, UUID):
                key_parts.append(str(arg))
            elif isinstance(arg, (dict, list)):
                # Hash complex objects
                arg_str = json.dumps(arg, sort_keys=True, default=str)
                key_parts.append(hashlib.md5(arg_str.encode()).hexdigest()[:8])
            else:
                key_parts.append(str(arg))
        
        # Add keyword arguments
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            kwargs_str = json.dumps(sorted_kwargs, default=str)
            key_parts.append(hashlib.md5(kwargs_str.encode()).hexdigest()[:8])
        
        return ":".join(key_parts)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache (memory first, then Redis)"""
        # Try memory cache first
        value = self.memory_cache.get(key)
        if value is not None:
            self._stats['memory_hits'] += 1
            return value
        
        # Try Redis cache
        value = await self.redis_cache.get(key)
        if value is not None:
            self._stats['redis_hits'] += 1
            # Store in memory cache for faster access
            self.memory_cache.set(key, value, ttl=CacheConfig.MEMORY_CACHE_TTL)
            return value
        
        self._stats['misses'] += 1
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in both memory and Redis cache"""
        self._stats['sets'] += 1
        
        # Set in memory cache
        memory_ttl = min(ttl or CacheConfig.MEMORY_CACHE_TTL, CacheConfig.MEMORY_CACHE_TTL)
        self.memory_cache.set(key, value, ttl=memory_ttl)
        
        # Set in Redis cache
        await self.redis_cache.set(key, value, ttl=ttl)
    
    async def delete(self, key: str) -> None:
        """Delete key from both caches"""
        self.memory_cache.delete(key)
        await self.redis_cache.delete(key)
    
    async def clear_pattern(self, pattern: str) -> None:
        """Clear keys matching pattern from both caches"""
        # Clear from memory cache (simple implementation)
        keys_to_delete = [k for k in self.memory_cache._cache.keys() if pattern in k]
        for key in keys_to_delete:
            self.memory_cache.delete(key)
        
        # Clear from Redis
        await self.redis_cache.clear_pattern(pattern)
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = sum([
            self._stats['memory_hits'],
            self._stats['redis_hits'], 
            self._stats['misses']
        ])
        
        return {
            'memory_cache': self.memory_cache.stats(),
            'redis_connected': self.redis_cache.connected,
            'total_requests': total_requests,
            'memory_hit_rate': self._stats['memory_hits'] / max(total_requests, 1),
            'redis_hit_rate': self._stats['redis_hits'] / max(total_requests, 1),
            'overall_hit_rate': (self._stats['memory_hits'] + self._stats['redis_hits']) / max(total_requests, 1),
            'stats': self._stats
        }


# Global cache instance
cache = HybridCache()


def cached(ttl: Optional[int] = None, key_prefix: str = "default"):
    """Decorator for caching function results with enhanced logging"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Import here to avoid circular imports
            try:
                from utils.logging import log_cache_hit, log_cache_miss, log_cache_set
            except ImportError:
                # Fallback to regular logging if enhanced logging not available
                log_cache_hit = log_cache_miss = log_cache_set = lambda *args, **kwargs: None
            
            # Generate cache key
            cache_key = cache._generate_cache_key(key_prefix, *args, **kwargs)
            endpoint = func.__name__
            
            # Extract user_id if available
            user_id = None
            if 'current_user' in kwargs and kwargs['current_user']:
                user_id = getattr(kwargs['current_user'], 'user_id', None)
            
            # Try to get from cache
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                log_cache_hit(cache_key, endpoint, user_id)
                return cached_result
            
            # Cache miss - log and execute function
            logger.debug(f"Cache miss for {func.__name__}: {cache_key}")
            log_cache_miss(cache_key, endpoint, user_id, "not_found")
            
            result = await func(*args, **kwargs)
            
            # Cache the result
            await cache.set(cache_key, result, ttl=ttl)
            log_cache_set(cache_key, endpoint, ttl or CacheConfig.ANALYTICS_CACHE_TTL, user_id)
            
            return result
        return wrapper
    return decorator


def cache_invalidate(pattern: str):
    """Decorator to invalidate cache patterns after function execution"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            # Invalidate cache after successful execution
            await cache.clear_pattern(pattern)
            logger.debug(f"Invalidated cache pattern: {pattern}")
            return result
        return wrapper
    return decorator


# Cache key generators for common patterns
class CacheKeys:
    """Predefined cache key patterns"""
    
    @staticmethod
    def user(user_id: Union[str, UUID]) -> str:
        return f"user:{user_id}"
    
    @staticmethod
    def user_progress(user_id: Union[str, UUID]) -> str:
        return f"progress:{user_id}"
    
    @staticmethod
    def user_sessions(user_id: Union[str, UUID], limit: int = 50, offset: int = 0) -> str:
        return f"sessions:{user_id}:{limit}:{offset}"
    
    @staticmethod
    def user_analytics(user_id: Union[str, UUID]) -> str:
        return f"analytics:{user_id}"
    
    @staticmethod
    def user_achievements(user_id: Union[str, UUID]) -> str:
        return f"achievements:{user_id}"
    
    @staticmethod
    def question(question_id: Union[str, UUID]) -> str:
        return f"question:{question_id}"
    
    @staticmethod
    def question_stats(question_id: Union[str, UUID]) -> str:
        return f"question_stats:{question_id}"
    
    @staticmethod
    def quiz_results(session_id: Union[str, UUID]) -> str:
        return f"quiz_results:{session_id}"
    
    @staticmethod
    def study_time_stats(user_id: Union[str, UUID]) -> str:
        return f"study_time:{user_id}"
    
    @staticmethod
    def leaderboard(timeframe: str = "all_time", limit: int = 50) -> str:
        return f"leaderboard:{timeframe}:{limit}"


# Cache invalidation patterns
class CacheInvalidationPatterns:
    """Patterns for cache invalidation"""
    
    @staticmethod
    def user_data(user_id: Union[str, UUID]) -> str:
        return f"*:{user_id}*"
    
    @staticmethod
    def user_progress(user_id: Union[str, UUID]) -> str:
        return f"progress:{user_id}*"
    
    @staticmethod
    def user_analytics(user_id: Union[str, UUID]) -> str:
        return f"analytics:{user_id}*"
    
    @staticmethod
    def question_data(question_id: Union[str, UUID]) -> str:
        return f"question*:{question_id}*" 