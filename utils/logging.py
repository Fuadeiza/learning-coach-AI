import logging
import logging.handlers
import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import Request


class CacheLogger:
    """Enhanced logger with cache hit/miss tracking and request logging"""
    
    def __init__(self, 
                 log_file: str = "logs/app.log",
                 max_file_size: int = 10 * 1024 * 1024,  # 10MB
                 backup_count: int = 5,
                 log_level: str = "INFO"):
        
        self.log_file = log_file
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        
        # Create logs directory if it doesn't exist
        log_dir = Path(log_file).parent
        log_dir.mkdir(exist_ok=True)
        
        # Setup main logger
        self.logger = logging.getLogger("learning_coach")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Setup rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # Setup console handler
        console_handler = logging.StreamHandler()
        
        # Create detailed formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-15s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Cache statistics
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "total_requests": 0,
            "start_time": time.time()
        }
        
        self.logger.info("🚀 Enhanced logging system initialized")
        self.logger.info(f"📁 Log file: {log_file}")
        self.logger.info(f"💾 Max file size: {max_file_size // (1024*1024)}MB")
        self.logger.info(f"🔄 Backup count: {backup_count}")

    def log_request_start(self, request: Request, endpoint: str, user_id: Optional[str] = None):
        """Log the start of a request with details"""
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        request_info = {
            "endpoint": endpoint,
            "method": request.method,
            "client_ip": client_ip,
            "user_id": user_id or "anonymous",
            "user_agent": user_agent[:100],  # Truncate long user agents
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(f"🔵 REQUEST START | {endpoint} | User: {user_id or 'anonymous'} | IP: {client_ip}")
        return request_info

    def log_request_end(self, request_info: Dict[str, Any], duration_ms: float, status_code: int = 200):
        """Log the end of a request with performance metrics"""
        endpoint = request_info["endpoint"]
        user_id = request_info["user_id"]
        
        self.cache_stats["total_requests"] += 1
        
        status_emoji = "✅" if status_code < 400 else "❌"
        
        self.logger.info(
            f"{status_emoji} REQUEST END | {endpoint} | User: {user_id} | "
            f"Duration: {duration_ms:.2f}ms | Status: {status_code}"
        )

    def log_cache_hit(self, key: str, endpoint: str, user_id: Optional[str] = None):
        """Log cache hit with details"""
        self.cache_stats["hits"] += 1
        hit_rate = (self.cache_stats["hits"] / max(self.cache_stats["total_requests"], 1)) * 100
        
        self.logger.info(
            f"🟢 CACHE HIT | {endpoint} | Key: {key[:50]}... | User: {user_id or 'anonymous'} | "
            f"Hit Rate: {hit_rate:.1f}%"
        )

    def log_cache_miss(self, key: str, endpoint: str, user_id: Optional[str] = None, reason: str = "not_found"):
        """Log cache miss with details"""
        self.cache_stats["misses"] += 1
        hit_rate = (self.cache_stats["hits"] / max(self.cache_stats["total_requests"], 1)) * 100
        
        self.logger.info(
            f"🔴 CACHE MISS | {endpoint} | Key: {key[:50]}... | User: {user_id or 'anonymous'} | "
            f"Reason: {reason} | Hit Rate: {hit_rate:.1f}%"
        )

    def log_cache_set(self, key: str, endpoint: str, ttl: int, user_id: Optional[str] = None):
        """Log cache set operation"""
        self.logger.debug(
            f"💾 CACHE SET | {endpoint} | Key: {key[:50]}... | TTL: {ttl}s | User: {user_id or 'anonymous'}"
        )

    def log_cache_clear(self, pattern: str, count: int, user_id: Optional[str] = None):
        """Log cache clear operation"""
        self.logger.info(
            f"🧹 CACHE CLEAR | Pattern: {pattern} | Cleared: {count} keys | User: {user_id or 'admin'}"
        )

    def log_database_query(self, query_type: str, table: str, duration_ms: float, user_id: Optional[str] = None):
        """Log database operations"""
        self.logger.debug(
            f"🗄️ DATABASE | {query_type} | Table: {table} | Duration: {duration_ms:.2f}ms | "
            f"User: {user_id or 'system'}"
        )

    def log_ai_request(self, agent_type: str, topic: str, duration_ms: float, user_id: Optional[str] = None):
        """Log AI agent requests"""
        self.logger.info(
            f"🤖 AI REQUEST | {agent_type} | Topic: {topic} | Duration: {duration_ms:.2f}ms | "
            f"User: {user_id or 'anonymous'}"
        )

    def log_error(self, error: Exception, endpoint: str, user_id: Optional[str] = None, extra_context: Dict = None):
        """Log errors with context"""
        context = f" | Context: {json.dumps(extra_context)}" if extra_context else ""
        
        self.logger.error(
            f"💥 ERROR | {endpoint} | {type(error).__name__}: {str(error)} | "
            f"User: {user_id or 'anonymous'}{context}",
            exc_info=True
        )

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get current cache statistics"""
        uptime_hours = (time.time() - self.cache_stats["start_time"]) / 3600
        total_requests = max(self.cache_stats["total_requests"], 1)
        
        return {
            "cache_hits": self.cache_stats["hits"],
            "cache_misses": self.cache_stats["misses"],
            "total_requests": self.cache_stats["total_requests"],
            "hit_rate_percent": round((self.cache_stats["hits"] / total_requests) * 100, 2),
            "requests_per_hour": round(self.cache_stats["total_requests"] / max(uptime_hours, 0.01), 2),
            "uptime_hours": round(uptime_hours, 2),
            "log_file": self.log_file,
            "log_file_size_mb": round(os.path.getsize(self.log_file) / (1024*1024), 2) if os.path.exists(self.log_file) else 0
        }

    def log_periodic_stats(self):
        """Log periodic cache and system statistics"""
        stats = self.get_cache_stats()
        
        self.logger.info(
            f"📊 PERIODIC STATS | Requests: {stats['total_requests']} | "
            f"Cache Hit Rate: {stats['hit_rate_percent']}% | "
            f"Req/Hour: {stats['requests_per_hour']} | "
            f"Uptime: {stats['uptime_hours']}h | "
            f"Log Size: {stats['log_file_size_mb']}MB"
        )

    def cleanup_old_logs(self):
        """Manual cleanup of old log files if needed"""
        log_dir = Path(self.log_file).parent
        log_files = list(log_dir.glob(f"{Path(self.log_file).stem}*"))
        
        if len(log_files) > self.backup_count + 1:  # +1 for current log file
            # Sort by modification time and keep only the newest files
            log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            files_to_remove = log_files[self.backup_count + 1:]
            
            for file_path in files_to_remove:
                try:
                    file_path.unlink()
                    self.logger.info(f"🗑️ Cleaned up old log file: {file_path}")
                except Exception as e:
                    self.logger.error(f"Failed to remove old log file {file_path}: {e}")


# Global logger instance
cache_logger = CacheLogger()


# Convenience functions for easy usage
def log_request_start(request: Request, endpoint: str, user_id: Optional[str] = None):
    return cache_logger.log_request_start(request, endpoint, user_id)

def log_request_end(request_info: Dict[str, Any], duration_ms: float, status_code: int = 200):
    cache_logger.log_request_end(request_info, duration_ms, status_code)

def log_cache_hit(key: str, endpoint: str, user_id: Optional[str] = None):
    cache_logger.log_cache_hit(key, endpoint, user_id)

def log_cache_miss(key: str, endpoint: str, user_id: Optional[str] = None, reason: str = "not_found"):
    cache_logger.log_cache_miss(key, endpoint, user_id, reason)

def log_cache_set(key: str, endpoint: str, ttl: int, user_id: Optional[str] = None):
    cache_logger.log_cache_set(key, endpoint, ttl, user_id)

def log_cache_clear(pattern: str, count: int, user_id: Optional[str] = None):
    cache_logger.log_cache_clear(pattern, count, user_id)

def log_database_query(query_type: str, table: str, duration_ms: float, user_id: Optional[str] = None):
    cache_logger.log_database_query(query_type, table, duration_ms, user_id)

def log_ai_request(agent_type: str, topic: str, duration_ms: float, user_id: Optional[str] = None):
    cache_logger.log_ai_request(agent_type, topic, duration_ms, user_id)

def log_error(error: Exception, endpoint: str, user_id: Optional[str] = None, extra_context: Dict = None):
    cache_logger.log_error(error, endpoint, user_id, extra_context)

def get_cache_stats():
    return cache_logger.get_cache_stats()

def log_periodic_stats():
    cache_logger.log_periodic_stats()
