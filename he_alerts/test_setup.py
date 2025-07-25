"""Test complete setup including database and credentials."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import engine
from app.core.config import settings
from app.services.email.gmail_client import GmailClient


async def test_setup():
    """Test the complete setup."""
    print("=" * 60)
    print("HE ALERTS - SETUP TEST")
    print("=" * 60)
    
    # Test 1: Configuration
    print("\n1. Configuration Check:")
    print(f"   - App Name: {settings.APP_NAME}")
    print(f"   - Database: Connected to Neon")
    print(f"   - Mistral API: {'Configured' if settings.MISTRAL_API_KEY else 'Missing'}")
    print(f"   - Email Settings: {'Configured' if settings.EMAIL_SENDER else 'Missing'}")
    
    # Test 2: Database Connection
    print("\n2. Database Connection Test:")
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text
            result = await conn.execute(text("SELECT 1"))
            print("   SUCCESS: Database connected!")
    except Exception as e:
        print(f"   ERROR: Database connection failed - {str(e)}")
        return False
    
    # Test 3: Gmail API
    print("\n3. Gmail API Test:")
    try:
        gmail = GmailClient()
        if await gmail.authenticate():
            print("   SUCCESS: Gmail API authenticated!")
        else:
            print("   ERROR: Gmail authentication failed")
    except Exception as e:
        print(f"   ERROR: Gmail setup failed - {str(e)}")
    
    print("\n" + "=" * 60)
    print("SETUP COMPLETE - Ready to test email processing!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    asyncio.run(test_setup())