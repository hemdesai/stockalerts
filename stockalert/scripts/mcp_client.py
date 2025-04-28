import logging
import requests
from typing import Optional
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent.parent / 'logs' / 'mcp_client.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MCPClient:
    """Client for interacting with the MCP Server for Gmail operations"""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        """Initialize the MCP client with server URL"""
        self.server_url = server_url
        self.session = requests.Session()
        self.timeout = 30  # seconds
        self.connected = self.check_connection()
        
        if self.connected:
            logger.info(f"Successfully connected to MCP server at {server_url}")
        else:
            logger.warning(f"Failed to connect to MCP server at {server_url}")
    
    def check_connection(self) -> bool:
        """Check if the MCP server is reachable and healthy"""
        try:
            response = self.session.get(
                f"{self.server_url}/",
                timeout=5  # Short timeout for health check
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error connecting to MCP server: {e}")
            return False
    
    def get_email_content(self, query: str, max_results: int = 1) -> Optional[str]:
        """Get content from latest matching email"""
        if not self.connected and not self.check_connection():
            logger.error("MCP server is not connected, cannot get email content")
            return None
            
        try:
            response = self.session.post(
                f"{self.server_url}/email/content",
                json={"query": query, "max_results": max_results},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("content")
            elif response.status_code == 404:
                logger.warning(f"No emails found for query: {query}")
                return None
            else:
                logger.error(f"Error getting email content: {response.text}")
                return None
                
        except requests.exceptions.ConnectionError:
            logger.error("Connection error: MCP server is not reachable")
            self.connected = False
            return None
        except requests.exceptions.Timeout:
            logger.error("Timeout error: MCP server did not respond in time")
            return None
        except Exception as e:
            logger.error(f"Error connecting to MCP server: {e}")
            return None
    
    def send_email(self, subject: str, html_content: str, recipient: Optional[str] = None) -> bool:
        """Send an email"""
        if not self.connected and not self.check_connection():
            logger.error("MCP server is not connected, cannot send email")
            return False
            
        try:
            payload = {
                "subject": subject,
                "html_content": html_content
            }
            
            if recipient:
                payload["recipient"] = recipient
                
            response = self.session.post(
                f"{self.server_url}/email/send",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                logger.info(f"Email sent successfully: {subject}")
                return True
            else:
                logger.error(f"Error sending email: {response.text}")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.error("Connection error: MCP server is not reachable")
            self.connected = False
            return False
        except requests.exceptions.Timeout:
            logger.error("Timeout error: MCP server did not respond in time")
            return False
        except Exception as e:
            logger.error(f"Error connecting to MCP server: {e}")
            return False
