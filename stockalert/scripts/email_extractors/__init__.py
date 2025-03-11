from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
from pathlib import Path
import os
import sys
from stockalert.utils.env_loader import load_environment

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load environment variables
env_vars = load_environment()

class BaseEmailExtractor:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
        self.gmail_service = self.setup_gmail()

    def setup_gmail(self):
        """Setup Gmail API connection"""
        creds = None
        token_path = Path(__file__).parent.parent.parent / 'token.json'
        creds_path = Path(__file__).parent.parent.parent / 'credentials.json'

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), self.SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), self.SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())

        return build('gmail', 'v1', credentials=creds)

    def get_email_content(self, query, max_results=1):
        """Get content from latest matching email"""
        try:
            messages = self.gmail_service.users().messages().list(
                userId='me', q=query, maxResults=max_results
            ).execute().get('messages', [])

            if not messages:
                print(f"No emails found for query: {query}")
                return None

            message = self.gmail_service.users().messages().get(
                userId='me', id=messages[0]['id'], format='full'
            ).execute()

            if 'payload' in message and 'parts' in message['payload']:
                data = message['payload']['parts'][0]['body'].get('data', '')
            else:
                data = message['payload']['body'].get('data', '')

            if data:
                return base64.urlsafe_b64decode(data).decode()
            return None

        except Exception as e:
            print(f"Error getting email content: {e}")
            return None 