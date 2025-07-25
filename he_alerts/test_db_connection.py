"""Test database connection to Neon."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import engine
from app.core.config import settings


async def test_connection():
    """Test the database connection."""
    try:
        print(f"Testing connection to database...")
        print(f"Database URL: {settings.DATABASE_URL.split('@')[1]}")  # Hide password
        
        async with engine.connect() as conn:
            result = await conn.execute("SELECT 1")
            print("✅ Database connection successful!")
            
        print("\nDatabase is ready for use!")
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(test_connection())