from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
from pathlib import Path
import os
import sys
import logging
from stockalert.utils.env_loader import load_environment
from stockalert.scripts.mcp_client import MCPClient

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent.parent / 'data' / 'extractor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
env_vars = load_environment()

class BaseEmailExtractor:
    def __init__(self):
        # Initialize MCP client for centralized email operations
        self.mcp_client = MCPClient()
        
        # Keep the original Gmail API setup for fallback
        self.SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
        self.gmail_service = self.setup_gmail()
        
        # Track whether we're using MCP or direct Gmail API
        self.using_mcp = self.mcp_client.check_connection()
        
        if self.using_mcp:
            logger.info("Using MCP client for email operations")
        else:
            logger.warning("MCP client not connected, using direct Gmail API for email operations")
            logger.info("Will attempt to reconnect to MCP server on future operations")

    def setup_gmail(self):
        """Setup Gmail API connection (fallback method)"""
        try:
            creds = None
            token_path = Path(__file__).parent.parent.parent / 'credentials' / 'token.json'
            creds_path = Path(__file__).parent.parent.parent / 'credentials' / 'credentials.json'

            if token_path.exists():
                try:
                    creds = Credentials.from_authorized_user_file(str(token_path), self.SCOPES)
                except Exception as e:
                    logger.error(f"Error loading credentials from token.json: {e}")
                    # If there's an error, we'll create new credentials below
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                    except Exception as e:
                        logger.error(f"Error refreshing credentials: {e}")
                        # If refresh fails, we'll create new credentials
                        creds = None
                
                if not creds:
                    if not creds_path.exists():
                        logger.error(f"Credentials file not found: {creds_path}")
                        return None
                    
                    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), self.SCOPES)
                    creds = flow.run_local_server(port=0)
                    
                    # Save the credentials for the next run
                    with open(token_path, 'w') as token:
                        token.write(creds.to_json())

            return build('gmail', 'v1', credentials=creds)
        except Exception as e:
            logger.error(f"Error setting up Gmail API: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def get_email_content(self, query, max_results=1):
        """Get content from latest matching email using MCP server"""
        try:
            # Check if we should try to reconnect to MCP
            if not self.using_mcp:
                self.check_mcp_connection()
                
            # First try using the MCP client if it's connected
            if self.using_mcp:
                logger.info(f"Attempting to get email content via MCP for query: {query}")
                content = self.mcp_client.get_email_content(query, max_results)
                if content:
                    logger.info(f"Successfully retrieved email content via MCP for query: {query}")
                    return content
                else:
                    logger.warning("MCP client failed to retrieve email content, falling back to direct Gmail API")
                    self.using_mcp = False  # Mark MCP as failed for future calls
            
            # If MCP client fails or is not connected, fall back to direct Gmail API
            if not self.gmail_service:
                logger.error("Gmail API service not initialized, cannot retrieve email content")
                return None
                
            logger.info(f"Using direct Gmail API for query: {query}")
            messages = self.gmail_service.users().messages().list(
                userId='me', q=query, maxResults=max_results
            ).execute().get('messages', [])

            if not messages:
                logger.warning(f"No emails found for query: {query}")
                return None

            message = self.gmail_service.users().messages().get(
                userId='me', id=messages[0]['id'], format='full'
            ).execute()

            if 'payload' in message and 'parts' in message['payload']:
                data = message['payload']['parts'][0]['body'].get('data', '')
            else:
                data = message['payload']['body'].get('data', '')

            if data:
                content = base64.urlsafe_b64decode(data).decode()
                logger.info(f"Successfully retrieved email content via direct Gmail API for query: {query}")
                return content
            
            logger.warning(f"No content found in email for query: {query}")
            return None

        except Exception as e:
            logger.error(f"Error getting email content: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
            
    def check_mcp_connection(self):
        """Check if MCP connection is available and update status"""
        if not self.using_mcp:
            # Try to reconnect to MCP
            if self.mcp_client.check_connection():
                logger.info("Successfully reconnected to MCP server")
                self.using_mcp = True
                return True
            else:
                logger.warning("MCP server still not available")
                return False
        return True