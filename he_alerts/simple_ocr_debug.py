"""Simple OCR debug to analyze text structure without database operations."""
import asyncio
import sys
import base64
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.email.gmail_client import GmailClient
from app.services.email.extractors.etf_parser import extract_largest_image, process_image_with_ocr
from app.core.config import settings


async def debug_ocr_text():
    print('=' * 60)
    print('ANALYZING ETF OCR TEXT STRUCTURE')
    print('=' * 60)
    
    gmail_client = GmailClient()
    
    # Get recent ETF emails
    emails = await gmail_client.fetch_recent_emails(hours=168)
    etf_emails = [email for email in emails if email.get('email_type') == 'etf']
    
    if etf_emails:
        print(f"Found {len(etf_emails)} ETF emails")
        etf_email = etf_emails[0]
        
        # Get the email content
        content = etf_email.get('body_html') or etf_email.get('body_text')
        if content:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract the largest image
            image_data = extract_largest_image(soup, content)
            if image_data:
                print(f"Found image data: {len(image_data)} bytes")
                
                # Convert image to base64
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
                
                print("Calling Mistral OCR API...")
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
                    print(f"First 30 lines:")
                    for i, line in enumerate(lines[:30]):
                        line = line.strip()
                        if line:
                            print(f"  {i:2d}: {line}")
                    
                    # Look for BULLISH/BEARISH
                    bullish_lines = []
                    bearish_lines = []
                    for i, line in enumerate(lines):
                        if 'BULLISH' in line.upper():
                            bullish_lines.append((i, line.strip()))
                        if 'BEARISH' in line.upper():
                            bearish_lines.append((i, line.strip()))
                    
                    print(f"\nBULLISH mentions: {len(bullish_lines)}")
                    for line_num, line in bullish_lines:
                        print(f"  Line {line_num}: {line}")
                    
                    print(f"\nBEARISH mentions: {len(bearish_lines)}")
                    for line_num, line in bearish_lines:
                        print(f"  Line {line_num}: {line}")
                    
                    # Look for table structure
                    table_lines = [line for line in lines if '|' in line]
                    print(f"\nTable lines: {len(table_lines)}")
                    print("First 20 table lines:")
                    for i, line in enumerate(table_lines[:20]):
                        print(f"  {i:2d}: {line.strip()}")
                        
                    # Look for specific patterns around BULLISH/BEARISH
                    print(f"\nLooking for section patterns...")
                    for i, line in enumerate(lines):
                        if 'BULLISH' in line.upper() or 'BEARISH' in line.upper():
                            print(f"Found sentiment line {i}: {line.strip()}")
                            # Show context around it
                            start = max(0, i-2)
                            end = min(len(lines), i+5)
                            for j in range(start, end):
                                prefix = ">>> " if j == i else "    "
                                print(f"  {prefix}{j:2d}: {lines[j].strip()}")
                            print()
                
                else:
                    print(f"OCR API Error: {response.status_code} - {response.text}")
            else:
                print("No image data found")
        else:
            print("No email content found")
    else:
        print("No ETF emails found")


if __name__ == "__main__":
    asyncio.run(debug_ocr_text())