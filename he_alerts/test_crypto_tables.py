"""
Test the improved crypto extraction by looking for specific tables.
"""
import asyncio
import requests
import base64
from bs4 import BeautifulSoup
from app.services.email.gmail_client import GmailClient
from app.core.config import settings

async def test_crypto_extraction():
    """Test crypto extraction with targeted table search."""
    gmail_client = GmailClient()
    
    # Authenticate
    if not await gmail_client.authenticate():
        print("Failed to authenticate")
        return
    
    print("Authenticated successfully")
    
    # Get latest crypto email
    recent_emails = await gmail_client.fetch_recent_emails(hours=48)
    crypto_emails = [e for e in recent_emails if e.get('email_type') == 'crypto']
    
    if not crypto_emails:
        print("No crypto emails found")
        return
    
    latest_crypto = crypto_emails[0]
    print(f"\nProcessing crypto email: {latest_crypto['message_id']}")
    
    # Get the email HTML content
    email_data = await gmail_client.get_email_by_id(latest_crypto['message_id'])
    html_content = email_data.get('body_html', '')
    
    # Parse HTML to find images
    soup = BeautifulSoup(html_content, 'html.parser')
    images = soup.find_all('img')
    print(f"\nFound {len(images)} images in email")
    
    # Track what we found
    found_tables = []
    
    # Check first 20 images for our target tables
    for idx, img in enumerate(images[:20]):
        src = img.get('src', '')
        if not src:
            continue
            
        print(f"\nChecking image {idx + 1}: {src[:80]}...")
        
        try:
            # Download image
            response = requests.get(src, timeout=10)
            if response.status_code != 200:
                print(f"  Failed to download (status {response.status_code})")
                continue
                
            image_data = response.content
            print(f"  Downloaded: {len(image_data)} bytes")
            
            # Quick OCR to check headers
            ocr_text = await quick_ocr_check(image_data)
            
            if ocr_text:
                # Handle Unicode issues
                ocr_text = ocr_text.encode('ascii', 'replace').decode('ascii')
                ocr_upper = ocr_text.upper()
                
                # Show what we found
                print(f"  OCR preview: {ocr_text[:100].replace(chr(10), ' ')}...")
                
                # Check for our target headers
                if "HEDGEYE RISK RANGES" in ocr_upper:
                    print("  [FOUND] HEDGEYE RISK RANGES table!")
                    found_tables.append(("CRYPTO", idx, src))
                    
                if "DERIVATIVE EXPOSURES" in ocr_upper or "RISK RANGE & TREND SIGNAL" in ocr_upper:
                    print("  [FOUND] DERIVATIVE EXPOSURES table!")
                    found_tables.append(("DERIVATIVE", idx, src))
                    
        except Exception as e:
            print(f"  Error: {e}")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY:")
    print(f"{'='*60}")
    print(f"Total images checked: {min(10, len(images))}")
    print(f"Tables found: {len(found_tables)}")
    
    for table_type, idx, src in found_tables:
        print(f"  - {table_type} table at image {idx + 1}")
        print(f"    URL: {src[:100]}...")


async def quick_ocr_check(image_data: bytes) -> str:
    """Quick OCR to check for headers."""
    try:
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        headers = {
            "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "pixtral-12b-2409",
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Extract the main headers and table titles from this image. Look for text like 'HEDGEYE RISK RANGES' or 'DERIVATIVE EXPOSURES'."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    }
                ]
            }],
            "max_tokens": 200
        }
        
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=15
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return ""
            
    except Exception as e:
        print(f"    OCR error: {e}")
        return ""


if __name__ == "__main__":
    asyncio.run(test_crypto_extraction())