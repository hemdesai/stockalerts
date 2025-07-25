"""
ETF email parser for ETF Pro Plus emails.
Handles both image extraction with OCR and direct table parsing.
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


def extract_etf_stocks(email_content: str) -> List[Dict[str, any]]:
    """
    Extract ETF data from ETF Pro Plus emails.
    
    Args:
        email_content: Raw email HTML content
        
    Returns:
        List of dictionaries with extracted ETF data
    """
    try:
        stocks = []
        soup = BeautifulSoup(email_content, 'html.parser')
        
        # First, try to extract from HTML tables (if present)
        stocks = extract_from_tables(soup)
        
        if not stocks:
            # If no table data, try to extract images for OCR processing
            logger.info("No table data found, attempting image extraction for OCR")
            image_data = extract_largest_image(soup, email_content)
            if image_data:
                stocks = process_image_with_ocr(image_data)
        
        logger.info(f"Total ETF stocks extracted: {len(stocks)}")
        return stocks
        
    except Exception as e:
        logger.error(f"Error parsing ETF email: {e}")
        return []


def extract_from_tables(soup: BeautifulSoup) -> List[Dict[str, any]]:
    """
    Try to extract ETF data from HTML tables.
    
    Args:
        soup: BeautifulSoup parsed HTML
        
    Returns:
        List of extracted ETF data
    """
    stocks = []
    
    # Look for tables that might contain ETF data
    tables = soup.find_all('table')
    logger.info(f"Found {len(tables)} tables in ETF email")
    
    for i, table in enumerate(tables):
        rows = table.find_all('tr')
        if not rows:
            continue
        
        # Check if this table has ETF-related headers
        header_cells = rows[0].find_all(['th', 'td'])
        header_text = ' '.join([cell.get_text(strip=True).upper() for cell in header_cells])
        
        # Look for ETF-specific headers
        if any(keyword in header_text for keyword in ['TICKER', 'ETF', 'TREND', 'BUY', 'SELL']):
            logger.info(f"Found potential ETF table at index {i}")
            
            # Find column indices
            ticker_idx = buy_idx = sell_idx = -1
            for j, cell in enumerate(header_cells):
                cell_text = cell.get_text(strip=True).upper()
                if 'TICKER' in cell_text:
                    ticker_idx = j
                elif 'BUY' in cell_text:
                    buy_idx = j
                elif 'SELL' in cell_text:
                    sell_idx = j
            
            if ticker_idx >= 0 and buy_idx >= 0 and sell_idx >= 0:
                # Process data rows
                for row in rows[1:]:  # Skip header
                    cells = row.find_all(['td', 'th'])
                    if len(cells) > max(ticker_idx, buy_idx, sell_idx):
                        try:
                            ticker = cells[ticker_idx].get_text(strip=True)
                            buy_text = cells[buy_idx].get_text(strip=True)
                            sell_text = cells[sell_idx].get_text(strip=True)
                            
                            # Clean and convert prices
                            buy_trade = clean_price(buy_text)
                            sell_trade = clean_price(sell_text)
                            
                            if ticker and buy_trade and sell_trade:
                                # Determine sentiment from ticker or other columns
                                sentiment = determine_etf_sentiment(ticker, row)
                                
                                stock = {
                                    "ticker": ticker,
                                    "sentiment": sentiment,
                                    "buy_trade": buy_trade,
                                    "sell_trade": sell_trade,
                                    "category": "etfs"
                                }
                                stocks.append(stock)
                                logger.info(f"Extracted ETF: {ticker} - Buy: {buy_trade}, Sell: {sell_trade}")
                        except Exception as e:
                            logger.error(f"Error parsing ETF table row: {e}")
    
    return stocks


def extract_largest_image(soup: BeautifulSoup, email_content: str) -> Optional[bytes]:
    """
    Extract the largest image from email (likely the ETF table).
    
    Args:
        soup: BeautifulSoup parsed HTML
        email_content: Raw email content
        
    Returns:
        Image data as bytes or None
    """
    try:
        largest_image_data = None
        largest_size = 0
        
        # Look for cloudfront.net images (common in ETF Pro Plus emails)
        cloudfront_images = []
        
        # Find in img tags
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if 'cloudfront.net' in src:
                cloudfront_images.append(src)
                logger.debug(f"Found cloudfront image: {src}")
        
        # Find in text using regex
        cloudfront_pattern = r'https?://[^"\'>\s]+cloudfront\.net[^"\'>\s]+'
        for url in re.findall(cloudfront_pattern, email_content):
            if url not in cloudfront_images:
                cloudfront_images.append(url)
                logger.debug(f"Found cloudfront URL in text: {url}")
        
        # Also look for "VIEW LARGER IMAGE" links
        for a in soup.find_all('a'):
            if 'VIEW LARGER IMAGE' in (a.text or '').upper():
                href = a.get('href')
                if href:
                    cloudfront_images.append(href)
                    logger.debug(f"Found VIEW LARGER IMAGE link: {href}")
        
        # Download and check each image
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        for img_url in cloudfront_images:
            try:
                logger.info(f"Downloading image: {img_url}")
                response = requests.get(img_url, headers=headers, timeout=15)
                if response.status_code == 200:
                    image_data = response.content
                    if len(image_data) > largest_size and len(image_data) > 10000:  # > 10KB
                        largest_size = len(image_data)
                        largest_image_data = image_data
                        logger.info(f"Found larger image, size: {len(image_data)} bytes")
            except Exception as e:
                logger.error(f"Error downloading image: {e}")
        
        return largest_image_data
        
    except Exception as e:
        logger.error(f"Error extracting images: {e}")
        return None


def process_image_with_ocr(image_data: bytes) -> List[Dict[str, any]]:
    """
    Process image using Mistral OCR API.
    
    Args:
        image_data: Image bytes
        
    Returns:
        List of extracted ETF data
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
        
        logger.info("Sending image to Mistral OCR API")
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
        
        # Parse the OCR markdown table
        return parse_ocr_markdown(ocr_text)
        
    except Exception as e:
        logger.error(f"Error processing image with OCR: {e}")
        return []


def parse_ocr_markdown(markdown_text: str) -> List[Dict[str, any]]:
    """
    Parse ETF data from OCR markdown output.
    
    Args:
        markdown_text: OCR output in markdown format
        
    Returns:
        List of extracted ETF data
    """
    stocks = []
    lines = [line.strip() for line in markdown_text.split('\n') if line.strip()]
    
    current_sentiment = "neutral"  # Default sentiment
    
    # Process each line to identify sections and data
    for i, line in enumerate(lines):
        # Check for section headers (handle OCR variations)
        line_upper = line.upper()
        if ('BULLISH' in line_upper or 'BULUSHI' in line_upper or 
            'BULL' in line_upper and ('ISH' in line_upper or 'USH' in line_upper)):
            current_sentiment = "bullish"
            logger.info(f"Found BULLISH section at line {i}: {line.strip()}")
            continue
        elif ('BEARISH' in line_upper or 'BEAVASH' in line_upper or 'BEARASH' in line_upper or
              'BEAR' in line_upper and ('ISH' in line_upper or 'ASH' in line_upper)):
            current_sentiment = "bearish" 
            logger.info(f"Found BEARISH section at line {i}: {line.strip()}")
            continue
        
        # Process data rows (lines with |)
        if line.startswith('|') and '|' in line:
            # Split into cells
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            
            if len(cells) >= 6:  # Need at least ticker, date, price, trend ranges
                try:
                    # Skip header rows
                    if any(header in cells[0].upper() for header in ['TICKER', 'BULLISH', 'BEARISH']):
                        continue
                    
                    # Extract ticker (column 1)
                    ticker = cells[1].strip() if len(cells) > 1 else cells[0].strip()
                    
                    # Skip if not a valid ticker
                    if not ticker or len(ticker) < 2 or len(ticker) > 6:
                        continue
                    
                    # Find trend ranges - usually columns 4 and 5 (buy and sell)
                    buy_trade = None
                    sell_trade = None
                    
                    # Look for prices in columns 4 and 5 (trend ranges)
                    if len(cells) >= 6:
                        buy_trade = clean_price(cells[4])  # First trend range price
                        sell_trade = clean_price(cells[5])  # Second trend range price
                    
                    if ticker and buy_trade and sell_trade:
                        stock = {
                            "ticker": ticker,
                            "sentiment": current_sentiment,
                            "buy_trade": buy_trade,
                            "sell_trade": sell_trade,
                            "category": "etfs"
                        }
                        stocks.append(stock)
                        logger.info(f"Parsed ETF from OCR: {ticker} ({current_sentiment}) - Buy: {buy_trade}, Sell: {sell_trade}")
                        
                except Exception as e:
                    logger.error(f"Error parsing OCR row: {line} - {e}")
    
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
    
    # Remove non-numeric characters except decimal point
    cleaned = re.sub(r'[^\d.-]', '', price_str)
    
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def determine_etf_sentiment(ticker: str, row_element) -> str:
    """
    Determine ETF sentiment from ticker name or row content.
    
    Args:
        ticker: ETF ticker symbol
        row_element: BeautifulSoup row element
        
    Returns:
        Sentiment string (bullish, bearish, or neutral)
    """
    # Check ticker for inverse/bear indicators
    ticker_upper = ticker.upper()
    if any(word in ticker_upper for word in ['BEAR', 'SHORT', 'INVERSE', 'SH', 'PSQ', 'DOG', 'DXD', 'SDS']):
        return "bearish"
    elif any(word in ticker_upper for word in ['BULL', 'LONG', 'TQQQ', 'SPXL', 'UPRO']):
        return "bullish"
    
    # Check row text for sentiment indicators
    row_text = row_element.get_text().lower() if row_element else ""
    if any(word in row_text for word in ['bear', 'short', 'inverse']):
        return "bearish"
    elif any(word in row_text for word in ['bull', 'long']):
        return "bullish"
    
    return "neutral"


def validate_etf_stocks(stocks: List[Dict[str, any]]) -> List[Dict[str, any]]:
    """
    Validate extracted ETF stock data.
    
    Args:
        stocks: List of extracted stocks
        
    Returns:
        List of validated stocks
    """
    validated = []
    
    for stock in stocks:
        # Validate ticker
        ticker = stock.get('ticker', '').strip()
        if not ticker or len(ticker) < 2 or len(ticker) > 6:
            logger.warning(f"Invalid ETF ticker: {ticker}")
            continue
        
        # Validate prices
        buy_trade = stock.get('buy_trade')
        sell_trade = stock.get('sell_trade')
        
        if buy_trade and sell_trade:
            # ETF prices should be reasonable
            if 0 < buy_trade < 10000 and 0 < sell_trade < 10000:
                validated.append(stock)
            else:
                logger.warning(f"Invalid prices for {ticker}: Buy={buy_trade}, Sell={sell_trade}")
        else:
            logger.warning(f"Missing prices for {ticker}")
    
    logger.info(f"Validated {len(validated)} out of {len(stocks)} ETF stocks")
    return validated