"""Debug IDEAS email structure to understand format."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.email.gmail_client import GmailClient
from bs4 import BeautifulSoup


async def debug_ideas_structure():
    print('=' * 60)
    print('DEBUGGING IDEAS EMAIL STRUCTURE')
    print('=' * 60)
    
    gmail_client = GmailClient()
    
    # Get recent IDEAS emails
    emails = await gmail_client.fetch_recent_emails(hours=168)
    ideas_emails = [email for email in emails if email.get('email_type') == 'ideas']
    
    if ideas_emails:
        print(f"Found {len(ideas_emails)} IDEAS emails")
        ideas_email = ideas_emails[0]
        
        print(f"\nEmail Subject: {ideas_email.get('subject')}")
        print(f"Email Date: {ideas_email.get('received_date')}")
        
        # Check HTML content
        html_content = ideas_email.get('body_html')
        if html_content:
            print(f"\nHTML content length: {len(html_content)} characters")
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for images
            images = soup.find_all('img')
            print(f"\nFound {len(images)} images in HTML")
            for i, img in enumerate(images[:5]):  # Show first 5
                src = img.get('src', 'No src')
                print(f"  Image {i}: {src[:100]}...")
            
            # Look for tables
            tables = soup.find_all('table')
            print(f"\nFound {len(tables)} tables in HTML")
            
            # Look for text patterns
            text = soup.get_text()
            if 'Longs' in text and 'Shorts' in text:
                print("\nFound 'Longs' and 'Shorts' sections in text")
                
                # Find the section containing the data
                for element in soup.find_all(['p', 'div', 'td', 'span']):
                    elem_text = element.get_text()
                    if any(ticker in elem_text for ticker in ['COP', 'DKNG', 'CELH', 'XYL']):
                        print(f"\nFound potential data in {element.name} element:")
                        print(elem_text[:200] + "..." if len(elem_text) > 200 else elem_text)
                        
                        # Check if it's an image
                        img_in_elem = element.find('img')
                        if img_in_elem:
                            print(f"  Contains image: {img_in_elem.get('src', 'No src')[:100]}...")
                        
            # Check for embedded base64 images
            import re
            base64_images = re.findall(r'data:image/[^;]+;base64,[^"\']+', html_content)
            print(f"\nFound {len(base64_images)} embedded base64 images")
            if base64_images:
                print("First base64 image starts with:", base64_images[0][:100] + "...")
                
        # Get the full message structure
        message_id = ideas_email.get('message_id')
        try:
            msg = gmail_client.service.users().messages().get(
                userId='me', 
                id=message_id
            ).execute()
            
            # Check message parts
            def analyze_parts(parts, level=0):
                indent = "  " * level
                for part in parts:
                    mime_type = part.get('mimeType', 'Unknown')
                    filename = part.get('filename', 'No filename')
                    size = part.get('body', {}).get('size', 0)
                    
                    print(f"{indent}Part: {mime_type}, Filename: {filename}, Size: {size}")
                    
                    if 'parts' in part:
                        analyze_parts(part['parts'], level + 1)
            
            print("\nMessage structure:")
            if 'parts' in msg['payload']:
                analyze_parts(msg['payload']['parts'])
            else:
                mime_type = msg['payload'].get('mimeType', 'Unknown')
                print(f"Single part: {mime_type}")
                
        except Exception as e:
            print(f"Error analyzing message structure: {e}")
            
    else:
        print("No IDEAS emails found")


if __name__ == "__main__":
    asyncio.run(debug_ideas_structure())