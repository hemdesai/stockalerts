from pathlib import Path
import sys
import re
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf
from pydantic import BaseModel
from typing import List, Optional
import os
import logging
from bs4 import BeautifulSoup

# Set up logging
logger = logging.getLogger(__name__)

# Add the project root to Python path when running directly
if __name__ == "__main__":
    # Get the absolute path to the project root directory
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.append(str(project_root))
    
    # When running directly, we need to import this way
    from stockalert.scripts.extractors import BaseEmailExtractor
else:
    # When imported as a module by another script, we import this way
    from . import BaseEmailExtractor

# Define Pydantic models for Daily data
class DailyAsset(BaseModel):
    ticker: str
    sentiment: str
    buy_trade: float
    sell_trade: float
    category: str = "daily"

class DailyData(BaseModel):
    assets: List[DailyAsset]

class DailyExtractor(BaseEmailExtractor):
    def __init__(self):
        super().__init__()
        self.ticker_mappings = {
            'UST30Y': '^TYX',
            'UST10Y': '^TNX',
            'UST2Y': '2YY=F',
            'SPX': '^GSPC',
            'COMPQ': '^IXIC',
            'RUT': '^RUT',
            'SSEC': '000001.SS',
            'NIKK': '^N225',
            'BSE': '^BSESN',
            'DAX': '^GDAXI',
            'VIX': '^VIX',
            'USD': 'DX-Y.NYB',
            'EUR/USD': 'EURUSD=X',
            'USD/YEN': 'JPY=X',
            'GBP/USD': 'GBPUSD=X',
            'CAD/USD': 'CADUSD=X',
            'WTIC': 'CL=F',
            'BRENT': 'BZ=F',
            'NATGAS': 'NG=F',
            'GOLD': 'GC=F',
            'COPPER': 'HG=F',
            'SILVER': 'SI=F',
            'BITCOIN': 'BTC-USD'
        }

    def get_ticker_name(self, ticker):
        """Get company/instrument name from yfinance"""
        try:
            info = yf.Ticker(ticker).info
            return info.get('shortName', '') or info.get('longName', '')
        except:
            return ''

    def extract(self):
        """Extract data from today's RISK RANGE email"""
        try:
            logger.info(f"Starting daily extraction from Gmail at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
            
            # First try today's email
            today = datetime.now().strftime('%Y/%m/%d')
            query = f'subject:"RISK RANGE" after:{today}'
            logger.info(f"Searching for today's RISK RANGE email with query: {query}")
            
            # Check MCP connection before proceeding
            if not self.using_mcp:
                self.check_mcp_connection()
                
            content = self.get_email_content(query)
            
            if not content:
                # If no email today, try last 3 days
                three_days_ago = (datetime.now() - timedelta(days=3)).strftime('%Y/%m/%d')
                query = f'subject:"RISK RANGE" after:{three_days_ago}'
                logger.info(f"No email found today, trying query: {query}")
                content = self.get_email_content(query)
            
            if not content:
                logger.warning("No RISK RANGE emails found in the last 3 days")
                logger.error("No data to process. Please check email access or try again later.")
                return []
            
            logger.info(f"Found email content, length: {len(content)}")
            
            # Save the raw email HTML for debugging
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / 'data'
            data_dir.mkdir(exist_ok=True)
            with open(data_dir / 'daily_email_raw.html', 'w', encoding='utf-8') as f:
                f.write(content)
                logger.debug(f"Saved raw email HTML to: {data_dir / 'daily_email_raw.html'}")
            
            # Parse the content
            parsed_data = self.parse_content(content)
            
            if not parsed_data:
                logger.warning("Parsing returned no data")
                return []
            
            # Save to CSV
            self.save_to_csv(parsed_data)
            
            # Clean up temporary files
            self.cleanup_temp_files()
            
            return parsed_data
        except Exception as e:
            logger.error(f"Error in extract: {e}")
            import traceback
            traceback.print_exc()
            
            # No fallback data, just return empty list
            logger.error("Extraction failed, no data available")
            return []

    def save_to_csv(self, data):
        """Save extracted data to CSV"""
        try:
            if not data:
                logger.warning("No data to save")
                return False
                
            # Create DataFrame
            df = pd.DataFrame(data)
            
            # Save to CSV
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / 'data'
            data_dir.mkdir(exist_ok=True)
            csv_path = data_dir / 'daily.csv'
            df.to_csv(csv_path, index=False)
            
            logger.info(f"CSV saved to: {csv_path}")
            logger.info(f"Total tickers saved: {len(data)}")
            return True
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
            return False

    def parse_content(self, content):
        """Parse email content into structured data"""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            parsed_data = []
            
            # Method 1: Try to find the data in HTML structure
            # Look for the section after "RISK RANGE™ SIGNALS:"
            signal_section = soup.find(text=re.compile(r'RISK RANGE™ SIGNALS:'))
            if signal_section:
                logger.info("Found RISK RANGE SIGNALS section")
                parent = signal_section.parent
                
                # Navigate through the HTML to find the data table
                # This might need adjustment based on the actual HTML structure
                table_section = None
                for sibling in parent.next_siblings:
                    if hasattr(sibling, 'find_all') and sibling.find_all('tr'):
                        table_section = sibling
                        break
                
                if table_section:
                    logger.info("Found table section")
                    rows = table_section.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) >= 4:  # Expecting at least 4 cells: ticker, sentiment, buy, sell
                            try:
                                ticker_cell = cells[0].text.strip()
                                # Extract ticker and sentiment
                                ticker_match = re.search(r'([A-Z0-9/]+)\s+\((BULLISH|BEARISH|NEUTRAL)\)', ticker_cell)
                                if ticker_match:
                                    ticker = ticker_match.group(1)
                                    sentiment = ticker_match.group(2)
                                    
                                    # Extract buy and sell values
                                    buy_text = cells[2].text.strip() if len(cells) > 2 else ""
                                    sell_text = cells[3].text.strip() if len(cells) > 3 else ""
                                    
                                    # Clean and convert to float
                                    buy = float(re.sub(r'[^\d.]', '', buy_text)) if buy_text else 0.0
                                    sell = float(re.sub(r'[^\d.]', '', sell_text)) if sell_text else 0.0
                                    
                                    mapped_ticker = self.ticker_mappings.get(ticker, ticker)
                                    parsed_data.append({
                                        'ticker': mapped_ticker,
                                        'sentiment': sentiment,
                                        'buy_trade': buy,
                                        'sell_trade': sell,
                                        'category': 'daily'
                                    })
                            except Exception as e:
                                logger.error(f"Error parsing row: {e}")
                                continue
            
            # Method 2: If HTML parsing didn't work, try text-based parsing
            if not parsed_data:
                logger.info("HTML parsing didn't yield results, trying text-based parsing")
                lines = content.split('\n')
                
                # Find the start of the data section
                start_idx = -1
                for i, line in enumerate(lines):
                    if 'RISK RANGE™ SIGNALS:' in line:
                        start_idx = i
                        break
                
                if start_idx == -1:
                    logger.warning("Could not find data section")
                    return None
                
                # Process lines
                for i, line in enumerate(lines[start_idx:]):
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Look for ticker and sentiment
                    ticker_match = re.search(r'([A-Z0-9/]+)\s+\((BULLISH|BEARISH|NEUTRAL)\)', line)
                    if ticker_match:
                        try:
                            ticker = ticker_match.group(1)
                            sentiment = ticker_match.group(2)
                            
                            # Get the next line which should contain the values
                            next_line = lines[start_idx + i + 1].strip() if start_idx + i + 1 < len(lines) else ""
                            
                            # Extract only the numbers at the end of the line
                            # This should avoid picking up numbers from descriptions
                            value_match = re.search(r'.*?([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)$', next_line)
                            if value_match:
                                buy = float(value_match.group(1).replace(',', ''))
                                sell = float(value_match.group(2).replace(',', ''))
                                
                                mapped_ticker = self.ticker_mappings.get(ticker, ticker)
                                parsed_data.append({
                                    'ticker': mapped_ticker,
                                    'sentiment': sentiment,
                                    'buy_trade': buy,
                                    'sell_trade': sell,
                                    'category': 'daily'
                                })
                                logger.debug(f"Parsed: {mapped_ticker} - Buy: {buy}, Sell: {sell}")
                        except (ValueError, IndexError) as e:
                            logger.error(f"Error parsing data for {ticker}: {e}")
                            continue
            
            logger.info(f"Total records parsed: {len(parsed_data)}")
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error parsing content: {e}")
            import traceback
            traceback.print_exc()
            return None



    def cleanup_temp_files(self):
        """Clean up temporary files created during extraction"""
        try:
            # Get the data directory
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / 'data'
            
            # Files to clean up
            files_to_clean = [
                data_dir / 'daily_email_raw.html'
            ]
            
            # Delete each file if it exists
            for file_path in files_to_clean:
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Cleaned up temporary file: {file_path}")
            
            # Also check for any other daily_*.html files that might have been created
            for file_path in data_dir.glob('daily_*.html'):
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Cleaned up temporary file: {file_path}")
            
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {e}")


if __name__ == "__main__":
    logger.info(f"Starting daily extraction from Gmail at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    
    # Create an instance of the extractor
    extractor = DailyExtractor()
    
    # Run the extraction
    result = extractor.extract()
    
    # Print the result
    if result:
        logger.info("Daily extraction completed successfully")
        
        # Verify the CSV file
        project_root = Path(__file__).parent.parent.parent
        csv_path = project_root / 'data' / 'daily.csv'
        
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                logger.info(f"CSV contains {len(df)} tickers")
                
                # Print summary
                bullish_count = sum(1 for asset in result if asset['sentiment'] == 'BULLISH')
                bearish_count = sum(1 for asset in result if asset['sentiment'] == 'BEARISH')
                neutral_count = sum(1 for asset in result if asset['sentiment'] == 'NEUTRAL')
                
                logger.info("\nDaily Extraction Summary:")
                logger.info(f"Total assets: {len(result)}")
                logger.info(f"BULLISH: {bullish_count}")
                logger.info(f"BEARISH: {bearish_count}")
                logger.info(f"NEUTRAL: {neutral_count}")
            except Exception as e:
                logger.error(f"Error verifying CSV: {e}")
    else:
        logger.error("Daily extraction failed")