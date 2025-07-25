"""
Debug script to analyze crypto email structure and attachments.
This helps understand how crypto data is formatted in emails.
"""
import asyncio
import base64
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import Dict, List, Optional, Tuple
import logging
import sys
import io

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Import Gmail API libraries directly
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gmail API settings
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDENTIALS_PATH = Path(__file__).parent / 'credentials' / 'gmail_credentials.json'
TOKEN_PATH = Path(__file__).parent / 'credentials' / 'gmail_token.json'


def get_gmail_service():
    """Get authenticated Gmail service."""
    creds = None
    
    # Load existing token
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                print(f"Error: Gmail credentials file not found at {CREDENTIALS_PATH}")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)


async def analyze_crypto_email_structure():
    """Analyze the structure of crypto emails to understand data format."""
    # Get Gmail service
    print("Authenticating with Gmail...")
    service = get_gmail_service()
    if not service:
        print("Failed to authenticate with Gmail")
        return
    
    print("\nSearching for crypto emails...")
    
    # Search specifically for crypto emails
    try:
        # Get emails from last 48 hours to ensure we find some
        since_date = datetime.now() - timedelta(hours=48)
        query = f'from:hemdesai@hotmail.com subject:"FW: CRYPTO QUANT" after:{since_date.strftime("%Y/%m/%d")}'
        
        print(f"Query: {query}")
        
        # Search for messages
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=5  # Get up to 5 recent crypto emails
        ).execute()
        
        messages = results.get('messages', [])
        print(f"\nFound {len(messages)} crypto emails")
        
        if not messages:
            print("No crypto emails found. Try increasing the time range.")
            return
        
        # Analyze each email
        for idx, message in enumerate(messages):
            print(f"\n{'='*60}")
            print(f"Analyzing Email {idx + 1}/{len(messages)}")
            print('='*60)
            
            # Get full message with attachments
            msg = service.users().messages().get(
                userId='me',
                id=message['id'],
                format='full'
            ).execute()
            
            # Extract headers
            headers = {h['name']: h['value'] for h in msg['payload']['headers']}
            print(f"\nSubject: {headers.get('Subject', 'N/A')}")
            print(f"Date: {headers.get('Date', 'N/A')}")
            print(f"From: {headers.get('From', 'N/A')}")
            
            # Analyze email structure
            print("\nEmail Structure:")
            analyze_payload_structure(msg['payload'], level=0)
            
            # Check for attachments
            print("\nAttachments:")
            attachments = find_attachments(msg['payload'])
            if attachments:
                for att in attachments:
                    print(f"  - Filename: {att['filename']}")
                    print(f"    MimeType: {att['mimeType']}")
                    print(f"    Size: {att.get('size', 'Unknown')} bytes")
                    
                    # If it's an image, save it for inspection
                    if att['mimeType'].startswith('image/'):
                        save_attachment(service, message['id'], att)
            else:
                print("  No attachments found")
            
            # Extract and display content
            print("\nContent Analysis:")
            text_content, html_content = extract_all_content(msg['payload'])
            
            if text_content:
                print(f"\nText Content (first 500 chars):")
                print("-" * 40)
                print(text_content[:500])
                if len(text_content) > 500:
                    print(f"... (total length: {len(text_content)} chars)")
            
            if html_content:
                print(f"\nHTML Content (first 500 chars):")
                print("-" * 40)
                print(html_content[:500])
                if len(html_content) > 500:
                    print(f"... (total length: {len(html_content)} chars)")
                
                # Check for embedded images in HTML
                print("\nChecking for embedded images in HTML:")
                check_embedded_images(html_content)
            
            # Look for specific crypto data patterns
            print("\nSearching for crypto data patterns:")
            search_crypto_patterns(text_content or html_content or "")
            
            # Only analyze first 2 emails in detail
            if idx >= 1:
                break
    
    except Exception as e:
        print(f"Error analyzing emails: {e}")
        import traceback
        traceback.print_exc()


def analyze_payload_structure(payload: Dict, level: int = 0):
    """Recursively analyze email payload structure."""
    indent = "  " * level
    
    mime_type = payload.get('mimeType', 'Unknown')
    print(f"{indent}MimeType: {mime_type}")
    
    if 'filename' in payload:
        print(f"{indent}Filename: {payload['filename']}")
    
    if 'body' in payload:
        body = payload['body']
        if 'size' in body:
            print(f"{indent}Body Size: {body['size']} bytes")
        if 'attachmentId' in body:
            print(f"{indent}Has Attachment ID: {body['attachmentId']}")
    
    if 'parts' in payload:
        print(f"{indent}Parts: {len(payload['parts'])}")
        for i, part in enumerate(payload['parts']):
            print(f"{indent}Part {i+1}:")
            analyze_payload_structure(part, level + 1)


def find_attachments(payload: Dict) -> List[Dict]:
    """Find all attachments in email payload."""
    attachments = []
    
    def search_parts(part):
        if 'filename' in part and part['filename']:
            # This is an attachment
            attachment_info = {
                'filename': part['filename'],
                'mimeType': part.get('mimeType', 'Unknown'),
                'size': part.get('body', {}).get('size', 0),
                'attachmentId': part.get('body', {}).get('attachmentId')
            }
            attachments.append(attachment_info)
        
        # Recursively search sub-parts
        if 'parts' in part:
            for subpart in part['parts']:
                search_parts(subpart)
    
    search_parts(payload)
    return attachments


def extract_all_content(payload: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Extract all text and HTML content from email."""
    text_parts = []
    html_parts = []
    
    def extract_from_part(part):
        mime_type = part.get('mimeType', '')
        
        if mime_type == 'text/plain':
            data = part.get('body', {}).get('data')
            if data:
                try:
                    text_parts.append(base64.urlsafe_b64decode(data).decode('utf-8'))
                except Exception as e:
                    print(f"Error decoding text part: {e}")
        
        elif mime_type == 'text/html':
            data = part.get('body', {}).get('data')
            if data:
                try:
                    html_parts.append(base64.urlsafe_b64decode(data).decode('utf-8'))
                except Exception as e:
                    print(f"Error decoding HTML part: {e}")
        
        # Recursively process sub-parts
        if 'parts' in part:
            for subpart in part['parts']:
                extract_from_part(subpart)
    
    extract_from_part(payload)
    
    text_content = '\n'.join(text_parts) if text_parts else None
    html_content = '\n'.join(html_parts) if html_parts else None
    
    return text_content, html_content


def check_embedded_images(html_content: str):
    """Check for embedded images in HTML content."""
    import re
    
    # Look for img tags
    img_tags = re.findall(r'<img[^>]+>', html_content, re.IGNORECASE)
    print(f"  Found {len(img_tags)} <img> tags")
    
    # Look for data URIs
    data_uris = re.findall(r'data:image/[^;]+;base64,[^"\']+', html_content)
    print(f"  Found {len(data_uris)} embedded base64 images")
    
    # Look for cid references (Content-ID for embedded images)
    cid_refs = re.findall(r'cid:[^"\']+', html_content)
    print(f"  Found {len(cid_refs)} CID references")
    
    # Show sample img tags
    if img_tags:
        print("\n  Sample img tags:")
        for tag in img_tags[:3]:
            print(f"    {tag[:100]}...")


def search_crypto_patterns(content: str):
    """Search for crypto-related patterns in content."""
    import re
    
    patterns = {
        'Crypto symbols': r'\b(BTC|ETH|SOL|ADA|AVAX|LINK|MATIC|DOGE|SHIB|LTC|XRP|BNB|DOT|UNI|MKR)\b',
        'Price patterns': r'\$[\d,]+\.?\d*',
        'Percentage patterns': r'[-+]?\d+\.?\d*%',
        'Buy/Sell signals': r'\b(BUY|SELL|HOLD|LONG|SHORT)\b',
        'Support/Resistance': r'\b(support|resistance|level|target)\b',
        'Table markers': r'<table|<tr|<td|\|',
    }
    
    for pattern_name, pattern in patterns.items():
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            print(f"\n  {pattern_name}:")
            # Show unique matches
            unique_matches = list(set(matches))[:10]
            for match in unique_matches:
                print(f"    - {match}")
            if len(set(matches)) > 10:
                print(f"    ... and {len(set(matches)) - 10} more")


def save_attachment(service, message_id: str, attachment_info: Dict):
    """Save attachment to local file for inspection."""
    try:
        att_id = attachment_info['attachmentId']
        filename = attachment_info['filename']
        
        # Get attachment data
        att = service.users().messages().attachments().get(
            userId='me',
            messageId=message_id,
            id=att_id
        ).execute()
        
        # Decode and save
        file_data = base64.urlsafe_b64decode(att['data'])
        
        # Save to debug folder
        debug_dir = Path(__file__).parent / "debug_crypto_images"
        debug_dir.mkdir(exist_ok=True)
        
        filepath = debug_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        with open(filepath, 'wb') as f:
            f.write(file_data)
        
        print(f"    Saved to: {filepath}")
        
    except Exception as e:
        print(f"    Error saving attachment: {e}")


if __name__ == "__main__":
    # Run the analysis
    asyncio.run(analyze_crypto_email_structure())