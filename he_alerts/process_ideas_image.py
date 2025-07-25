"""Process the IDEAS image from the HTML email."""
import asyncio
import sys
import requests
import base64
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.email.gmail_client import GmailClient
from app.core.config import settings
from bs4 import BeautifulSoup


async def process_ideas_image():
    print('=' * 60)
    print('PROCESSING IDEAS IMAGE FROM EMAIL')
    print('=' * 60)
    
    gmail_client = GmailClient()
    
    # Get recent IDEAS emails
    emails = await gmail_client.fetch_recent_emails(hours=168)
    ideas_emails = [email for email in emails if email.get('email_type') == 'ideas']
    
    if ideas_emails:
        ideas_email = ideas_emails[0]
        html_content = ideas_email.get('body_html')
        
        if html_content:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for the main ideas image
            for img in soup.find_all('img'):
                src = img.get('src', '')
                # Look for the screenshot image (not the header)
                if 'Screenshot' in src and 'cloudfront.net' in src:
                    print(f"Found IDEAS data image: {src}")
                    
                    # Download the image
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                    
                    response = requests.get(src, headers=headers, timeout=15)
                    if response.status_code == 200:
                        image_data = response.content
                        print(f"Downloaded image: {len(image_data)} bytes")
                        
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
                            print("OCR TEXT OUTPUT:")
                            print(f"{'='*60}")
                            print(ocr_text)
                            print(f"{'='*60}")
                            
                            # Parse the data
                            lines = ocr_text.split('\n')
                            
                            print("\nParsing extracted data...")
                            stocks = []
                            current_section = None
                            
                            for line in lines:
                                # Check for section headers
                                if 'Longs' in line:
                                    current_section = 'bullish'
                                    print(f"Found Longs section: {line}")
                                elif 'Shorts' in line:
                                    current_section = 'bearish'
                                    print(f"Found Shorts section: {line}")
                                
                                # Parse data rows
                                if '|' in line and current_section:
                                    parts = [p.strip() for p in line.split('|')]
                                    if len(parts) >= 4:
                                        # Try to extract ticker and prices
                                        import re
                                        for i, part in enumerate(parts):
                                            # Check if this could be a ticker
                                            if re.match(r'^[A-Z]{2,5}$', part):
                                                ticker = part
                                                
                                                # Look for prices in subsequent parts
                                                prices = []
                                                for j in range(i+1, len(parts)):
                                                    price_match = re.search(r'\$?([\d,]+\.?\d*)', parts[j])
                                                    if price_match:
                                                        prices.append(float(price_match.group(1).replace(',', '')))
                                                
                                                if len(prices) >= 2:
                                                    # Skip closing price, get trend range prices
                                                    if len(prices) >= 3:
                                                        buy_price = prices[1]  # Second price
                                                        sell_price = prices[2]  # Third price
                                                    else:
                                                        buy_price = prices[0]
                                                        sell_price = prices[1]
                                                    
                                                    stock = {
                                                        'ticker': ticker,
                                                        'sentiment': current_section,
                                                        'buy_trade': buy_price,
                                                        'sell_trade': sell_price
                                                    }
                                                    stocks.append(stock)
                                                    print(f"Extracted: {ticker} ({current_section}) - Buy: ${buy_price}, Sell: ${sell_price}")
                                                    break
                            
                            print(f"\nTotal stocks extracted: {len(stocks)}")
                            
                            # Compare with expected values
                            expected = {
                                'COP': (211.00, 223.00),
                                'DKNG': (41.42, 45.65),
                                'CELH': (43.03, 46.56),
                                'XYL': (128.00, 136.00),
                                'COIN': (355.00, 431.00),
                                'PLNT': (106.00, 116.00)
                            }
                            
                            print("\nValidation against expected values:")
                            for stock in stocks:
                                ticker = stock['ticker']
                                if ticker in expected:
                                    exp_buy, exp_sell = expected[ticker]
                                    actual_buy = stock['buy_trade']
                                    actual_sell = stock['sell_trade']
                                    match = (abs(actual_buy - exp_buy) < 1 and abs(actual_sell - exp_sell) < 1)
                                    print(f"{ticker}: Expected ${exp_buy}/${exp_sell}, Got ${actual_buy}/${actual_sell} - {'✓' if match else '✗'}")
                            
                        else:
                            print(f"OCR API Error: {response.status_code}")
                    else:
                        print(f"Failed to download image: {response.status_code}")
                    break


if __name__ == "__main__":
    asyncio.run(process_ideas_image())