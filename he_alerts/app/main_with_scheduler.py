"""
FastAPI application with schedulers enabled.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1.api import api_router
from app.services.scheduler.email_scheduler import EmailScheduler
from app.services.scheduler.price_updater import PriceUpdateScheduler


# Initialize schedulers
email_scheduler = EmailScheduler()
price_scheduler = PriceUpdateScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler with schedulers.
    
    Args:
        app: FastAPI application instance
        
    Yields:
        None during application lifetime
    """
    # Startup
    logger = setup_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Log level: {settings.LOG_LEVEL}")
    
    # Start schedulers
    logger.info("Starting email scheduler...")
    email_scheduler.start()
    
    logger.info("Starting price update scheduler...")
    price_scheduler.start()
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")
    
    # Stop schedulers
    logger.info("Stopping schedulers...")
    email_scheduler.stop()
    price_scheduler.stop()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Automated stock alert system with email processing and IBKR integration",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with basic information."""
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs_url": "/docs" if settings.DEBUG else "disabled",
        "api_version": "v1",
        "api_prefix": settings.API_V1_STR,
        "schedulers": {
            "email": "active",
            "price_updates": "active"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main_with_scheduler:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.RELOAD,
        workers=settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower()
    )