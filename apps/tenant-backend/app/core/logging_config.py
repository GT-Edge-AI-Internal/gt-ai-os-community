"""
GT 2.0 Tenant Backend Logging Configuration

Structured logging with tenant isolation and security considerations.
"""

import logging
import logging.config
import sys
from typing import Dict, Any

from app.core.config import get_settings


def setup_logging() -> None:
    """Setup logging configuration for the tenant backend"""
    settings = get_settings()
    
    # Determine log directory based on environment
    if settings.environment == "test":
        log_dir = f"/tmp/gt2-data/{settings.tenant_domain}/logs"
    else:
        log_dir = f"/data/{settings.tenant_domain}/logs"
    
    # Create logging configuration
    log_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(funcName)s() - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.log_level,
                "formatter": "json" if settings.log_format == "json" else "default",
                "stream": sys.stdout,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json" if settings.log_format == "json" else "detailed",
                "filename": f"{log_dir}/tenant-backend.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "": {  # Root logger
                "level": settings.log_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "app": {
                "level": settings.log_level,
                "handlers": ["console", "file"] if settings.environment == "production" else ["console"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "INFO" if settings.debug else "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "WARNING",  # Suppress INFO level access logs (operational endpoints)
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }
    
    # Create log directory if it doesn't exist
    import os
    os.makedirs(log_dir, exist_ok=True, mode=0o700)
    
    # Apply logging configuration
    logging.config.dictConfig(log_config)
    
    # Add tenant context to all logs
    class TenantContextFilter(logging.Filter):
        def filter(self, record):
            record.tenant_id = settings.tenant_id
            record.tenant_domain = settings.tenant_domain
            return True
    
    tenant_filter = TenantContextFilter()
    
    # Add tenant filter to all handlers
    for handler in logging.getLogger().handlers:
        handler.addFilter(tenant_filter)
    
    # Log startup information
    logger = logging.getLogger("app.startup")
    logger.info(
        "Tenant backend logging initialized",
        extra={
            "tenant_id": settings.tenant_id,
            "tenant_domain": settings.tenant_domain,
            "environment": settings.environment,
            "log_level": settings.log_level,
            "log_format": settings.log_format,
        }
    )


def get_logger(name: str) -> logging.Logger:
    """Get logger with consistent naming and formatting"""
    return logging.getLogger(f"app.{name}")



class SecurityRedactionFilter(logging.Filter):
    """Filter to redact sensitive information from logs"""
    
    SENSITIVE_FIELDS = [
        "password", "token", "secret", "key", "authorization", 
        "cookie", "session", "csrf", "api_key", "jwt"
    ]
    
    def filter(self, record):
        if hasattr(record, 'args') and record.args:
            # Redact sensitive information from log messages
            record.args = self._redact_sensitive_data(record.args)
        
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            for field in self.SENSITIVE_FIELDS:
                if field.lower() in record.msg.lower():
                    record.msg = record.msg.replace(field, "[REDACTED]")
        
        return True
    
    def _redact_sensitive_data(self, data):
        """Recursively redact sensitive data from log arguments"""
        if isinstance(data, dict):
            return {
                key: "[REDACTED]" if any(sensitive in key.lower() for sensitive in self.SENSITIVE_FIELDS)
                else self._redact_sensitive_data(value)
                for key, value in data.items()
            }
        elif isinstance(data, (list, tuple)):
            return type(data)(self._redact_sensitive_data(item) for item in data)
        return data


def setup_security_logging():
    """Setup security-focused logging with redaction"""
    security_filter = SecurityRedactionFilter()
    
    # Add security filter to all loggers
    for name in ["app", "uvicorn", "sqlalchemy"]:
        logger = logging.getLogger(name)
        logger.addFilter(security_filter)