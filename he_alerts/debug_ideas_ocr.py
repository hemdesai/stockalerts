"""Debug IDEAS OCR to understand why prices aren't being extracted correctly."""
import asyncio
import sys
import base64
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.email.gmail_client import GmailClient
from app.core.config import settings


async def debug_ideas_ocr():
    print('=' * 60)
    print('DEBUGGING IDEAS OCR TEXT EXTRACTION')
    print('=' * 60)
    
    gmail_client = GmailClient()
    
    # Get recent IDEAS emails
    emails = await gmail_client.fetch_recent_emails(hours=168)
    ideas_emails = [email for email in emails if email.get('email_type') == 'ideas']
    
    if ideas_emails:
        print(f"Found {len(ideas_emails)} IDEAS emails")
        ideas_email = ideas_emails[0]
        
        # Get attachments
        message_id = ideas_email.get('message_id')
        
        # Fetch the full message with attachments
        try:
            msg = gmail_client.service.users().messages().get(
                userId='me', 
                id=message_id
            ).execute()
            
            # Look for PNG attachments
            attachments = []
            if 'parts' in msg['payload']:
                for part in msg['payload']['parts']:
                    if part.get('filename', '').lower().endswith('.png'):
                        attachment_id = part['body'].get('attachmentId')
                        if attachment_id:
                            att = gmail_client.service.users().messages().attachments().get(
                                userId='me',
                                messageId=message_id,
                                id=attachment_id
                            ).execute()
                            
                            data = att['data']
                            # Fix base64 padding if needed
                            data += '=' * (4 - len(data) % 4)
                            file_data = base64.urlsafe_b64decode(data)
                            
                            attachments.append({
                                'filename': part['filename'],
                                'data': file_data
                            })
                            print(f"Found attachment: {part['filename']} ({len(file_data)} bytes)")
            
            if attachments:
                # Process the first PNG attachment
                attachment = attachments[0]
                image_data = attachment['data']
                
                # Convert to base64 for OCR
                image_base64 = base64.b64encode(image_data).decode('utf-8')
                data_url = f"data:image/png;base64,{image_base64}"
                
                # Call Mistral OCR API
                headers = {
                    "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "document": {"image_url": data_url},
                    "model": "mistral-ocr-latest"
                }
                
                print("\nCalling Mistral OCR API...")
                response = requests.post(
                    "https://api.mistral.ai/v1/ocr",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    ocr_data = response.json()
                    ocr_text = ocr_data['pages'][0]['markdown']
                    
                    print(f"\n{'='*60}")
                    print("FULL OCR TEXT OUTPUT:")
                    print(f"{'='*60}")
                    print(ocr_text)
                    print(f"{'='*60}")
                    
                    # Analyze the structure
                    lines = ocr_text.split('\n')
                    print(f"\nOCR TEXT ANALYSIS:")
                    print(f"Total lines: {len(lines)}")
                    
                    # Look for Longs/Shorts sections
                    longs_idx = shorts_idx = -1
                    for i, line in enumerate(lines):
                        if 'Longs' in line or 'LONGS' in line.upper():
                            longs_idx = i
                            print(f"Found Longs section at line {i}: {line.strip()}")
                        if 'Shorts' in line or 'SHORTS' in line.upper():
                            shorts_idx = i
                            print(f"Found Shorts section at line {i}: {line.strip()}")
                    
                    # Show lines with table data
                    print(f"\nTable lines with prices:")
                    for i, line in enumerate(lines):
                        if '|' in line and '$' in line:
                            print(f"  {i:2d}: {line}")
                    
                    # Look for specific patterns
                    print(f"\nLooking for price patterns...")
                    import re
                    for i, line in enumerate(lines):
                        # Look for lines with ticker and prices
                        if re.search(r'[A-Z]{2,5}', line) and '$' in line:
                            print(f"Line {i}: {line.strip()}")
                            # Extract all prices from the line
                            prices = re.findall(r'\$[\d,]+\.?\d*', line)
                            if prices:
                                print(f"  Found prices: {prices}")
                    
                else:
                    print(f"OCR API Error: {response.status_code} - {response.text}")
            else:
                print("No PNG attachments found in IDEAS email")
                
        except Exception as e:
            print(f"Error fetching attachments: {e}")
    else:
        print("No IDEAS emails found")


if __name__ == "__main__":
    asyncio.run(debug_ideas_ocr())