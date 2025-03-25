"""
MCP Server Demo Script

This script demonstrates how to start the MCP server and use it for Gmail and Google Sheets operations.
"""

import sys
import time
import logging
from pathlib import Path
import subprocess
import threading

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from stockalert.scripts.mcp_client import MCPClient
from stockalert.scripts.extractors.daily_extractor import DailyExtractor
from stockalert.scripts.email_service import EmailService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def start_mcp_server():
    """Start the MCP server in a separate process"""
    try:
        # Get the path to the MCP server script
        mcp_server_path = Path(__file__).parent / 'mcp_server.py'
        
        # Start the server using Python
        process = subprocess.Popen(
            [sys.executable, str(mcp_server_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait a bit to ensure the server starts
        time.sleep(5)
        
        # Check if the process is still running
        if process.poll() is None:
            logger.info("MCP server started successfully")
            return process
        else:
            stdout, stderr = process.communicate()
            logger.error(f"MCP server failed to start: {stderr.decode()}")
            return None
            
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        return None

def test_email_extraction():
    """Test email extraction using MCP client"""
    try:
        logger.info("Testing email extraction with MCP client...")
        
        # Create an instance of DailyExtractor (which now uses MCP client)
        extractor = DailyExtractor()
        
        # Extract data
        data = extractor.extract()
        
        if data:
            logger.info(f"Successfully extracted {len(data)} items from email")
            # Show sample data
            sample = data[:2] if len(data) >= 2 else data
            logger.info(f"Sample data: {sample}")
        else:
            logger.info("No data extracted from email")
            
    except Exception as e:
        logger.error(f"Error testing email extraction: {e}")

def test_email_sending():
    """Test email sending using MCP client"""
    try:
        logger.info("Testing email sending with MCP client...")
        
        # Create an instance of EmailService (which now uses MCP client)
        email_service = EmailService()
        
        # Create a test email
        subject = "MCP Server Test Email"
        html_content = """
        <html>
        <body>
            <h1>MCP Server Test</h1>
            <p>This email was sent using the MCP server.</p>
            <p>If you're seeing this, the MCP server is working correctly!</p>
        </body>
        </html>
        """
        
        # Send the email
        success = email_service.send_email(subject, html_content)
        
        if success:
            logger.info("Successfully sent test email")
        else:
            logger.error("Failed to send test email")
            
    except Exception as e:
        logger.error(f"Error testing email sending: {e}")

def test_sheet_writing():
    """Test writing to Google Sheets using MCP client"""
    try:
        logger.info("Testing Google Sheets writing with MCP client...")
        
        # Create an instance of EmailService (which now uses MCP client)
        email_service = EmailService()
        
        # Create test data
        test_alerts = [
            {
                'ticker': 'AAPL',
                'sentiment': 'BULLISH',
                'name': 'Apple Inc.',
                'action': 'BUY',
                'current_price': 175.50,
                'buy_trade': 170.00,
                'sell_trade': 185.00,
                'category': 'daily'
            },
            {
                'ticker': 'MSFT',
                'sentiment': 'NEUTRAL',
                'name': 'Microsoft Corporation',
                'action': 'HOLD',
                'current_price': 420.25,
                'buy_trade': 400.00,
                'sell_trade': 440.00,
                'category': 'daily'
            }
        ]
        
        # Write to sheet
        success = email_service.write_alerts_to_sheet(test_alerts, 'research', 'mcp_test')
        
        if success:
            logger.info("Successfully wrote test data to Google Sheet")
        else:
            logger.error("Failed to write test data to Google Sheet")
            
    except Exception as e:
        logger.error(f"Error testing Google Sheets writing: {e}")

def main():
    """Main function to demonstrate MCP server"""
    try:
        logger.info("Starting MCP server demo...")
        
        # Start the MCP server
        server_process = start_mcp_server()
        
        if not server_process:
            logger.error("Failed to start MCP server. Exiting demo.")
            return
        
        # Wait for server to initialize
        logger.info("Waiting for MCP server to initialize...")
        time.sleep(5)
        
        # Run tests
        test_email_extraction()
        test_email_sending()
        test_sheet_writing()
        
        # Ask user if they want to stop the server
        input("Press Enter to stop the MCP server and exit...")
        
        # Stop the server
        logger.info("Stopping MCP server...")
        server_process.terminate()
        server_process.wait()
        logger.info("MCP server stopped")
        
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
        if 'server_process' in locals() and server_process:
            server_process.terminate()
            server_process.wait()
            logger.info("MCP server stopped")
    except Exception as e:
        logger.error(f"Error in MCP server demo: {e}")
        if 'server_process' in locals() and server_process:
            server_process.terminate()
            server_process.wait()

if __name__ == "__main__":
    main()
