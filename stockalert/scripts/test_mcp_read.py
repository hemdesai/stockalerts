"""
Test script to verify MCP client can read emails from Gmail
"""
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from stockalert.scripts.mcp_client import MCPClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_read_email():
    """Test reading emails from Gmail using MCP client"""
    try:
        # Initialize MCP client
        mcp_client = MCPClient()
        
        # Check connection
        if not mcp_client.check_connection():
            logger.error("MCP server is not connected")
            return False
        
        # Try very specific queries that we know work from direct Gmail test
        queries = [
            "subject:\"RISK RANGE\"",  # The RISK RANGE email
            "is:inbox",  # All inbox emails
            "subject:test",  # Emails with test in the subject
            ""  # Empty query should return most recent emails
        ]
        
        # Try each query until we find emails
        content = None
        for query in queries:
            logger.info(f"Attempting to read emails with query: '{query}'")
            content = mcp_client.get_email_content(query)
            if content:
                logger.info(f"Found email content with query: '{query}'")
                break
        
        if content:
            logger.info(f"Successfully retrieved email content, length: {len(content)}")
            logger.info(f"First 200 characters: {content[:200]}...")
            return True
        else:
            logger.error("Failed to retrieve email content")
            return False
            
    except Exception as e:
        logger.error(f"Error testing MCP email reading: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("Starting MCP email read test...")
    success = test_read_email()
    if success:
        logger.info("MCP email read test completed successfully!")
    else:
        logger.error("MCP email read test failed!")