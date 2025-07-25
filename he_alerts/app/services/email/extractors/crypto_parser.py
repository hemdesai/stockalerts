"""
Crypto email parser for CRYPTO QUANT emails.
Handles embedded images with OCR for risk ranges extraction.
"""
import re
import base64
import requests
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
import structlog

from app.core.config import settings
from app.schemas.stock import StockCreate

logger = structlog.get_logger(__name__)


def extract_crypto_stocks(email_content: str) -> List[Dict[str, any]]:
    """
    Extract crypto data from CRYPTO QUANT emails.
    
    Args:
        email_content: Raw email HTML content
        
    Returns:
        List of dictionaries with extracted crypto data
    """
    try:
        stocks = []
        soup = BeautifulSoup(email_content, 'html.parser')
        
        # Look for embedded images containing crypto data
        logger.info("Looking for embedded crypto images in HTML")
        
        # Find all images in the email
        images_found = []
        for img in soup.find_all('img'):
            src = img.get('src', '')
            alt = img.get('alt', '')
            
            # Add all images, we'll check content with OCR
            if src and src.startswith('http'):
                images_found.append(src)
                logger.info(f"Found image: {src[:100]}...")
        
        # Also check for background images or other embedded images
        # Look for cloudfront/S3 URLs that might contain the data
        import re
        cloudfront_pattern = r'https?://[^"\'>]+\.cloudfront\.net[^"\'>]+\.(?:png|jpg|jpeg|gif)'
        s3_pattern = r'https?://[^"\'>]+\.s3[^"\'>]+\.(?:png|jpg|jpeg|gif)'
        
        for pattern in [cloudfront_pattern, s3_pattern]:
            for url in re.findall(pattern, email_content):
                if url not in images_found:
                    images_found.append(url)
                    logger.info(f"Found additional image URL: {url[:100]}...")
        
        # Process ALL images to find both risk ranges AND derivative exposures tables
        for img_url in images_found:
            try:
                logger.info(f"Downloading image for OCR: {img_url[:100]}...")
                
                # Download the image
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(img_url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    image_data = response.content
                    logger.info(f"Downloaded image: {len(image_data)} bytes")
                    
                    # Process with OCR - this will handle both table types
                    ocr_result = process_crypto_image_with_ocr(image_data)
                    if ocr_result:
                        stocks.extend(ocr_result)
                        logger.info(f"Successfully extracted {len(ocr_result)} items from image")
                else:
                    logger.warning(f"Failed to download image: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Error processing image {img_url[:50]}...: {e}")
                continue
        
        if not stocks:
            logger.warning("No crypto data extracted from images, trying fallback methods")
            # Could implement additional fallback methods here
        
        logger.info(f"Total crypto assets extracted: {len(stocks)}")
        return stocks
        
    except Exception as e:
        logger.error(f"Error parsing crypto email: {e}")
        return []


def process_crypto_image_with_ocr(image_data: bytes) -> List[Dict[str, any]]:
    """
    Process crypto image using Mistral OCR API.
    
    Args:
        image_data: Image bytes
        
    Returns:
        List of extracted crypto data
    """
    try:
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
        
        logger.info("Sending crypto image to Mistral OCR API")
        response = requests.post(
            "https://api.mistral.ai/v1/ocr",
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            logger.error(f"OCR API Error: {response.status_code} - {response.text}")
            return []
        
        ocr_data = response.json()
        ocr_text = ocr_data['pages'][0]['markdown']
        logger.info(f"OCR extracted {len(ocr_text)} characters")
        
        # Check if this is a risk ranges table
        if "HEDGEYE RISK RANGES" in ocr_text.upper() or "RISK RANGE" in ocr_text.upper():
            logger.info("Found Hedgeye Risk Ranges table")
            return parse_risk_ranges_table(ocr_text)
        # Check for derivative exposures table
        elif any(phrase in ocr_text.upper() for phrase in ["DERIVATIVE EXPOSURES", "DIRECT & DERIVATIVE", "IBIT", "MSTR"]):
            logger.info("Found Derivative Exposures table")
            return parse_derivative_exposures_table(ocr_text)
        else:
            logger.info("This image does not contain crypto data tables")
            return []
        
    except Exception as e:
        logger.error(f"Error processing crypto image with OCR: {e}")
        return []


def parse_risk_ranges_table(ocr_text: str) -> List[Dict[str, any]]:
    """
    Parse the Hedgeye Risk Ranges table from OCR text.
    
    Args:
        ocr_text: OCR output text
        
    Returns:
        List of extracted crypto data
    """
    stocks = []
    lines = ocr_text.split('\n')
    
    # Crypto ticker mappings
    ticker_mappings = {
        'BTC': 'BTC',
        'ETH': 'ETH',
        'SOL': 'SOL',
        'AVAX': 'AVAX',
        'AAVE': 'AAVE',
        'XRP': 'XRP',
        'ADA': 'ADA',
        'MATIC': 'MATIC',
        'DOT': 'DOT',
        'LINK': 'LINK'
    }
    
    try:
        # Find the start of the risk ranges table
        table_start = -1
        for i, line in enumerate(lines):
            if "HEDGEYE RISK RANGES" in line.upper():
                table_start = i
                logger.info(f"Found risk ranges header at line {i}")
                break
        
        if table_start == -1:
            logger.warning("Could not find HEDGEYE RISK RANGES header")
            return []
        
        # Process table rows
        current_sentiment = "neutral"  # Default sentiment
        
        for i in range(table_start + 1, len(lines)):
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Check for sentiment indicators
            if "BULLISH" in line.upper():
                current_sentiment = "bullish"
                logger.info("Found BULLISH sentiment indicator")
            elif "BEARISH" in line.upper():
                current_sentiment = "bearish"
                logger.info("Found BEARISH sentiment indicator")
            
            # Process data rows with pipe separators
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
                
                # Look for crypto ticker patterns
                for part in parts:
                    # Check if this part contains a known crypto ticker
                    for ticker in ticker_mappings:
                        if ticker in part.upper() and re.match(r'^[A-Z]{2,5}$', part.strip()):
                            # Found a ticker, now extract the prices
                            logger.info(f"Found ticker: {ticker}")
                            
                            # Extract all numbers from the line
                            numbers = re.findall(r'\$?([\d,]+\.?\d*)', line)
                            numbers = [float(n.replace(',', '')) for n in numbers if n]
                            
                            if len(numbers) >= 3:  # Need at least price, buy, sell
                                # Usually: current price, buy trade, sell trade
                                buy_trade = numbers[1] if len(numbers) > 1 else None
                                sell_trade = numbers[2] if len(numbers) > 2 else None
                                
                                if buy_trade and sell_trade:
                                    stock = {
                                        "ticker": ticker,
                                        "sentiment": current_sentiment,
                                        "buy_trade": buy_trade,
                                        "sell_trade": sell_trade,
                                        "category": "digitalassets"
                                    }
                                    stocks.append(stock)
                                    logger.info(f"Extracted {ticker}: Buy=${buy_trade}, Sell=${sell_trade}, Sentiment={current_sentiment}")
                            break
            
            # Alternative parsing for rows without pipes
            else:
                # Look for patterns like "BTC 80012 93968"
                parts = line.split()
                if len(parts) >= 3:
                    potential_ticker = parts[0].upper()
                    if potential_ticker in ticker_mappings:
                        try:
                            # Extract numbers
                            numbers = []
                            for part in parts[1:]:
                                cleaned = re.sub(r'[^\d.]', '', part)
                                if cleaned:
                                    numbers.append(float(cleaned))
                            
                            if len(numbers) >= 2:
                                buy_trade = numbers[0]
                                sell_trade = numbers[1]
                                
                                stock = {
                                    "ticker": potential_ticker,
                                    "sentiment": current_sentiment,
                                    "buy_trade": buy_trade,
                                    "sell_trade": sell_trade,
                                    "category": "digitalassets"
                                }
                                stocks.append(stock)
                                logger.info(f"Extracted {potential_ticker}: Buy=${buy_trade}, Sell=${sell_trade}")
                        except Exception as e:
                            logger.debug(f"Error parsing line: {line} - {e}")
        
        # If manual parsing didn't work well, try using Mistral AI assistance
        if len(stocks) < 3:  # Expecting at least BTC, ETH, SOL
            logger.info("Manual parsing found few assets, using Mistral AI assistance")
            ai_stocks = parse_with_mistral_assistance(ocr_text)
            if ai_stocks:
                # Merge or replace with AI results
                existing_tickers = {s['ticker'] for s in stocks}
                for ai_stock in ai_stocks:
                    if ai_stock['ticker'] not in existing_tickers:
                        stocks.append(ai_stock)
        
    except Exception as e:
        logger.error(f"Error parsing risk ranges table: {e}")
    
    return stocks


def parse_with_mistral_assistance(ocr_text: str) -> List[Dict[str, any]]:
    """
    Use Mistral AI to help parse the crypto table.
    
    Args:
        ocr_text: OCR text to parse
        
    Returns:
        List of extracted stocks
    """
    try:
        prompt = f"""
Below is the OCR output from a cryptocurrency risk ranges table. The table contains:
- Cryptocurrency tickers (BTC, ETH, SOL, AVAX, AAVE, etc.)
- Current prices
- Buy Trade levels
- Sell Trade levels
- Trend indicators (BULLISH/BEARISH)

Text from OCR:
<BEGIN_IMAGE_OCR>
{ocr_text}
</BEGIN_IMAGE_OCR>

Extract ALL cryptocurrencies from the table and return a JSON response with the following format:
{{
    "assets": [
        {{
            "ticker": "BTC",
            "sentiment": "bullish" or "bearish" or "neutral",
            "buy_trade": buy trade price as float,
            "sell_trade": sell trade price as float,
            "category": "digitalassets"
        }},
        ...
    ]
}}

Important:
- Extract the actual buy/sell trade levels from the "HEDGEYE RISK RANGES" section
- Use lowercase for sentiment: "bullish", "bearish", or "neutral"
- Return numeric values as floats without commas or dollar signs
- Only include crypto assets with valid buy and sell prices
- Return ONLY the JSON object, no other text
"""

        headers = {
            "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "mistral-large-latest",
            "messages": [{"role": "user", "content": prompt}]
        }
        
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            chat_data = response.json()
            response_content = chat_data["choices"][0]["message"]["content"]
            
            # Extract JSON from response
            import json
            try:
                crypto_data = json.loads(response_content)
                return crypto_data.get("assets", [])
            except json.JSONDecodeError:
                # Try to find JSON in the response
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    crypto_data = json.loads(json_match.group(0))
                    return crypto_data.get("assets", [])
        
    except Exception as e:
        logger.error(f"Error using Mistral AI for crypto parsing: {e}")
    
    return []


def parse_derivative_exposures_table(ocr_text: str) -> List[Dict[str, any]]:
    """
    Parse the Derivative Exposures table from OCR text.
    This table contains crypto-related stocks like IBIT, MSTR, MARA, RIOT, etc.
    
    Args:
        ocr_text: OCR output text
        
    Returns:
        List of extracted crypto-related stock data
    """
    stocks = []
    lines = ocr_text.split('\n')
    
    try:
        # Find the table header
        header_found = False
        in_table = False
        
        for i, line in enumerate(lines):
            line_upper = line.upper()
            
            # Look for table header
            if "DIRECT & DERIVATIVE EXPOSURES" in line_upper or "RISK RANGE & TREND SIGNAL" in line_upper:
                header_found = True
                logger.info(f"Found derivative exposures header at line {i}: {line}")
                continue
            
            # Look for column headers
            if header_found and ("TICKER" in line_upper or ("BUY TRADE" in line_upper and "SELL TRADE" in line_upper)):
                in_table = True
                logger.info(f"Found table columns at line {i}")
                continue
            
            if not in_table:
                continue
            
            # Skip empty lines
            if not line.strip():
                continue
                
            # End of table detection
            if in_table and ("---" in line or "___" in line or len(line.strip()) < 3):
                # Might be end of table
                if len(stocks) > 0:  # If we already found some stocks, stop
                    break
            
            # Parse data rows - look for lines with multiple values separated by spaces or pipes
            parts = []
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
            else:
                # Split by multiple spaces
                parts = line.split()
            
            if len(parts) >= 4:  # Need at least ticker, price, buy, sell
                potential_ticker = parts[0].strip().upper()
                
                # Validate ticker - should be 3-5 uppercase letters
                if re.match(r'^[A-Z]{3,5}$', potential_ticker):
                    try:
                        # Extract numeric values from remaining parts
                        numbers = []
                        for part in parts[1:]:
                            # Remove dollar signs, commas, percentages
                            cleaned = re.sub(r'[$,%]', '', part)
                            try:
                                num = float(cleaned)
                                numbers.append(num)
                            except:
                                continue
                        
                        if len(numbers) >= 3:  # Need at least price, buy, sell
                            # Usually: current price, buy trade, sell trade
                            price = numbers[0]
                            buy_trade = numbers[1]
                            sell_trade = numbers[2]
                            
                            # Determine sentiment from the line or trend signal column
                            sentiment = "neutral"
                            if "BULLISH" in line_upper:
                                sentiment = "bullish"
                            elif "BEARISH" in line_upper:
                                sentiment = "bearish"
                            
                            stock = {
                                "ticker": potential_ticker,
                                "sentiment": sentiment,
                                "buy_trade": buy_trade,
                                "sell_trade": sell_trade,
                                "category": "digitalassets"
                            }
                            stocks.append(stock)
                            logger.info(f"Extracted {potential_ticker}: Price=${price}, Buy=${buy_trade}, Sell=${sell_trade}, Sentiment={sentiment}")
                            
                    except Exception as e:
                        logger.debug(f"Error parsing line '{line}': {e}")
        
        # If no stocks found, try more flexible parsing
        if len(stocks) == 0:
            logger.info("No stocks found with strict parsing, trying flexible approach")
            # Look for any line with a valid ticker and numbers
            for line in lines:
                # Common crypto stock tickers
                crypto_stock_tickers = ['IBIT', 'MSTR', 'MARA', 'RIOT', 'ETHA', 'BLOK', 'COIN', 'BITO', 
                                       'ARKB', 'BTCO', 'FBTC', 'GBTC', 'BITF', 'HUT', 'CLSK']
                
                for ticker in crypto_stock_tickers:
                    if ticker in line.upper():
                        # Extract numbers from this line
                        numbers = re.findall(r'\$?([\d,]+\.?\d*)', line)
                        if len(numbers) >= 3:
                            try:
                                buy_trade = float(numbers[1].replace(',', ''))
                                sell_trade = float(numbers[2].replace(',', ''))
                                
                                sentiment = "bullish" if "BULLISH" in line.upper() else "bearish" if "BEARISH" in line.upper() else "neutral"
                                
                                stock = {
                                    "ticker": ticker,
                                    "sentiment": sentiment,
                                    "buy_trade": buy_trade,
                                    "sell_trade": sell_trade,
                                    "category": "digitalassets"
                                }
                                stocks.append(stock)
                                logger.info(f"Flexibly extracted {ticker}: Buy=${buy_trade}, Sell=${sell_trade}")
                                break
                            except:
                                continue
        
        logger.info(f"Total derivative exposures extracted: {len(stocks)}")
        
    except Exception as e:
        logger.error(f"Error parsing derivative exposures table: {e}")
    
    return stocks


def parse_derivative_with_mistral(ocr_text: str) -> List[Dict[str, any]]:
    """
    Use Mistral AI to help parse the derivative exposures table.
    
    Args:
        ocr_text: OCR text to parse
        
    Returns:
        List of extracted stocks
    """
    try:
        prompt = f"""
Below is the OCR output from a "DIRECT & DERIVATIVE EXPOSURES" table containing crypto-related stocks. The table has:
- Stock tickers (IBIT, MSTR, MARA, RIOT, COIN, etc.)
- Current prices
- Buy Trade levels
- Sell Trade levels
- Trend signals (BULLISH/BEARISH)

Text from OCR:
<BEGIN_IMAGE_OCR>
{ocr_text}
</BEGIN_IMAGE_OCR>

Extract ALL crypto-related stocks from the table and return a JSON response with the following format:
{{
    "assets": [
        {{
            "ticker": "IBIT",
            "sentiment": "bullish" or "bearish" or "neutral",
            "buy_trade": buy trade price as float,
            "sell_trade": sell trade price as float,
            "category": "digitalassets"
        }},
        ...
    ]
}}

Important:
- The first row might be missing the ticker - it should be "IBIT"
- These are crypto-related STOCKS (not pure cryptocurrencies)
- Use lowercase for sentiment: "bullish", "bearish", or "neutral"
- Return numeric values as floats without commas or dollar signs
- Only include stocks with valid buy and sell prices
- Return ONLY the JSON object, no other text
"""

        headers = {
            "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "mistral-large-latest",
            "messages": [{"role": "user", "content": prompt}]
        }
        
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            chat_data = response.json()
            response_content = chat_data["choices"][0]["message"]["content"]
            
            # Extract JSON from response
            import json
            try:
                crypto_data = json.loads(response_content)
                return crypto_data.get("assets", [])
            except json.JSONDecodeError:
                # Try to find JSON in the response
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    crypto_data = json.loads(json_match.group(0))
                    return crypto_data.get("assets", [])
        
    except Exception as e:
        logger.error(f"Error using Mistral AI for derivative exposures parsing: {e}")
    
    return []


def validate_crypto_stocks(stocks: List[Dict[str, any]]) -> List[Dict[str, any]]:
    """
    Validate extracted crypto stock data.
    
    Args:
        stocks: List of extracted stocks
        
    Returns:
        List of validated stocks
    """
    validated = []
    
    for stock in stocks:
        # Validate ticker
        ticker = stock.get('ticker', '').strip().upper()
        if not ticker or len(ticker) < 2 or len(ticker) > 5:
            logger.warning(f"Invalid crypto ticker: {ticker}")
            continue
        
        # Validate prices
        buy_trade = stock.get('buy_trade')
        sell_trade = stock.get('sell_trade')
        
        if buy_trade and sell_trade:
            # Crypto prices can vary widely
            if buy_trade > 0 and sell_trade > 0:
                # Ensure buy < sell for normal trading ranges
                if buy_trade > sell_trade:
                    logger.warning(f"Buy price > Sell price for {ticker}, swapping")
                    buy_trade, sell_trade = sell_trade, buy_trade
                    stock['buy_trade'] = buy_trade
                    stock['sell_trade'] = sell_trade
                
                validated.append(stock)
            else:
                logger.warning(f"Invalid prices for {ticker}: Buy={buy_trade}, Sell={sell_trade}")
        else:
            logger.warning(f"Missing prices for {ticker}")
    
    logger.info(f"Validated {len(validated)} out of {len(stocks)} crypto stocks")
    return validated