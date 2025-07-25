"""
Gmail API client for fetching and processing emails.
"""
import base64
import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class GmailClient:
    """
    Gmail API client for reading emails and extracting content.
    """
    
    def __init__(self):
        self.service = None
        self.scopes = settings.GMAIL_SCOPES
        self.credentials_path = Path(settings.GMAIL_CREDENTIALS_PATH)
        self.token_path = Path(settings.GMAIL_TOKEN_PATH)
        
        # Ensure credentials directory exists
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Email type classification patterns
        self.email_patterns = {
            "daily": "FW: RISK RANGE™ SIGNALS:",
            "crypto": "FW: CRYPTO QUANT",
            "ideas": "FW: Investing Ideas Newsletter:",
            "etf": "FW: ETF Pro Plus - Levels"
        }
        
        # Category mappings
        self.category_map = {
            "daily": "daily",
            "crypto": "digitalassets", 
            "ideas": "ideas",
            "etf": "etfs"
        }
    
    async def authenticate(self) -> bool:
        """
        Authenticate with Gmail API using OAuth2.
        
        Returns:
            bool: True if authentication successful
        """
        try:
            creds = None
            
            # Load existing token
            if self.token_path.exists():
                creds = Credentials.from_authorized_user_file(str(self.token_path), self.scopes)
            
            # Refresh or get new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        logger.info("Gmail credentials refreshed successfully")
                    except Exception as e:
                        logger.error(f"Error refreshing Gmail credentials: {e}")
                        creds = None
                
                if not creds:
                    if not self.credentials_path.exists():
                        logger.error(f"Gmail credentials file not found: {self.credentials_path}")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_path), self.scopes
                    )
                    creds = flow.run_local_server(port=0)
                    logger.info("New Gmail credentials obtained")
                
                # Save credentials for next run
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
            
            # Build service
            self.service = build('gmail', 'v1', credentials=creds)
            logger.info("Gmail API service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Gmail authentication failed: {e}")
            return False
    
    def classify_email_type(self, subject: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Classify email type based on subject line.
        
        Args:
            subject: Email subject line
            
        Returns:
            Tuple of (email_type, category) or (None, None) if no match
        """
        for email_type, pattern in self.email_patterns.items():
            if pattern in subject:
                category = self.category_map[email_type]
                return email_type, category
        
        return None, None
    
    async def fetch_recent_emails(self, hours: int = 24) -> List[Dict]:
        """
        Fetch recent emails from hemdesai@hotmail.com.
        
        Args:
            hours: Number of hours back to search
            
        Returns:
            List of email data dictionaries
        """
        if not self.service:
            if not await self.authenticate():
                return []
        
        try:
            # Calculate date range
            since_date = datetime.now() - timedelta(hours=hours)
            query = f'from:hemdesai@hotmail.com after:{since_date.strftime("%Y/%m/%d")}'
            
            logger.info(f"Searching Gmail with query: {query}")
            
            # Search for messages
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=50
            ).execute()
            
            messages = results.get('messages', [])
            logger.info(f"Found {len(messages)} messages")
            
            email_data = []
            
            for message in messages:
                try:
                    # Get full message details
                    msg = self.service.users().messages().get(
                        userId='me',
                        id=message['id'],
                        format='full'
                    ).execute()
                    
                    # Extract email data
                    email_info = self._extract_email_data(msg)
                    if email_info:
                        email_data.append(email_info)
                        
                except Exception as e:
                    logger.error(f"Error processing message {message['id']}: {e}")
                    continue
            
            logger.info(f"Successfully processed {len(email_data)} emails")
            return email_data
            
        except HttpError as e:
            logger.error(f"Gmail API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return []
    
    def _extract_email_data(self, message: Dict) -> Optional[Dict]:
        """
        Extract structured data from Gmail message.
        
        Args:
            message: Gmail API message object
            
        Returns:
            Dictionary with email data or None if invalid
        """
        try:
            headers = {h['name']: h['value'] for h in message['payload']['headers']}
            
            subject = headers.get('Subject', '')
            sender = headers.get('From', '')
            date_str = headers.get('Date', '')
            
            # Parse date
            try:
                received_date = parsedate_to_datetime(date_str).replace(tzinfo=None)
            except:
                received_date = datetime.now()
            
            # Classify email type
            email_type, category = self.classify_email_type(subject)
            if not email_type:
                logger.debug(f"Skipping email - no matching pattern: {subject}")
                return None
            
            # Extract email content
            body_text, body_html = self._extract_email_content(message['payload'])
            
            return {
                'message_id': message['id'],
                'thread_id': message['threadId'],
                'subject': subject,
                'sender': sender,
                'received_date': received_date,
                'email_type': email_type,
                'category': category,
                'body_text': body_text,
                'body_html': body_html,
                'raw_content_hash': self._calculate_content_hash(body_text or body_html)
            }
            
        except Exception as e:
            logger.error(f"Error extracting email data: {e}")
            return None
    
    def _extract_email_content(self, payload: Dict) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract text and HTML content from email payload.
        
        Args:
            payload: Gmail message payload
            
        Returns:
            Tuple of (text_content, html_content)
        """
        text_content = None
        html_content = None
        
        def extract_part_content(part):
            nonlocal text_content, html_content
            
            mime_type = part.get('mimeType', '')
            
            if mime_type == 'text/plain':
                data = part.get('body', {}).get('data')
                if data:
                    text_content = base64.urlsafe_b64decode(data).decode('utf-8')
            
            elif mime_type == 'text/html':
                data = part.get('body', {}).get('data')
                if data:
                    html_content = base64.urlsafe_b64decode(data).decode('utf-8')
            
            elif mime_type.startswith('multipart/'):
                for subpart in part.get('parts', []):
                    extract_part_content(subpart)
        
        # Handle different payload structures
        if 'parts' in payload:
            for part in payload['parts']:
                extract_part_content(part)
        else:
            extract_part_content(payload)
        
        return text_content, html_content
    
    def _calculate_content_hash(self, content: str) -> str:
        """
        Calculate SHA256 hash of email content.
        
        Args:
            content: Email content string
            
        Returns:
            SHA256 hash as hex string
        """
        import hashlib
        if not content:
            return ""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    async def get_email_by_id(self, message_id: str) -> Optional[Dict]:
        """
        Get specific email by message ID.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Email data dictionary or None
        """
        if not self.service:
            if not await self.authenticate():
                return None
        
        try:
            msg = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            return self._extract_email_data(msg)
            
        except Exception as e:
            logger.error(f"Error fetching email {message_id}: {e}")
            return None