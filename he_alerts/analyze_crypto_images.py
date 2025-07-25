"""Analyze crypto images to get correct tickers."""
import asyncio
import requests
import base64
import re
from app.core.config import settings
from app.services.email.gmail_client import GmailClient


async def analyze_crypto_images():
    print("Analyzing Crypto Images for Correct Tickers")
    print("=" * 60)
    
    # Get the most recent crypto email
    gmail_client = GmailClient()
    emails = await gmail_client.fetch_recent_emails(hours=72)
    crypto_emails = [e for e in emails if e.get('email_type') == 'crypto']
    
    if not crypto_emails:
        print("No crypto emails found")
        return
    
    email = crypto_emails[0]
    subject = email.get('subject', '').encode('ascii', 'ignore').decode('ascii')
    print(f"Processing email: {subject[:50]}...")
    
    # Look for crypto images
    content = email.get('body_html', '')
    
    # Find all crypto-related image URLs
    image_patterns = [
        r'(https://[^"\'>]+crypto[^"\'>]+\.png[^"\'>]*)',
        r'(https://[^"\'>]+\.png[^"\'>]*)'
    ]
    
    all_images = []
    for pattern in image_patterns:
        images = re.findall(pattern, content, re.IGNORECASE)
        all_images.extend(images)
    
    # Remove duplicates
    all_images = list(set(all_images))
    
    print(f"\nFound {len(all_images)} unique images")
    
    # Process images to find the derivative exposures table
    for i, url in enumerate(all_images):
        if 'crypto' in url.lower() or i < 5:  # Check crypto images or first 5
            print(f"\nProcessing image {i+1}: {url[:80]}...")
            
            try:
                # Download image
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    print(f"Downloaded: {len(response.content)} bytes")
                    
                    # OCR the image
                    image_base64 = base64.b64encode(response.content).decode('utf-8')
                    data_url = f"data:image/png;base64,{image_base64}"
                    
                    ocr_headers = {
                        "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    
                    payload = {
                        "document": {"image_url": data_url},
                        "model": "mistral-ocr-latest"
                    }
                    
                    print("Sending to OCR...")
                    ocr_response = requests.post(
                        "https://api.mistral.ai/v1/ocr",
                        headers=ocr_headers,
                        json=payload
                    )
                    
                    if ocr_response.status_code == 200:
                        ocr_data = ocr_response.json()
                        ocr_text = ocr_data['pages'][0]['markdown']
                        
                        # Check if this contains derivative exposures
                        if "DERIVATIVE EXPOSURES" in ocr_text.upper() or "RISK RANGE & TREND SIGNAL" in ocr_text.upper():
                            print("\n✓ Found DERIVATIVE EXPOSURES table!")
                            print("-" * 60)
                            print(ocr_text)
                            print("-" * 60)
                            
                            # Extract tickers from the table
                            lines = ocr_text.split('\n')
                            print("\nExtracted tickers:")
                            for line in lines:
                                # Look for lines with ticker pattern
                                if '|' in line:
                                    parts = line.split('|')
                                    if len(parts) > 0:
                                        potential_ticker = parts[0].strip()
                                        # Check if it looks like a ticker
                                        if re.match(r'^[A-Z]{2,5}$', potential_ticker):
                                            print(f"  - {potential_ticker}: {line}")
                            
                            # Save full OCR for analysis
                            with open(f'crypto_derivative_table_{i}.txt', 'w', encoding='utf-8') as f:
                                f.write(ocr_text)
                            print(f"\nSaved full OCR to: crypto_derivative_table_{i}.txt")
                            
                            return ocr_text
                        else:
                            print("Not the derivative exposures table")
                    else:
                        print(f"OCR failed: {ocr_response.status_code}")
                        
            except Exception as e:
                print(f"Error: {e}")
                continue
    
    print("\nNo derivative exposures table found in images")
    return None


if __name__ == "__main__":
    asyncio.run(analyze_crypto_images())