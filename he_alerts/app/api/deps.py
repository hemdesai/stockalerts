"""
FastAPI dependencies.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.email_processor import EmailProcessor

# Database dependency
async def get_database() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    async for session in get_db():
        yield session

# Email processor dependency
def get_email_processor() -> EmailProcessor:
    """Get email processor instance."""
    return EmailProcessor()