"""
Database initialization script.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import engine
from app.models import Base
from app.core.logging import get_logger

logger = get_logger(__name__)


async def create_tables():
    """Create all database tables."""
    try:
        logger.info("Creating database tables...")
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database tables created successfully")
        
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


async def main():
    """Main function."""
    await create_tables()


if __name__ == "__main__":
    asyncio.run(main())