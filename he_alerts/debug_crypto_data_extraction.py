"""
Debug script to extract and analyze crypto data from email content.
This script focuses on finding the actual crypto trading data in the email body.
"""
import asyncio
import base64
from datetime import datetime, timedelta
from pathlib import Path
import re
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


def extract_content_sections(text_content: str):
    """Extract different sections from the email text."""
    sections = {}
    
    # Try to find common section markers
    section_patterns = [
        r"RISK RANGE.*?(?=\n\n|\Z)",
        r"SIGNAL STRENGTH.*?(?=\n\n|\Z)",
        r"CRYPTO LEVELS.*?(?=\n\n|\Z)",
        r"BITCOIN.*?(?=\n\n|\Z)",
        r"ETHEREUM.*?(?=\n\n|\Z)",
        r"SOLANA.*?(?=\n\n|\Z)",
        r"BUY.*?(?=\n\n|\Z)",
        r"SELL.*?(?=\n\n|\Z)",
        r"SUPPORT.*?(?=\n\n|\Z)",
        r"RESISTANCE.*?(?=\n\n|\Z)",
    ]
    
    for pattern in section_patterns:
        matches = re.findall(pattern, text_content, re.DOTALL | re.IGNORECASE)
        if matches:
            sections[pattern] = matches
    
    return sections


def find_crypto_data_patterns(content: str):
    """Look for crypto trading data patterns."""
    patterns = {
        # Look for crypto with prices
        'crypto_with_price': r'(\b(?:BTC|BITCOIN|ETH|ETHEREUM|SOL|SOLANA|ADA|AVAX|LINK|MATIC|DOGE|SHIB|LTC|XRP|BNB|DOT|UNI|MKR)\b)[:\s]*\$?([\d,]+\.?\d*)',
        
        # Look for buy/sell levels
        'buy_sell_levels': r'(BUY|SELL|LONG|SHORT)[:\s]*\$?([\d,]+\.?\d*)',
        
        # Look for support/resistance
        'support_resistance': r'(SUPPORT|RESISTANCE|LEVEL|TARGET)[:\s]*\$?([\d,]+\.?\d*)',
        
        # Look for percentage changes
        'percentage_changes': r'([\+\-]?\d+\.?\d*%)',
        
        # Look for price ranges
        'price_ranges': r'\$?([\d,]+\.?\d*)\s*[-–—]\s*\$?([\d,]+\.?\d*)',
        
        # Look for signal strength
        'signal_strength': r'SIGNAL\s*STRENGTH[:\s]*(\w+)',
        
        # Look for risk range
        'risk_range': r'RISK\s*RANGE[:\s]*([^\n]+)',
        
        # Table-like structures
        'table_rows': r'^([A-Z]+[\w\s]*?)[\s\|:]+\$?([\d,]+\.?\d*)[\s\|]+\$?([\d,]+\.?\d*)',
    }
    
    results = {}
    for name, pattern in patterns.items():
        matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
        if matches:
            results[name] = matches
    
    return results


def analyze_table_structures(content: str):
    """Look for table-like structures in the content."""
    # Split content into lines
    lines = content.split('\n')
    
    table_sections = []
    current_table = []
    in_table = False
    
    for line in lines:
        # Check if line looks like a table row (has multiple columns separated by spaces/tabs/pipes)
        if re.search(r'[\|\t]|(\s{2,})', line) and any(char.isdigit() for char in line):
            in_table = True
            current_table.append(line)
        elif in_table and line.strip() == '':
            # Empty line might end the table
            if current_table:
                table_sections.append('\n'.join(current_table))
                current_table = []
            in_table = False
        elif in_table:
            current_table.append(line)
    
    # Don't forget the last table
    if current_table:
        table_sections.append('\n'.join(current_table))
    
    return table_sections


async def analyze_crypto_data():
    """Analyze crypto email data extraction."""
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
        
        # Extract text content
        text_content = None
        html_content = None
        
        def extract_content(part):
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
            
            if 'parts' in part:
                for subpart in part['parts']:
                    extract_content(subpart)
        
        extract_content(msg['payload'])
        
        if not text_content and not html_content:
            print("No content found in email")
            return
        
        # Analyze text content
        print("\n" + "="*60)
        print("TEXT CONTENT ANALYSIS")
        print("="*60)
        
        if text_content:
            # Extract sections
            sections = extract_content_sections(text_content)
            print(f"\nFound {len(sections)} potential sections")
            for section_name, matches in sections.items():
                print(f"\n{section_name}:")
                for match in matches[:2]:  # Show first 2 matches
                    print(f"  {match[:100]}...")
            
            # Find crypto data patterns
            print("\n" + "-"*40)
            print("CRYPTO DATA PATTERNS")
            print("-"*40)
            
            patterns = find_crypto_data_patterns(text_content)
            for pattern_name, matches in patterns.items():
                print(f"\n{pattern_name}:")
                for match in matches[:5]:  # Show first 5 matches
                    print(f"  {match}")
            
            # Look for table structures
            print("\n" + "-"*40)
            print("TABLE STRUCTURES")
            print("-"*40)
            
            tables = analyze_table_structures(text_content)
            for i, table in enumerate(tables[:3]):  # Show first 3 tables
                print(f"\nTable {i+1}:")
                print(table)
            
            # Show a larger sample of the text around key terms
            print("\n" + "-"*40)
            print("CONTEXT AROUND KEY TERMS")
            print("-"*40)
            
            key_terms = ['BTC', 'BITCOIN', 'ETH', 'ETHEREUM', 'BUY', 'SELL', 'SIGNAL', 'RISK RANGE']
            for term in key_terms:
                pattern = rf'.{{0,100}}\b{term}\b.{{0,100}}'
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                if matches:
                    print(f"\n{term}:")
                    for match in matches[:2]:
                        print(f"  ...{match.strip()}...")
            
            # Save full text content for manual inspection
            output_file = Path(__file__).parent / f"crypto_email_text_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(text_content)
            print(f"\nFull text content saved to: {output_file}")
        
        # Brief HTML analysis
        if html_content:
            print("\n" + "="*60)
            print("HTML CONTENT ANALYSIS")
            print("="*60)
            
            # Remove HTML tags to get plain text
            from html.parser import HTMLParser
            
            class HTMLTextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text = []
                
                def handle_data(self, data):
                    self.text.append(data)
                
                def get_text(self):
                    return ' '.join(self.text)
            
            parser = HTMLTextExtractor()
            parser.feed(html_content)
            html_text = parser.get_text()
            
            # Find patterns in HTML text
            patterns = find_crypto_data_patterns(html_text)
            for pattern_name, matches in patterns.items():
                if matches:
                    print(f"\n{pattern_name} (from HTML):")
                    for match in matches[:3]:
                        print(f"  {match}")
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(analyze_crypto_data())