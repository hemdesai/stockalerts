"""
Test script to verify MCP client can send emails via Gmail
"""
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from stockalert.scripts.mcp_client import MCPClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_send_email():
    """Test sending an email using MCP client"""
    try:
        # Initialize MCP client
        mcp_client = MCPClient()
        
        # Check connection
        if not mcp_client.check_connection():
            logger.error("MCP server is not connected")
            return False
        
        # Create test email content
        subject = f"MCP Test Email - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        html_content = f"""
        <html>
        <body>
            <h2>MCP Test Email</h2>
            <p>This is a test email sent via the MCP server at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>If you're seeing this, the MCP server is working correctly for sending emails!</p>
        </body>
        </html>
        """
        recipient = "hemdesai@gmail.com"
        
        # Send the email
        logger.info(f"Attempting to send test email to {recipient}")
        success = mcp_client.send_email(subject, html_content, recipient)
        
        if success:
            logger.info(f"Successfully sent test email to {recipient}")
            return True
        else:
            logger.error(f"Failed to send test email to {recipient}")
            return False
            
    except Exception as e:
        logger.error(f"Error testing MCP email sending: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("Starting MCP email send test...")
    success = test_send_email()
    if success:
        logger.info("MCP email send test completed successfully!")
    else:
        logger.error("MCP email send test failed!")