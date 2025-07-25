"""Download crypto2.png or similar image with derivative exposures."""
import asyncio
import requests
import base64
import re
from app.services.email.gmail_client import GmailClient
from app.core.config import settings


async def find_crypto2_image():
    print("Looking for crypto2.png or derivative exposures image...")
    print("=" * 60)
    
    # Get the most recent crypto email
    gmail_client = GmailClient()
    emails = await gmail_client.fetch_recent_emails(hours=72)
    crypto_emails = [e for e in emails if e.get('email_type') == 'crypto']
    
    if not crypto_emails:
        print("No crypto emails found")
        return
    
    email = crypto_emails[0]
    content = email.get('body_html', '')
    
    # Look for crypto2.png or numbered crypto images
    crypto_pattern = r'(https://[^"\'>]+crypto[^"\'>]*[_-]?\d+\.png[^"\'>]*)'
    crypto_urls = re.findall(crypto_pattern, content, re.IGNORECASE)
    
    print(f"Found {len(crypto_urls)} crypto image URLs")
    
    # Process each to find derivative exposures
    for i, url in enumerate(crypto_urls):
        if 'crypto' in url.lower() and ('2' in url or '1' in url):
            print(f"\nChecking: {url[:100]}...")
            
            try:
                # Download
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    print(f"Downloaded: {len(response.content)} bytes")
                    
                    # Save locally
                    filename = f"crypto_derivative_{i}.png"
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    print(f"Saved as: {filename}")
                    
                    # OCR to check content
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
                    
                    print("Running OCR...")
                    ocr_response = requests.post(
                        "https://api.mistral.ai/v1/ocr",
                        headers=ocr_headers,
                        json=payload
                    )
                    
                    if ocr_response.status_code == 200:
                        ocr_data = ocr_response.json()
                        ocr_text = ocr_data['pages'][0]['markdown']
                        
                        # Check content
                        if "DERIVATIVE" in ocr_text.upper() or any(ticker in ocr_text.upper() for ticker in ['IBIT', 'MSTR', 'MARA', 'RIOT', 'COIN']):
                            print("\n✓ Found derivative exposures content!")
                            print("-" * 60)
                            # Print relevant lines
                            for line in ocr_text.split('\n')[:30]:  # First 30 lines
                                if any(word in line.upper() for word in ['DERIVATIVE', 'IBIT', 'MSTR', 'TICKER', 'BUY', 'SELL', '|']):
                                    print(line)
                            
                            # Save full OCR
                            with open(f'derivative_ocr_{i}.txt', 'w', encoding='utf-8') as f:
                                f.write(ocr_text)
                            print(f"\nSaved full OCR to: derivative_ocr_{i}.txt")
                            return ocr_text
                    else:
                        print(f"OCR failed: {ocr_response.status_code}")
                        
            except Exception as e:
                print(f"Error: {e}")
    
    print("\nNo derivative exposures table found in crypto images")
    return None


if __name__ == "__main__":
    asyncio.run(find_crypto2_image())