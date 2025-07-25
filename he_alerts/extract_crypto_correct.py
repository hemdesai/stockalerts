"""
Extract crypto data from the correct images.
"""
import asyncio
import requests
import base64
import re
from app.services.email.gmail_client import GmailClient
from app.core.config import settings
from bs4 import BeautifulSoup

async def extract_crypto_data():
    """Extract crypto data from the specific images."""
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
    
    # Target images based on our findings
    # Image 6 (index 5) - HEDGEYE RISK RANGES
    # Image 14 (index 13) - DERIVATIVE EXPOSURES
    
    all_stocks = []
    
    # Extract from HEDGEYE RISK RANGES (image 6)
    if len(images) > 5:
        print("\nExtracting HEDGEYE RISK RANGES (cryptocurrencies)...")
        src = images[5].get('src', '')
        cryptos = await extract_from_image(src, "crypto")
        all_stocks.extend(cryptos)
    
    # Extract from DERIVATIVE EXPOSURES (image 14)
    if len(images) > 13:
        print("\nExtracting DERIVATIVE EXPOSURES (crypto stocks)...")
        src = images[13].get('src', '')
        stocks = await extract_from_image(src, "derivative")
        all_stocks.extend(stocks)
    
    # Display results
    print(f"\n{'='*80}")
    print("EXTRACTION RESULTS")
    print('='*80)
    
    # Separate cryptos and stocks
    cryptos = [s for s in all_stocks if s['ticker'] in ['BTC', 'ETH', 'SOL', 'AVAX', 'AAVE']]
    stocks = [s for s in all_stocks if s['ticker'] not in ['BTC', 'ETH', 'SOL', 'AVAX', 'AAVE']]
    
    if cryptos:
        print("\nCRYPTOCURRENCIES:")
        print(f"{'Ticker':8} {'Sentiment':10} {'Buy':>12} {'Sell':>12}")
        print("-"*50)
        for item in sorted(cryptos, key=lambda x: x['ticker']):
            print(f"{item['ticker']:8} {item['sentiment']:10} ${item['buy_trade']:>11.2f} ${item['sell_trade']:>11.2f}")
    
    if stocks:
        print("\nCRYPTO STOCKS:")
        print(f"{'Ticker':8} {'Sentiment':10} {'Buy':>12} {'Sell':>12}")
        print("-"*50)
        for item in sorted(stocks, key=lambda x: x['ticker']):
            print(f"{item['ticker']:8} {item['sentiment']:10} ${item['buy_trade']:>11.2f} ${item['sell_trade']:>11.2f}")
    
    return all_stocks


async def extract_from_image(image_url: str, table_type: str):
    """Extract data from a specific image."""
    try:
        # Download image
        response = requests.get(image_url, timeout=30)
        if response.status_code != 200:
            print(f"Failed to download image")
            return []
        
        image_data = response.content
        print(f"Downloaded image: {len(image_data)} bytes")
        
        # OCR the image
        ocr_text = await ocr_full_image(image_data, table_type)
        
        if not ocr_text:
            return []
        
        # Parse based on table type
        if table_type == "crypto":
            return parse_crypto_table(ocr_text)
        else:
            return parse_derivative_table(ocr_text)
            
    except Exception as e:
        print(f"Error extracting from image: {e}")
        return []


async def ocr_full_image(image_data: bytes, table_type: str) -> str:
    """OCR the full image to extract table data."""
    try:
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        headers = {
            "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        if table_type == "crypto":
            prompt = """Extract the HEDGEYE RISK RANGES table data. 
For each cryptocurrency (BTC, ETH, SOL, AVAX, AAVE), extract:
- Ticker symbol
- Current price
- Buy Trade price
- Sell Trade price
- Trend (BULLISH/BEARISH/NEUTRAL)

Format each row as: TICKER | PRICE | BUY_TRADE | SELL_TRADE | TREND"""
        else:
            prompt = """Extract the DIRECT & DERIVATIVE EXPOSURES table data.
For each stock (IBIT, MSTR, MARA, RIOT, COIN, BITO, ETHA, BLOK), extract:
- Ticker symbol
- Current price
- Buy Trade price
- Sell Trade price
- Trend (BULLISH/BEARISH/NEUTRAL)

Format each row as: TICKER | PRICE | BUY_TRADE | SELL_TRADE | TREND"""
        
        payload = {
            "model": "pixtral-12b-2409",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                ]
            }],
            "max_tokens": 1000
        }
        
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            ocr_text = response.json()['choices'][0]['message']['content']
            print(f"OCR Result:\n{ocr_text}")
            return ocr_text
        else:
            print(f"OCR failed: {response.status_code}")
            return ""
            
    except Exception as e:
        print(f"OCR error: {e}")
        return ""


def parse_crypto_table(ocr_text: str):
    """Parse the crypto HEDGEYE RISK RANGES table."""
    stocks = []
    lines = ocr_text.split('\n')
    
    for line in lines:
        # Skip headers and empty lines
        if not line.strip() or 'extracted data' in line.lower():
            continue
            
        # Look for lines with dashes at the start (formatted output)
        if line.strip().startswith('-'):
            line = line.strip()[1:].strip()  # Remove leading dash
            
        # Look for lines with pipe separators
        if '|' in line:
            parts = [p.strip() for p in line.split('|')]
            
            if len(parts) >= 5:
                ticker = parts[0].upper()
                
                # Only process known crypto tickers
                if ticker in ['BTC', 'ETH', 'SOL', 'AVAX', 'AAVE']:
                    try:
                        # Extract prices (handle commas in numbers)
                        buy_price = float(parts[2].replace(',', ''))
                        sell_price = float(parts[3].replace(',', ''))
                        
                        # Extract sentiment
                        sentiment = "neutral"
                        trend = parts[4].upper() if len(parts) > 4 else ""
                        if "BULLISH" in trend:
                            sentiment = "bullish"
                        elif "BEARISH" in trend:
                            sentiment = "bearish"
                        
                        stocks.append({
                            "ticker": ticker,
                            "sentiment": sentiment,
                            "buy_trade": buy_price,
                            "sell_trade": sell_price,
                            "category": "digitalassets"
                        })
                        print(f"  Parsed {ticker}: Buy=${buy_price:,.2f}, Sell=${sell_price:,.2f}, {sentiment}")
                        
                    except Exception as e:
                        print(f"  Error parsing {ticker}: {e}")
    
    return stocks


def parse_derivative_table(ocr_text: str):
    """Parse the DERIVATIVE EXPOSURES table."""
    stocks = []
    lines = ocr_text.split('\n')
    
    for line in lines:
        # Skip headers and empty lines
        if not line.strip() or 'formatted as' in line.lower():
            continue
            
        # Look for lines with dashes at the start (formatted output)
        if line.strip().startswith('-'):
            line = line.strip()[1:].strip()  # Remove leading dash
            
        # Look for lines with pipe separators
        if '|' in line:
            parts = [p.strip() for p in line.split('|')]
            
            if len(parts) >= 5:
                ticker = parts[0].upper()
                
                # Only process known crypto stock tickers
                if ticker in ['IBIT', 'MSTR', 'MARA', 'RIOT', 'COIN', 'BITO', 'ETHA', 'BLOK']:
                    try:
                        # Extract prices (handle commas)
                        buy_price = float(parts[2].replace(',', ''))
                        sell_price = float(parts[3].replace(',', ''))
                        
                        # Extract sentiment
                        sentiment = "neutral"
                        trend = parts[4].upper() if len(parts) > 4 else ""
                        if "BULLISH" in trend:
                            sentiment = "bullish"
                        elif "BEARISH" in trend:
                            sentiment = "bearish"
                        
                        stocks.append({
                            "ticker": ticker,
                            "sentiment": sentiment,
                            "buy_trade": buy_price,
                            "sell_trade": sell_price,
                            "category": "digitalassets"
                        })
                        print(f"  Parsed {ticker}: Buy=${buy_price:.2f}, Sell=${sell_price:.2f}, {sentiment}")
                        
                    except Exception as e:
                        print(f"  Error parsing {ticker}: {e}")
    
    return stocks


if __name__ == "__main__":
    asyncio.run(extract_crypto_data())