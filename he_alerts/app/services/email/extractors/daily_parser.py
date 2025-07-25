"""
Daily email HTML parser for RISK RANGE signals.
Uses BeautifulSoup to parse HTML tables directly without AI.
"""
import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import structlog

from app.schemas.stock import StockCreate

logger = structlog.get_logger(__name__)

# Tickers to exclude (indices, bonds, commodities, etc.)
EXCLUDE_TICKERS = {
    'UST30Y', 'UST10Y', 'UST2Y', 'SPX', 'COMPQ', 'RUT', 'SSEC', 'NIKK', 
    'BSE', 'DAX', 'VIX', 'USD', 'EUR/USD', 'USD/YEN', 'GBP/USD', 'CAD/USD',
    'WTIC', 'BRENT', 'NATGAS', 'GOLD', 'COPPER', 'SILVER', 'BITCOIN'
}


def parse_daily_email(email_content: str) -> List[Dict[str, any]]:
    """
    Parse daily RISK RANGE email using HTML parsing.
    
    Args:
        email_content: Raw email HTML content
        
    Returns:
        List of dictionaries with extracted stock data
    """
    try:
        stocks = []
        soup = BeautifulSoup(email_content, 'html.parser')
        
        # Look for tables in the content
        tables = soup.find_all('table')
        logger.info(f"Found {len(tables)} tables in daily email")
        
        # Try to find the right table with our data
        target_table = None
        for i, table in enumerate(tables):
            # Check if this table has the right structure
            rows = table.find_all('tr')
            if not rows:
                continue
            
            # Check the header row
            header_cells = rows[0].find_all(['th', 'td'])
            header_text = ' '.join([cell.get_text(strip=True) for cell in header_cells])
            
            # Look for key indicators in the header
            if (('INDEX' in header_text or 'TICKER' in header_text) and 
                'BUY TRADE' in header_text and 'SELL TRADE' in header_text):
                target_table = table
                logger.info(f"Found target table at index {i}")
                break
        
        # If we found the target table, parse it
        if target_table:
            rows = target_table.find_all('tr')
            # Skip the header row
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:  # Need at least ticker, buy, sell
                    try:
                        ticker_cell = cells[0].get_text(strip=True)
                        # Extract ticker and sentiment
                        ticker_match = re.search(r'([A-Z0-9/]+)\s+\((BULLISH|BEARISH|NEUTRAL)\)', ticker_cell)
                        if ticker_match:
                            ticker = ticker_match.group(1)
                            sentiment = ticker_match.group(2).lower()  # Convert to lowercase
                            
                            # Skip excluded tickers
                            if ticker in EXCLUDE_TICKERS:
                                logger.debug(f"Skipping excluded ticker: {ticker}")
                                continue
                            
                            # Get buy and sell values
                            buy_text = cells[1].get_text(strip=True)
                            sell_text = cells[2].get_text(strip=True)
                            
                            # Convert to float if valid
                            buy_trade = None
                            if re.search(r'\d', buy_text):
                                buy_trade = float(re.sub(r'[^\d.]', '', buy_text))
                            
                            sell_trade = None
                            if re.search(r'\d', sell_text):
                                sell_trade = float(re.sub(r'[^\d.]', '', sell_text))
                            
                            # Only add if we have valid prices
                            if buy_trade is not None and sell_trade is not None:
                                stock = {
                                    "ticker": ticker,
                                    "sentiment": sentiment,
                                    "buy_trade": buy_trade,
                                    "sell_trade": sell_trade,
                                    "category": "daily"
                                }
                                stocks.append(stock)
                                logger.info(f"Extracted daily stock: {ticker} - Sentiment: {sentiment}, Buy: {buy_trade}, Sell: {sell_trade}")
                    except Exception as e:
                        logger.error(f"Error parsing table row: {e}")
            
            if stocks:
                logger.info(f"Successfully extracted {len(stocks)} stocks from HTML table")
                return stocks
        
        # If HTML parsing didn't work, try text-based parsing
        logger.info("HTML table parsing didn't yield results, trying text-based parsing")
        
        # Convert HTML to plain text
        text_content = soup.get_text()
        lines = text_content.split('\n')
        
        # Find the header line
        header_idx = -1
        for i, line in enumerate(lines):
            if (('INDEX' in line or 'TICKER' in line) and 
                'BUY TRADE' in line and 'SELL TRADE' in line):
                header_idx = i
                logger.info(f"Found header at line {i}: {line}")
                break
        
        # If we couldn't find the header, try to find the RISK RANGE SIGNALS section
        if header_idx == -1:
            for i, line in enumerate(lines):
                if re.search(r'RISK RANGE\s*(?:™)?\s*SIGNALS:', line, re.IGNORECASE):
                    header_idx = i
                    logger.info(f"Found RISK RANGE SIGNALS at line {i}")
                    break
        
        if header_idx == -1:
            logger.warning("Could not find header line in daily email")
            return stocks
        
        # Process data after the header
        i = header_idx + 1
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                i += 1
                continue
            
            # Look for ticker and sentiment pattern
            ticker_match = re.search(r'([A-Z0-9/]+)\s+\((BULLISH|BEARISH|NEUTRAL)\)', line)
            if ticker_match:
                ticker = ticker_match.group(1)
                sentiment = ticker_match.group(2).lower()
                
                # Skip excluded tickers
                if ticker in EXCLUDE_TICKERS:
                    i += 1
                    continue
                
                # Look for values in the current line or next lines
                values = []
                
                # Check current line for numbers
                current_values = re.findall(r'([\d,\.]+)', line)
                values.extend(current_values)
                
                # If not enough values, check next lines
                j = i + 1
                while j < len(lines) and len(values) < 2:
                    next_line = lines[j].strip()
                    if next_line and not re.search(r'[A-Z0-9/]+\s+\(', next_line):
                        next_values = re.findall(r'([\d,\.]+)', next_line)
                        values.extend(next_values)
                        if next_values:
                            break
                    else:
                        break
                    j += 1
                
                if len(values) >= 2:
                    try:
                        buy_trade = float(values[0].replace(',', ''))
                        sell_trade = float(values[1].replace(',', ''))
                        
                        stock = {
                            "ticker": ticker,
                            "sentiment": sentiment,
                            "buy_trade": buy_trade,
                            "sell_trade": sell_trade,
                            "category": "daily"
                        }
                        stocks.append(stock)
                        logger.info(f"Extracted daily stock from text: {ticker} - Buy: {buy_trade}, Sell: {sell_trade}")
                    except Exception as e:
                        logger.error(f"Error parsing values for {ticker}: {e}")
            i += 1
        
        logger.info(f"Total daily stocks extracted: {len(stocks)}")
        return stocks
        
    except Exception as e:
        logger.error(f"Error parsing daily email: {e}")
        return []


def validate_daily_stocks(stocks: List[Dict[str, any]]) -> List[Dict[str, any]]:
    """
    Validate extracted daily stock data.
    
    Args:
        stocks: List of extracted stocks
        
    Returns:
        List of validated stocks
    """
    validated = []
    
    for stock in stocks:
        # Skip if ticker is in exclude list
        if stock.get('ticker') in EXCLUDE_TICKERS:
            continue
            
        # Validate prices are reasonable
        buy_trade = stock.get('buy_trade')
        sell_trade = stock.get('sell_trade')
        
        if buy_trade and sell_trade:
            # For daily stocks, prices should be positive and reasonable
            if 0 < buy_trade < 100000 and 0 < sell_trade < 100000:
                validated.append(stock)
            else:
                logger.warning(f"Invalid prices for {stock.get('ticker')}: Buy={buy_trade}, Sell={sell_trade}")
        else:
            logger.warning(f"Missing prices for {stock.get('ticker')}")
    
    logger.info(f"Validated {len(validated)} out of {len(stocks)} daily stocks")
    return validated