"""
Health check endpoints.
"""
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_database
from app.core.config import settings
from app.core.logging import get_logger
from app.services.email_processor import EmailProcessor

logger = get_logger(__name__)
router = APIRouter()


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "service": settings.APP_NAME
    }


@router.get("/detailed")
async def detailed_health_check(
    db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Detailed health check with database and service status."""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "service": settings.APP_NAME,
        "components": {}
    }
    
    # Check database connection
    try:
        await db.execute("SELECT 1")
        health_status["components"]["database"] = {
            "status": "healthy",
            "url": settings.DATABASE_URL.replace(settings.DATABASE_URL.split('@')[0].split('//')[1], '***'),
            "pool_size": settings.DATABASE_POOL_SIZE
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Check email processor
    try:
        processor = EmailProcessor()
        health_status["components"]["email_processor"] = {
            "status": "healthy",
            "extractors": list(processor.extractors.keys())
        }
    except Exception as e:
        logger.error(f"Email processor health check failed: {e}")
        health_status["components"]["email_processor"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Check configuration
    try:
        config_status = {
            "mistral_api_configured": bool(settings.MISTRAL_API_KEY),
            "gmail_credentials_configured": bool(settings.GMAIL_CREDENTIALS_PATH),
            "email_sender_configured": bool(settings.EMAIL_SENDER),
            "timezone": settings.TIMEZONE,
            "log_level": settings.LOG_LEVEL
        }
        health_status["components"]["configuration"] = {
            "status": "healthy",
            "details": config_status
        }
    except Exception as e:
        logger.error(f"Configuration health check failed: {e}")
        health_status["components"]["configuration"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    return health_status