"""
Structured logging configuration using structlog.
"""
import logging
import sys
from pathlib import Path
from typing import Any, Dict

import structlog
from structlog.types import FilteringBoundLogger

from app.core.config import settings


def setup_logging() -> FilteringBoundLogger:
    """
    Configure structured logging for the application.
    
    Returns:
        FilteringBoundLogger: Configured logger instance
    """
    # Ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            # Add timestamp
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            # Add file and line number for development
            structlog.dev.set_exc_info if settings.DEBUG else structlog.processors.format_exc_info,
            # Format for console output
            structlog.dev.ConsoleRenderer(colors=True) if settings.DEBUG 
            else structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Create main application logger
    logger = structlog.get_logger("he_alerts")
    
    return logger


def get_logger(name: str) -> FilteringBoundLogger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        FilteringBoundLogger: Logger instance
    """
    return structlog.get_logger(name)


# Create main application logger
logger = setup_logging()