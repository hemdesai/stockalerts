"""
Improved crypto parser that specifically looks for the two target tables.
"""
import re
import base64
import requests
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def extract_crypto_data(html_content: str) -> List[Dict[str, Any]]:
    """
    Extract crypto data by finding and OCR'ing specific tables.
    
    Looks for:
    1. HEDGEYE RISK RANGES* (for cryptocurrencies)
    2. DIRECT & DERIVATIVE EXPOSURES: RISK RANGE & TREND SIGNAL (for crypto stocks)
    
    Args:
        html_content: HTML content of the email
        
    Returns:
        List of extracted crypto and crypto stock data
    """
    all_stocks = []
    
    try:
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all images
        images = soup.find_all('img')
        logger.info(f"Found {len(images)} images in email")
        
        # Track which tables we've found
        found_crypto_table = False
        found_derivative_table = False
        
        # Process each image
        for idx, img in enumerate(images):
            if found_crypto_table and found_derivative_table:
                logger.info("Found both tables, stopping image processing")
                break
                
            src = img.get('src', '')
            if not src:
                continue
            
            # Download and OCR the image
            logger.info(f"Processing image {idx + 1}/{len(images)}: {src[:100]}...")
            
            try:
                # Download image
                response = requests.get(src, timeout=30)
                if response.status_code != 200:
                    continue
                
                image_data = response.content
                logger.info(f"Downloaded image: {len(image_data)} bytes")
                
                # OCR the image
                ocr_text = ocr_image_with_mistral(image_data)
                
                if not ocr_text:
                    continue
                
                # Check if this image contains our target tables
                ocr_upper = ocr_text.upper()
                
                # Check for crypto table
                if not found_crypto_table and "HEDGEYE RISK RANGES" in ocr_upper:
                    logger.info("Found HEDGEYE RISK RANGES table!")
                    crypto_stocks = parse_crypto_risk_ranges(ocr_text)
                    if crypto_stocks:
                        all_stocks.extend(crypto_stocks)
                        found_crypto_table = True
                        logger.info(f"Extracted {len(crypto_stocks)} cryptocurrencies")
                
                # Check for derivative exposures table
                if not found_derivative_table and (
                    "DIRECT & DERIVATIVE EXPOSURES" in ocr_upper or 
                    "DERIVATIVE EXPOSURES" in ocr_upper
                ):
                    logger.info("Found DERIVATIVE EXPOSURES table!")
                    derivative_stocks = parse_derivative_exposures(ocr_text)
                    if derivative_stocks:
                        all_stocks.extend(derivative_stocks)
                        found_derivative_table = True
                        logger.info(f"Extracted {len(derivative_stocks)} crypto stocks")
                        
            except Exception as e:
                logger.error(f"Error processing image {idx}: {e}")
                continue
        
        # Log what we found
        if not found_crypto_table:
            logger.warning("Did not find HEDGEYE RISK RANGES table")
        if not found_derivative_table:
            logger.warning("Did not find DERIVATIVE EXPOSURES table")
            
    except Exception as e:
        logger.error(f"Error in extract_crypto_data: {e}")
    
    return all_stocks


def ocr_image_with_mistral(image_data: bytes) -> Optional[str]:
    """
    OCR an image using Mistral AI.
    
    Args:
        image_data: Image bytes
        
    Returns:
        OCR text or None
    """
    try:
        # Convert to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Prepare request
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
                        "text": "Extract all text from this image. Focus on tables with headers like 'HEDGEYE RISK RANGES' or 'DERIVATIVE EXPOSURES'. Include all numbers, tickers, and price data exactly as shown."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    }
                ]
            }]
        }
        
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            ocr_text = response.json()['choices'][0]['message']['content']
            logger.info(f"OCR extracted {len(ocr_text)} characters")
            return ocr_text
        else:
            logger.error(f"Mistral OCR failed: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error in OCR: {e}")
        return None


def parse_crypto_risk_ranges(ocr_text: str) -> List[Dict[str, Any]]:
    """
    Parse the HEDGEYE RISK RANGES table for cryptocurrencies.
    
    Expected format:
    HEDGEYE RISK RANGES*
    TICKER | PRICE | BUY TRADE | SELL TRADE | TREND
    BTC    | 94,567| 89,012    | 96,968     | BULLISH
    ETH    | 3,456 | 3,253     | 3,924      | BULLISH
    etc.
    """
    stocks = []
    
    try:
        lines = ocr_text.split('\n')
        
        # Find table start
        table_start = -1
        for i, line in enumerate(lines):
            if "HEDGEYE RISK RANGES" in line.upper():
                table_start = i
                break
        
        if table_start == -1:
            return stocks
        
        # Expected crypto tickers
        crypto_tickers = ['BTC', 'ETH', 'SOL', 'AVAX', 'AAVE', 'XRP', 'ADA', 'MATIC', 'DOT', 'LINK']
        
        # Process lines after header
        for i in range(table_start + 1, min(table_start + 20, len(lines))):
            line = lines[i].strip()
            
            if not line:
                continue
            
            # Check each crypto ticker
            for ticker in crypto_tickers:
                if ticker in line.upper():
                    # Extract numbers from the line
                    numbers = re.findall(r'[\d,]+\.?\d*', line)
                    
                    if len(numbers) >= 3:  # Need at least price, buy, sell
                        try:
                            # Remove commas and convert to float
                            buy_price = float(numbers[1].replace(',', ''))
                            sell_price = float(numbers[2].replace(',', ''))
                            
                            # Determine sentiment
                            sentiment = "bullish"
                            if "BEARISH" in line.upper():
                                sentiment = "bearish"
                            elif "NEUTRAL" in line.upper():
                                sentiment = "neutral"
                            
                            stock = {
                                "ticker": ticker,
                                "sentiment": sentiment,
                                "buy_trade": buy_price,
                                "sell_trade": sell_price,
                                "category": "digitalassets"
                            }
                            stocks.append(stock)
                            logger.info(f"Extracted {ticker}: Buy=${buy_price}, Sell=${sell_price}, Sentiment={sentiment}")
                            break
                            
                        except Exception as e:
                            logger.error(f"Error parsing {ticker} line: {e}")
                            
    except Exception as e:
        logger.error(f"Error parsing crypto risk ranges: {e}")
    
    return stocks


def parse_derivative_exposures(ocr_text: str) -> List[Dict[str, Any]]:
    """
    Parse the DIRECT & DERIVATIVE EXPOSURES table for crypto stocks.
    
    Expected format:
    DIRECT & DERIVATIVE EXPOSURES: RISK RANGE & TREND SIGNAL
    TICKER | PRICE | BUY TRADE | SELL TRADE | TREND
    IBIT   | 65.19 | 61.85     | 69.17      | BULLISH
    MSTR   | 405   | 385       | 465        | BULLISH
    etc.
    """
    stocks = []
    
    try:
        lines = ocr_text.split('\n')
        
        # Find table start
        table_start = -1
        for i, line in enumerate(lines):
            line_upper = line.upper()
            if "DERIVATIVE EXPOSURES" in line_upper or "RISK RANGE & TREND SIGNAL" in line_upper:
                table_start = i
                break
        
        if table_start == -1:
            return stocks
        
        # Expected crypto stock tickers
        crypto_stock_tickers = ['IBIT', 'BITO', 'ETHA', 'BLOK', 'MSTR', 'MARA', 'RIOT', 'COIN', 'CLSK', 'HUT', 'BITF']
        
        # Process lines after header
        for i in range(table_start + 1, min(table_start + 25, len(lines))):
            line = lines[i].strip()
            
            if not line:
                continue
            
            # Check each crypto stock ticker
            for ticker in crypto_stock_tickers:
                if ticker in line.upper():
                    # Extract numbers from the line
                    numbers = re.findall(r'[\d,]+\.?\d*', line)
                    
                    if len(numbers) >= 3:  # Need at least price, buy, sell
                        try:
                            # Remove commas and convert to float
                            buy_price = float(numbers[1].replace(',', ''))
                            sell_price = float(numbers[2].replace(',', ''))
                            
                            # Determine sentiment
                            sentiment = "bullish"
                            if "BEARISH" in line.upper():
                                sentiment = "bearish"
                            elif "NEUTRAL" in line.upper():
                                sentiment = "neutral"
                            
                            stock = {
                                "ticker": ticker,
                                "sentiment": sentiment,
                                "buy_trade": buy_price,
                                "sell_trade": sell_price,
                                "category": "digitalassets"
                            }
                            stocks.append(stock)
                            logger.info(f"Extracted {ticker}: Buy=${buy_price}, Sell=${sell_price}, Sentiment={sentiment}")
                            break
                            
                        except Exception as e:
                            logger.error(f"Error parsing {ticker} line: {e}")
                            
    except Exception as e:
        logger.error(f"Error parsing derivative exposures: {e}")
    
    return stocks