"""
Ideas email parser for Investing Ideas Newsletter.
Handles PNG attachments with Longs/Shorts tables using OCR.
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


def extract_ideas_stocks(email_content: str, attachments: List[Dict[str, Any]]) -> List[Dict[str, any]]:
    """
    Extract ideas data from Investing Ideas Newsletter emails.
    
    Args:
        email_content: Raw email HTML content
        attachments: List of email attachments
        
    Returns:
        List of dictionaries with extracted ideas data
    """
    try:
        stocks = []
        
        # First, check for PNG attachments
        png_attachments = [att for att in attachments if att.get('filename', '').lower().endswith('.png')]
        
        if png_attachments:
            # Process the first PNG attachment
            logger.info(f"Found {len(png_attachments)} PNG attachments in ideas email")
            attachment = png_attachments[0]
            
            # Get the attachment data
            image_data = attachment.get('data')
            if image_data:
                stocks = process_ideas_image_with_ocr(image_data)
        else:
            logger.info("No PNG attachments found, checking for embedded images in HTML")
            # Try to extract image from HTML body
            soup = BeautifulSoup(email_content, 'html.parser')
            
            # Look for cloudfront images (common in newsletter emails)
            image_extracted = False
            for img in soup.find_all('img'):
                src = img.get('src', '')
                # Look for screenshot images (not headers)
                if 'Screenshot' in src and 'cloudfront.net' in src:
                    logger.info(f"Found embedded IDEAS image: {src}")
                    
                    # Download the image
                    try:
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        }
                        response = requests.get(src, headers=headers, timeout=15)
                        if response.status_code == 200:
                            image_data = response.content
                            logger.info(f"Downloaded embedded image: {len(image_data)} bytes")
                            stocks = process_ideas_image_with_ocr(image_data)
                            image_extracted = True
                            break
                    except Exception as e:
                        logger.error(f"Error downloading embedded image: {e}")
            
            if not image_extracted:
                logger.info("No embedded images found, attempting to extract from HTML tables")
                stocks = extract_from_tables(soup)
        
        logger.info(f"Total ideas stocks extracted: {len(stocks)}")
        return stocks
        
    except Exception as e:
        logger.error(f"Error parsing ideas email: {e}")
        return []


def process_ideas_image_with_ocr(image_data: bytes) -> List[Dict[str, any]]:
    """
    Process ideas image using Mistral OCR API.
    
    Args:
        image_data: Image bytes
        
    Returns:
        List of extracted ideas data
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
        
        logger.info("Sending ideas image to Mistral OCR API")
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
        logger.info(f"OCR extracted {len(ocr_text)} characters from ideas image")
        
        # Parse the OCR text for Longs and Shorts
        return parse_ideas_ocr_text(ocr_text)
        
    except Exception as e:
        logger.error(f"Error processing ideas image with OCR: {e}")
        return []


def parse_ideas_ocr_text(ocr_text: str) -> List[Dict[str, any]]:
    """
    Parse ideas data from OCR text with Longs and Shorts sections.
    
    Args:
        ocr_text: OCR output text
        
    Returns:
        List of extracted ideas data
    """
    stocks = []
    
    try:
        # Split into Longs and Shorts sections
        sections = re.split(r'(?:# )?Shorts', ocr_text, flags=re.IGNORECASE)
        
        if len(sections) >= 2:
            longs_section = sections[0]
            shorts_section = sections[1] if len(sections) > 1 else ""
        else:
            # Try alternative split
            longs_match = re.search(r'(?:# )?Longs', ocr_text, re.IGNORECASE)
            shorts_match = re.search(r'(?:# )?Shorts', ocr_text, re.IGNORECASE)
            
            if longs_match and shorts_match:
                longs_section = ocr_text[longs_match.end():shorts_match.start()]
                shorts_section = ocr_text[shorts_match.end():]
            else:
                longs_section = ocr_text
                shorts_section = ""
        
        # Parse Longs (BULLISH)
        logger.info("Parsing LONGS section for bullish stocks")
        longs_stocks = parse_section(longs_section, "bullish")
        stocks.extend(longs_stocks)
        
        # Parse Shorts (BEARISH)
        logger.info("Parsing SHORTS section for bearish stocks")
        shorts_stocks = parse_section(shorts_section, "bearish")
        stocks.extend(shorts_stocks)
        
        # Only use Mistral AI assistance if manual parsing found nothing at all
        if len(stocks) == 0:
            logger.info("Manual parsing found no stocks, using Mistral AI for assistance")
            fallback_stocks = parse_with_mistral_assistance(ocr_text)
            if fallback_stocks:
                stocks = fallback_stocks
        
    except Exception as e:
        logger.error(f"Error parsing ideas OCR text: {e}")
    
    return stocks


def parse_section(section_text: str, sentiment: str) -> List[Dict[str, any]]:
    """
    Parse a section (Longs or Shorts) to extract stock data.
    
    Args:
        section_text: Text of the section
        sentiment: "bullish" or "bearish"
        
    Returns:
        List of extracted stocks
    """
    stocks = []
    lines = section_text.strip().split('\n')
    
    for line in lines:
        if '|' in line:
            parts = [p.strip() for p in line.split('|')]
            parts = [p for p in parts if p]  # Remove empty parts
            
            if len(parts) >= 3:
                try:
                    # Extract ticker (usually first column after removing empty parts)
                    ticker = parts[0].strip()
                    
                    # Skip headers and invalid tickers
                    if (ticker.lower() in ['stock', 'ticker', '-----', '', 'longs', 'shorts'] or 
                        'closing' in ticker.lower() or 
                        'trend' in ticker.lower() or
                        'price' in ticker.lower() or
                        not re.match(r'^[A-Z]{2,5}$', ticker)):  # Changed to 2-5 letters
                        continue
                    
                    # Extract trend ranges from parts[2:] (skip closing price)
                    trend_parts = []
                    for part in parts[2:]:
                        if '$' in part or any(c.isdigit() for c in part):
                            trend_parts.append(part)
                    
                    if len(trend_parts) >= 2:
                        # Clean up and convert to float
                        buy_str = trend_parts[0].replace('$', '').replace(',', '').strip()
                        sell_str = trend_parts[1].replace('$', '').replace(',', '').strip()
                        
                        # Extract just the numeric part
                        buy_match = re.search(r'([\d\.]+)', buy_str)
                        sell_match = re.search(r'([\d\.]+)', sell_str)
                        
                        if buy_match and sell_match:
                            buy_trade = float(buy_match.group(1))
                            sell_trade = float(sell_match.group(1))
                            
                            stock = {
                                "ticker": ticker,
                                "sentiment": sentiment,
                                "buy_trade": buy_trade,
                                "sell_trade": sell_trade,
                                "category": "ideas"
                            }
                            stocks.append(stock)
                            logger.info(f"Extracted {sentiment} idea: {ticker} - Buy: {buy_trade}, Sell: {sell_trade}")
                        
                except Exception as e:
                    logger.debug(f"Error parsing line in {sentiment} section: {line} - {e}")
    
    # Try alternative pattern matching if we didn't get enough stocks
    if len(stocks) < 2:
        # Pattern: TICKER | $150.67 | $144.00 | $175.00
        pattern = r'([A-Z]{1,5})\s*\|\s*\$?([\d,]+\.?\d*)\s*\|\s*\$?([\d,]+\.?\d*)\s*\|\s*\$?([\d,]+\.?\d*)'
        matches = re.findall(pattern, section_text)
        
        for match in matches:
            ticker = match[0].strip()
            if re.match(r'^[A-Z]{1,5}$', ticker) and not any(s['ticker'] == ticker for s in stocks):
                try:
                    buy_trade = float(match[2].replace(',', ''))
                    sell_trade = float(match[3].replace(',', ''))
                    
                    stock = {
                        "ticker": ticker,
                        "sentiment": sentiment,
                        "buy_trade": buy_trade,
                        "sell_trade": sell_trade,
                        "category": "ideas"
                    }
                    stocks.append(stock)
                    logger.info(f"Alt pattern extracted {sentiment} idea: {ticker} - Buy: {buy_trade}, Sell: {sell_trade}")
                except Exception as e:
                    logger.debug(f"Error in alternative parsing for {ticker}: {e}")
        
        # Try third approach with more relaxed pattern matching if we still don't have enough assets
        if len(stocks) < 3:
            logger.info("Trying third parsing approach with more relaxed pattern matching...")
            # Look for ticker-like patterns (1-5 uppercase letters) followed by numbers
            ticker_pattern = r'\b([A-Z]{1,5})\b'
            ticker_matches = re.findall(ticker_pattern, section_text)
            
            # Process each potential ticker
            for ticker in ticker_matches:
                # Skip if we already have this ticker
                if any(s['ticker'] == ticker for s in stocks):
                    continue
                
                # Validate ticker format (1-5 uppercase letters)
                if not re.match(r'^[A-Z]{1,5}$', ticker):
                    continue
                
                # Look for numbers near this ticker
                ticker_pos = section_text.find(ticker)
                if ticker_pos != -1:
                    # Look for numbers in the next 100 characters
                    context = section_text[ticker_pos:ticker_pos + 100]
                    # Find all numbers in this context
                    number_pattern = r'\$?([\d\.,]+)'
                    number_matches = re.findall(number_pattern, context)
                    
                    if len(number_matches) >= 2:
                        try:
                            # Find buy and sell prices (skip closing price if present)
                            suitable_prices = []
                            for num_str in number_matches:
                                price = float(num_str.replace(',', ''))
                                if 1 < price < 50000:  # Reasonable stock prices
                                    suitable_prices.append(price)
                            
                            if len(suitable_prices) >= 2:
                                # Usually the trend range is buy/sell
                                buy_trade = suitable_prices[-2]  # Second to last
                                sell_trade = suitable_prices[-1]  # Last
                                
                                stock = {
                                    "ticker": ticker,
                                    "sentiment": sentiment,
                                    "buy_trade": buy_trade,
                                    "sell_trade": sell_trade,
                                    "category": "ideas"
                                }
                                stocks.append(stock)
                                logger.info(f"Third method extracted {sentiment} idea: {ticker} - Buy: {buy_trade}, Sell: {sell_trade}")
                        except Exception as e:
                            logger.debug(f"Error in third parsing approach for {ticker}: {e}")
    
    return stocks


def parse_with_mistral_assistance(ocr_text: str) -> List[Dict[str, any]]:
    """
    Use Mistral AI to help parse the ideas table.
    
    Args:
        ocr_text: OCR text to parse
        
    Returns:
        List of extracted stocks
    """
    try:
        prompt = f"""
Below is the OCR output in markdown format from a stock ideas table image. The table is split into two sections: 'Longs' (BULLISH stocks) and 'Shorts' (BEARISH stocks).
Each row in the table contains:
- Stock ticker (e.g., AAPL, MSFT)
- Closing price
- Buy Trade price
- Sell Trade price
- Other information like upside/downside percentages
Text from OCR:
<BEGIN_IMAGE_OCR>
{ocr_text}
<END_IMAGE_OCR>
I need you to carefully extract ALL stock tickers from BOTH the Longs and Shorts sections, along with their corresponding Buy Trade and Sell Trade values.
Extract the actual values from the OCR text. DO NOT use any hardcoded values or make up data.
Convert this into a structured JSON response with the following format:
{{
    "assets": [
        {{
            "ticker": "AAPL",
            "sentiment": "bullish" if in Longs section, "bearish" if in Shorts section,
            "buy_trade": extracted buy trade value as float,
            "sell_trade": extracted sell trade value as float,
            "category": "ideas"
        }},
        ...
    ]
}}
Rules:
- Include ALL stocks found in the OCR text
- Set sentiment to "bullish" for stocks in the Longs section and "bearish" for stocks in the Shorts section
- Format numbers as floats without commas (e.g., 150.67, not $150.67)
- Set category to "ideas" for all stocks
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
            
            # Try to extract JSON from response with better error handling
            import json
            try:
                ideas_data = json.loads(response_content)
                return ideas_data.get("assets", [])
            except json.JSONDecodeError:
                # Try to find JSON in the response
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    ideas_data = json.loads(json_match.group(0))
                    return ideas_data.get("assets", [])
        
    except Exception as e:
        logger.error(f"Error using Mistral AI for ideas parsing: {e}")
    
    return []


def extract_from_tables(soup: BeautifulSoup) -> List[Dict[str, any]]:
    """
    Try to extract ideas data from HTML tables.
    
    Args:
        soup: BeautifulSoup parsed HTML
        
    Returns:
        List of extracted ideas data
    """
    stocks = []
    
    # Look for tables that might contain ideas data
    tables = soup.find_all('table')
    
    for table in tables:
        # Look for Longs/Shorts indicators
        table_text = table.get_text()
        has_longs = 'longs' in table_text.lower()
        has_shorts = 'shorts' in table_text.lower()
        
        if has_longs or has_shorts:
            rows = table.find_all('tr')
            current_section = "bullish" if has_longs else "bearish"
            
            for row in rows:
                # Check if this row indicates a section change
                row_text = row.get_text().lower()
                if 'shorts' in row_text:
                    current_section = "bearish"
                elif 'longs' in row_text:
                    current_section = "bullish"
                
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 4:  # Need ticker, close, buy, sell
                    try:
                        ticker = cells[0].get_text(strip=True)
                        if re.match(r'^[A-Z]{1,5}$', ticker):
                            buy_text = cells[2].get_text(strip=True)
                            sell_text = cells[3].get_text(strip=True)
                            
                            buy_trade = clean_price(buy_text)
                            sell_trade = clean_price(sell_text)
                            
                            if buy_trade and sell_trade:
                                stock = {
                                    "ticker": ticker,
                                    "sentiment": current_section,
                                    "buy_trade": buy_trade,
                                    "sell_trade": sell_trade,
                                    "category": "ideas"
                                }
                                stocks.append(stock)
                                logger.info(f"Extracted {current_section} idea from table: {ticker}")
                    except Exception as e:
                        logger.debug(f"Error parsing table row: {e}")
    
    return stocks


def clean_price(price_str: str) -> Optional[float]:
    """
    Clean and convert price string to float.
    
    Args:
        price_str: Price string
        
    Returns:
        Float price or None
    """
    if not price_str:
        return None
    
    # Remove $ and commas, extract numeric value
    price_match = re.search(r'([\d,]+\.?\d*)', price_str)
    if price_match:
        try:
            return float(price_match.group(1).replace(',', ''))
        except ValueError:
            return None
    return None


def validate_ideas_stocks(stocks: List[Dict[str, any]]) -> List[Dict[str, any]]:
    """
    Validate extracted ideas stock data.
    
    Args:
        stocks: List of extracted stocks
        
    Returns:
        List of validated stocks
    """
    validated = []
    
    for stock in stocks:
        # Validate ticker
        ticker = stock.get('ticker', '').strip()
        if not ticker or len(ticker) < 1 or len(ticker) > 5:
            logger.warning(f"Invalid ideas ticker: {ticker}")
            continue
        
        # Validate sentiment
        sentiment = stock.get('sentiment', '').lower()
        if sentiment not in ['bullish', 'bearish']:
            logger.warning(f"Invalid sentiment for {ticker}: {sentiment}")
            continue
        
        # Validate prices
        buy_trade = stock.get('buy_trade')
        sell_trade = stock.get('sell_trade')
        
        if buy_trade and sell_trade:
            # Ideas stock prices should be reasonable
            if 0 < buy_trade < 50000 and 0 < sell_trade < 50000:
                validated.append(stock)
            else:
                logger.warning(f"Invalid prices for {ticker}: Buy={buy_trade}, Sell={sell_trade}")
        else:
            logger.warning(f"Missing prices for {ticker}")
    
    logger.info(f"Validated {len(validated)} out of {len(stocks)} ideas stocks")
    return validated