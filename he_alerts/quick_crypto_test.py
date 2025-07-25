"""Quick test to extract crypto data from specific images."""
import asyncio
import requests
import base64
from app.core.config import settings
from app.services.email.gmail_client import GmailClient


async def quick_crypto_test():
    print("Quick Crypto Extraction Test")
    print("=" * 60)
    
    # Get the most recent crypto email
    gmail_client = GmailClient()
    emails = await gmail_client.fetch_recent_emails(hours=72)
    crypto_emails = [e for e in emails if e.get('email_type') == 'crypto']
    
    if not crypto_emails:
        print("No crypto emails found")
        return
    
    email = crypto_emails[0]
    print(f"Processing email: {email.get('subject')}")
    
    # Look for BTC_2.png which typically has the risk ranges
    content = email.get('body_html', '')
    
    # Find BTC_2.png URL
    import re
    btc2_pattern = r'(https://[^"\'>]+BTC_2\.png[^"\'>]*)'
    btc2_matches = re.findall(btc2_pattern, content)
    
    if btc2_matches:
        url = btc2_matches[0]
        print(f"\nFound BTC_2.png: {url[:80]}...")
        
        # Download and OCR this specific image
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            print(f"Downloaded image: {len(response.content)} bytes")
            
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
                print(f"\nOCR Result ({len(ocr_text)} chars):")
                print("-" * 60)
                print(ocr_text[:1000])  # First 1000 chars
                print("-" * 60)
                
                # Check if it contains risk ranges
                if "HEDGEYE RISK RANGES" in ocr_text.upper():
                    print("\n✓ Found HEDGEYE RISK RANGES table!")
                    
                    # Quick extraction of crypto data
                    lines = ocr_text.split('\n')
                    for line in lines:
                        if any(crypto in line.upper() for crypto in ['BTC', 'ETH', 'SOL', 'AVAX', 'AAVE']):
                            print(f"  {line}")
                else:
                    print("\n✗ No risk ranges found in this image")
            else:
                print(f"OCR failed: {ocr_response.status_code}")
    else:
        print("No BTC_2.png found in email")
    
    # Also look for derivative exposures
    print("\n\nLooking for derivative exposures...")
    crypto_pattern = r'(https://[^"\'>]+crypto[^"\'>]+\.png[^"\'>]*)'
    crypto_matches = re.findall(crypto_pattern, content, re.IGNORECASE)
    
    for i, url in enumerate(crypto_matches[:3]):  # Check first 3 crypto images
        print(f"\nChecking crypto image {i+1}: {url[:80]}...")
        # Could process these too if needed


if __name__ == "__main__":
    asyncio.run(quick_crypto_test())