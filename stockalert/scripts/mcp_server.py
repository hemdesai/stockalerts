import logging
import sys
import time
import base64
from pathlib import Path
from typing import Optional

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel
import uvicorn
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from stockalert.utils.env_loader import get_env

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / 'data' / 'mcp_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Models for API requests and responses
class EmailQuery(BaseModel):
    query: str
    max_results: int = 1

class EmailSendRequest(BaseModel):
    subject: str
    html_content: str
    recipient: Optional[str] = None

# MCP Server class
class MCPServer:
    """Mail Client Protocol Server for Gmail interactions"""
    
    def __init__(self):
        """Initialize the MCP server with credentials and caches"""
        try:
            # Set up paths
            self.root_dir = Path(__file__).parent.parent
            self.credentials_dir = self.root_dir / 'credentials'
            self.token_path = self.credentials_dir / 'token.json'
            self.creds_path = self.credentials_dir / 'credentials.json'
            
            # Create credentials directory if it doesn't exist
            self.credentials_dir.mkdir(exist_ok=True)
            
            # Set up Gmail API
            self.SCOPES = [
                'https://mail.google.com/',  # Full Gmail access
                'https://www.googleapis.com/auth/gmail.readonly', 
                'https://www.googleapis.com/auth/gmail.send'
            ]
            self.gmail_service = self.setup_gmail()
            
            # Set up email credentials
            self.sender_email = get_env('EMAIL_SENDER', 'hemdesai@gmail.com')
            self.app_password = get_env('EMAIL_PASSWORD', 'gizp vnlz nmgc lowo')
            self.recipient_email = get_env('EMAIL_RECIPIENT', 'hemdesai@gmail.com')
            
            # Set up caches
            self.email_cache = {}
            
            # Set up cache expiry times (in seconds)
            self.email_cache_expiry = 300  # 5 minutes
            
            logger.info("MCP server initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing MCP server: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def setup_gmail(self):
        """Setup Gmail API connection"""
        try:
            creds = None
            
            # Check if token.json exists
            if self.token_path.exists():
                try:
                    creds = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)
                    logger.info("Loaded credentials from token.json")
                except Exception as e:
                    logger.error(f"Error loading credentials from token.json: {e}")
                    # If there's an error, we'll create new credentials below
            
            # If no valid credentials, create new ones
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        logger.info("Refreshed expired credentials")
                    except Exception as e:
                        logger.error(f"Error refreshing credentials: {e}")
                        # If refresh fails, we'll create new credentials
                        creds = None
                
                # If still no valid credentials, run the flow
                if not creds:
                    try:
                        from google_auth_oauthlib.flow import InstalledAppFlow
                        
                        # Check if credentials.json exists
                        if not self.creds_path.exists():
                            logger.error(f"credentials.json not found at {self.creds_path}")
                            raise FileNotFoundError(f"credentials.json not found at {self.creds_path}")
                        
                        logger.info(f"Starting OAuth flow with scopes: {self.SCOPES}")
                        flow = InstalledAppFlow.from_client_secrets_file(str(self.creds_path), self.SCOPES)
                        # Run the OAuth flow with default settings to match Google Cloud Console configuration
                        creds = flow.run_local_server(port=0)
                        logger.info("Successfully completed OAuth flow")
                        
                        # Save the credentials for the next run
                        with open(self.token_path, 'w') as token:
                            token.write(creds.to_json())
                            logger.info(f"Saved new credentials to {self.token_path}")
                    except Exception as e:
                        logger.error(f"Error creating new credentials: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        raise
            
            # Build the Gmail service
            service = build('gmail', 'v1', credentials=creds)
            logger.info("Successfully built Gmail service")
            return service
            
        except Exception as e:
            logger.error(f"Error setting up Gmail: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def get_email_content(self, query: str, max_results: int = 1) -> Optional[str]:
        """Get content from latest matching email"""
        try:
            # Check cache first
            cache_key = f"{query}_{max_results}"
            if cache_key in self.email_cache:
                cache_entry = self.email_cache[cache_key]
                if time.time() - cache_entry['timestamp'] < self.email_cache_expiry:
                    logger.info(f"Using cached email content for query: {query}")
                    return cache_entry['content']
            
            # Query Gmail API
            try:
                messages = self.gmail_service.users().messages().list(
                    userId='me', q=query, maxResults=max_results
                ).execute().get('messages', [])
            except HttpError as e:
                logger.error(f"Error querying Gmail API: {e}")
                return None
            
            if not messages:
                logger.info(f"No emails found for query: {query}")
                return None
            
            # Get the message content
            try:
                message = self.gmail_service.users().messages().get(
                    userId='me', id=messages[0]['id'], format='full'
                ).execute()
            except HttpError as e:
                logger.error(f"Error getting message content: {e}")
                return None
            
            # Extract the message content
            content = None
            
            if 'payload' in message:
                if 'parts' in message['payload']:
                    # Multipart message - try to find HTML part first
                    for part in message['payload']['parts']:
                        if part.get('mimeType') == 'text/html':
                            data = part['body'].get('data', '')
                            if data:
                                content = base64.urlsafe_b64decode(data).decode()
                                break
                    
                    # If no HTML part found, try to find text part
                    if not content:
                        for part in message['payload']['parts']:
                            if part.get('mimeType') == 'text/plain':
                                data = part['body'].get('data', '')
                                if data:
                                    content = base64.urlsafe_b64decode(data).decode()
                                    break
                    
                    # If still no content, try the first part
                    if not content and message['payload']['parts']:
                        data = message['payload']['parts'][0]['body'].get('data', '')
                        if data:
                            content = base64.urlsafe_b64decode(data).decode()
                else:
                    # Single part message
                    data = message['payload']['body'].get('data', '')
                    if data:
                        content = base64.urlsafe_b64decode(data).decode()
            
            if content:
                # Cache the content
                self.email_cache[cache_key] = {
                    'content': content,
                    'timestamp': time.time()
                }
                
                return content
            else:
                logger.warning(f"Could not extract content from message ID: {messages[0]['id']}")
                return None
        except Exception as e:
            logger.error(f"Error getting email content: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def send_email(self, subject: str, html_content: str, recipient: Optional[str] = None) -> bool:
        """Send an email using Gmail SMTP with app password"""
        try:
            # Use the provided recipient or default
            to_email = recipient or self.recipient_email
            
            # Create the email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = to_email
            
            # Add HTML content
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send the email via Gmail SMTP
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(self.sender_email, self.app_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully: {subject}")
            return True
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

# FastAPI application
app = FastAPI(title="Stock Alert MCP Server", 
              description="Mail Client Protocol Server for Gmail interactions")

# Global MCP server instance
mcp_server = None

@app.on_event("startup")
def startup_event():
    """Initialize the MCP server on startup"""
    global mcp_server
    try:
        mcp_server = MCPServer()
        logger.info("MCP server initialized on startup")
    except Exception as e:
        logger.error(f"Error initializing MCP server on startup: {e}")
        import traceback
        logger.error(traceback.format_exc())

@app.get("/")
def root():
    """Health check endpoint"""
    return {"status": "healthy", "service": "MCP Server", "version": "1.0"}

@app.post("/email/content")
def get_email_content(query: EmailQuery):
    """Get content from latest matching email"""
    global mcp_server
    if not mcp_server:
        raise HTTPException(status_code=500, detail="MCP server not initialized")
    
    content = mcp_server.get_email_content(query.query, query.max_results)
    if content:
        return {"content": content}
    else:
        raise HTTPException(status_code=404, detail="No matching emails found")

@app.post("/email/send")
def send_email(request: EmailSendRequest):
    """Send an email"""
    global mcp_server
    if not mcp_server:
        raise HTTPException(status_code=500, detail="MCP server not initialized")
    
    success = mcp_server.send_email(request.subject, request.html_content, request.recipient)
    if success:
        return {"status": "success", "message": "Email sent successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send email")

def start_server():
    """Start the MCP server"""
    try:
        # Use a fixed port for easier configuration
        port = 8000
        host = "0.0.0.0"  # Listen on all interfaces
        
        logger.info(f"Starting MCP server on {host}:{port}")
        uvicorn.run(app, host=host, port=port)
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    start_server()
