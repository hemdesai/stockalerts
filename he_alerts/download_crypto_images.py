"""
Download crypto chart images from email to analyze their content.
"""
import asyncio
import base64
from datetime import datetime, timedelta
from pathlib import Path
import re
import requests
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

# Gmail API settings
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDENTIALS_PATH = Path(__file__).parent / 'credentials' / 'gmail_credentials.json'
TOKEN_PATH = Path(__file__).parent / 'credentials' / 'gmail_token.json'


def get_gmail_service():
    """Get authenticated Gmail service."""
    creds = None
    
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    
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
        
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)


def extract_image_urls(html_content: str):
    """Extract Hedgeye chart image URLs from HTML content."""
    # Pattern to find chart images
    patterns = [
        r'https://d1yhils6iwh5l5\.cloudfront\.net/charts/resized/\d+/original/([^"]+\.png)',
        r'https://hedgeye\.s3\.amazonaws\.com/attachments/([^"]+)',
    ]
    
    image_urls = []
    for pattern in patterns:
        matches = re.findall(pattern, html_content)
        for match in matches:
            if pattern.startswith('https://d1yhils6iwh5l5'):
                url = f'https://d1yhils6iwh5l5.cloudfront.net/charts/resized/143426/original/{match}'
            else:
                url = f'https://hedgeye.s3.amazonaws.com/attachments/{match}'
            
            # Focus on crypto-related images
            if any(crypto in match.upper() for crypto in ['BTC', 'ETH', 'CRYPTO', 'GIP', 'ETF']):
                image_urls.append((match, url))
    
    return image_urls


async def download_crypto_images():
    """Download crypto images from recent email."""
    print("Authenticating with Gmail...")
    service = get_gmail_service()
    if not service:
        print("Failed to authenticate with Gmail")
        return
    
    print("\nFetching most recent crypto email...")
    
    try:
        # Get the most recent crypto email
        since_date = datetime.now() - timedelta(hours=48)
        query = f'from:hemdesai@hotmail.com subject:"FW: CRYPTO QUANT" after:{since_date.strftime("%Y/%m/%d")}'
        
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=1
        ).execute()
        
        messages = results.get('messages', [])
        if not messages:
            print("No crypto emails found")
            return
        
        # Get the full message
        msg = service.users().messages().get(
            userId='me',
            id=messages[0]['id'],
            format='full'
        ).execute()
        
        # Extract HTML content
        html_content = None
        
        def extract_content(part):
            nonlocal html_content
            mime_type = part.get('mimeType', '')
            
            if mime_type == 'text/html':
                data = part.get('body', {}).get('data')
                if data:
                    html_content = base64.urlsafe_b64decode(data).decode('utf-8')
            
            if 'parts' in part:
                for subpart in part['parts']:
                    extract_content(subpart)
        
        extract_content(msg['payload'])
        
        if not html_content:
            print("No HTML content found in email")
            return
        
        # Extract image URLs
        print("\nExtracting image URLs...")
        image_urls = extract_image_urls(html_content)
        
        print(f"Found {len(image_urls)} crypto-related images")
        
        # Create directory for images
        image_dir = Path(__file__).parent / "crypto_images"
        image_dir.mkdir(exist_ok=True)
        
        # Download images
        for filename, url in image_urls[:10]:  # Download first 10
            print(f"\nDownloading: {filename}")
            print(f"URL: {url}")
            
            try:
                # Add email parameter to URL if needed
                if '?src=email' not in url:
                    url += '?src=email&email=hemdesai@hotmail.com'
                
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    filepath = image_dir / filename
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    print(f"Saved to: {filepath}")
                else:
                    print(f"Failed to download: {response.status_code}")
            
            except Exception as e:
                print(f"Error downloading {filename}: {e}")
        
        print(f"\nImages saved to: {image_dir}")
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(download_crypto_images())