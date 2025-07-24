import base64
import logging
import os
import time
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .mcp_client import MCPClient

# Set up logging
logger = logging.getLogger(__name__)

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
            logger.info("MCP server connection successful. Using MCP for email operations.")
        else:
            logger.warning("MCP server not available. Falling back to direct Gmail API.")

    def setup_gmail(self):
        creds = None
        # Define paths relative to this file's location
        script_dir = os.path.dirname(__file__)
        credentials_dir = os.path.abspath(os.path.join(script_dir, '..', 'credentials'))
        token_path = os.path.join(credentials_dir, 'token.json')
        credentials_path = os.path.join(credentials_dir, 'credentials.json')

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Error refreshing token: {e}")
                    creds = self.run_gmail_flow(credentials_path)
            else:
                creds = self.run_gmail_flow(credentials_path)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        return build('gmail', 'v1', credentials=creds)

    def run_gmail_flow(self, credentials_path):
        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_path, self.SCOPES)
        return flow.run_local_server(port=0)

    def get_email_content(self, query):
        if self.using_mcp:
            try:
                return self.mcp_client.get_email_content(query)
            except Exception as e:
                logger.error(f"MCP client failed to get email content: {e}. Falling back to direct Gmail API.")
                self.using_mcp = False # Disable MCP for subsequent calls in this session
        
        # Fallback to direct Gmail API
        return self.get_email_content_direct(query)

    def get_email_content_direct(self, query):
        try:
            response = self.gmail_service.users().messages().list(userId='me', q=query, maxResults=1).execute()
            messages = response.get('messages', [])
            if not messages:
                logger.warning(f"No emails found for query: {query}")
                return None

            message = self.gmail_service.users().messages().get(userId='me', id=messages[0]['id']).execute()
            
            if 'parts' in message['payload']:
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
            logger.error(f"An error occurred with direct Gmail API: {e}")
            return None

    def get_email_attachments(self, query):
        if self.using_mcp:
            try:
                return self.mcp_client.get_email_attachments(query)
            except Exception as e:
                logger.error(f"MCP client failed to get attachments: {e}. Falling back to direct Gmail API.")
                self.using_mcp = False

        return self.get_email_attachments_direct(query)

    def get_email_attachments_direct(self, query):
        try:
            response = self.gmail_service.users().messages().list(userId='me', q=query, maxResults=1).execute()
            messages = response.get('messages', [])
            if not messages:
                logger.warning(f"No emails found for query: {query}")
                return []

            msg_id = messages[0]['id']
            message = self.gmail_service.users().messages().get(userId='me', id=msg_id).execute()
            parts = message['payload'].get('parts', [])
            attachments = []
            for part in parts:
                if part.get('filename'):
                    attachment_id = part['body'].get('attachmentId')
                    if attachment_id:
                        attachment = self.gmail_service.users().messages().attachments().get(
                            userId='me', messageId=msg_id, id=attachment_id).execute()
                        file_data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))
                        attachments.append({'filename': part['filename'], 'data': file_data})
            logger.info(f"Found {len(attachments)} attachments via direct Gmail API for query: {query}")
            return attachments
        except Exception as e:
            logger.error(f"An error occurred while fetching attachments directly: {e}")
            return []
