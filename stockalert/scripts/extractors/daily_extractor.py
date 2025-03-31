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
        """Extract data from today's RISK RANGE email using MCP only"""
        try:
            logger.info(f"Starting daily extraction from Gmail via MCP at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
            
            # First try today's email
            today = datetime.now().strftime('%Y/%m/%d')
            query = f'subject:"RISK RANGE" after:{today}'
            logger.info(f"Searching for today's RISK RANGE email with query: {query}")
            
            # Ensure MCP connection is active
            if not self.mcp_client.check_connection():
                logger.error("MCP connection is not available. Cannot proceed with extraction.")
                return []
                
            content = self.mcp_client.get_email_content(query)
            
            if not content:
                # If no email today, try last 3 days
                three_days_ago = (datetime.now() - timedelta(days=3)).strftime('%Y/%m/%d')
                query = f'subject:"RISK RANGE" after:{three_days_ago}'
                logger.info(f"No email found today, trying query: {query}")
                content = self.mcp_client.get_email_content(query)
            
            if not content:
                logger.warning("No RISK RANGE emails found in the last 3 days via MCP")
                logger.error("No data to process. Please check email access or try again later.")
                return []
            
            logger.info(f"Found email content via MCP, length: {len(content)}")
            
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
            logger.error(traceback.format_exc())
            return []

    def extract_from_email(self, email_content):
        """Extract data from email content"""
        if not email_content:
            logger.error("No email content provided")
            return None
        
        # Parse the content
        parsed_data = self.parse_content(email_content)
        if not parsed_data:
            logger.error("Failed to parse email content")
            return None
        
        logger.info(f"Successfully extracted {len(parsed_data)} records from email")
        return parsed_data

    def get_email_content(self, query, max_results=1):
        """Get content from latest matching email using MCP server only"""
        try:
            # Ensure MCP connection is active
            if not self.mcp_client.check_connection():
                logger.error("MCP connection is not available. Cannot retrieve email content.")
                return None
                
            logger.info(f"Attempting to get email content via MCP for query: {query}")
            content = self.mcp_client.get_email_content(query, max_results)
            
            if content:
                logger.info(f"Successfully retrieved email content via MCP for query: {query}")
                return content
            else:
                logger.error(f"MCP client failed to retrieve email content for query: {query}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting email content via MCP: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
            
    def parse_direct_format(self, content):
        """Parse the exact format provided by the user"""
        try:
            logger.info("Parsing using the direct format method")
            parsed_data = []
            
            # Save the raw content for debugging
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / 'data'
            data_dir.mkdir(exist_ok=True)
            with open(data_dir / 'daily_email_raw.txt', 'w', encoding='utf-8') as f:
                f.write(content)
                logger.debug(f"Saved raw email content to: {data_dir / 'daily_email_raw.txt'}")
            
            # First, try to extract the table section from the HTML
            soup = BeautifulSoup(content, 'html.parser')
            
            # Look for tables in the content
            tables = soup.find_all('table')
            logger.info(f"Found {len(tables)} tables in the content")
            
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
                
                logger.debug(f"Table {i} header: {header_text}")
                
                # Look for key indicators in the header
                if ('INDEX' in header_text and 'BUY TRADE' in header_text and 
                    'SELL TRADE' in header_text and 'PREV' in header_text):
                    target_table = table
                    logger.info(f"Found target table at index {i}")
                    break
            
            # If we found the target table, parse it
            if target_table:
                rows = target_table.find_all('tr')
                # Skip the header row
                for row in rows[1:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 4:  # Need at least ticker, buy, sell, prev
                        try:
                            ticker_cell = cells[0].get_text(strip=True)
                            # Extract ticker and sentiment
                            ticker_match = re.search(r'([A-Z0-9/]+)\s+\((BULLISH|BEARISH|NEUTRAL)\)', ticker_cell)
                            if ticker_match:
                                ticker = ticker_match.group(1)
                                sentiment = ticker_match.group(2)
                                
                                # Get buy and sell values
                                buy_text = cells[1].get_text(strip=True)
                                sell_text = cells[2].get_text(strip=True)
                                
                                # Convert to float if valid
                                buy = 0.0
                                if re.search(r'\d', buy_text):
                                    buy = float(re.sub(r'[^\d.]', '', buy_text))
                                
                                sell = 0.0
                                if re.search(r'\d', sell_text):
                                    sell = float(re.sub(r'[^\d.]', '', sell_text))
                                
                                # Add to parsed data
                                mapped_ticker = self.ticker_mappings.get(ticker, ticker)
                                parsed_data.append({
                                    'ticker': mapped_ticker,
                                    'sentiment': sentiment,
                                    'buy_trade': buy,
                                    'sell_trade': sell,
                                    'category': 'daily'
                                })
                                logger.info(f"Successfully parsed {ticker}: Buy={buy}, Sell={sell}")
                        except Exception as e:
                            logger.error(f"Error parsing row: {e}")
                
                if parsed_data:
                    logger.info(f"Successfully parsed {len(parsed_data)} tickers from HTML table")
                    return parsed_data
            
            # If HTML parsing didn't work, try text-based parsing
            logger.info("HTML table parsing didn't yield results, trying text-based parsing")
            
            # Convert HTML to plain text
            text_content = soup.get_text()
            
            # Save the text content for debugging
            with open(data_dir / 'daily_email_text.txt', 'w', encoding='utf-8') as f:
                f.write(text_content)
                logger.debug(f"Saved text content to: {data_dir / 'daily_email_text.txt'}")
            
            lines = text_content.split('\n')
            
            # Find the header line - look for various patterns
            header_idx = -1
            for i, line in enumerate(lines):
                # Look for the header line with various patterns
                if (('INDEX' in line and 'BUY TRADE' in line and 'SELL TRADE' in line) or
                    ('TICKER' in line and 'BUY TRADE' in line and 'SELL TRADE' in line)):
                    header_idx = i
                    logger.info(f"Found header at line {i}: {line}")
                    break
            
            # If we couldn't find the header, try to find the RISK RANGE SIGNALS section
            if header_idx == -1:
                for i, line in enumerate(lines):
                    if re.search(r'RISK RANGE\s*(?:™)?\s*SIGNALS:', line, re.IGNORECASE):
                        header_idx = i
                        logger.info(f"Found RISK RANGE SIGNALS at line {i}: {line}")
                        break
            
            if header_idx == -1:
                logger.warning("Could not find header line in the content")
                return None
            
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
                    sentiment = ticker_match.group(2)
                    logger.debug(f"Found ticker: {ticker}, sentiment: {sentiment}")
                    
                    # Look for values in the current line or next line
                    values_line = line
                    
                    # If values are not in the current line, check the next line
                    if not re.search(r'\d+\.?\d*', values_line):
                        i += 1
                        if i < len(lines):
                            values_line = lines[i].strip()
                    
                    # Extract all numbers from the line
                    values = re.findall(r'([\d,\.]+)', values_line)
                    
                    if values:
                        try:
                            # Determine which values are buy and sell
                            buy = 0.0
                            sell = 0.0
                            
                            # If we have at least 2 values, use the first two for buy and sell
                            if len(values) >= 2:
                                if re.search(r'\d', values[0]):
                                    buy = float(values[0].replace(',', ''))
                                if re.search(r'\d', values[1]):
                                    sell = float(values[1].replace(',', ''))
                            elif len(values) == 1:
                                # If only one value, assume it's buy
                                if re.search(r'\d', values[0]):
                                    buy = float(values[0].replace(',', ''))
                            
                            # Add to parsed data
                            mapped_ticker = self.ticker_mappings.get(ticker, ticker)
                            parsed_data.append({
                                'ticker': mapped_ticker,
                                'sentiment': sentiment,
                                'buy_trade': buy,
                                'sell_trade': sell,
                                'category': 'daily'
                            })
                            logger.info(f"Successfully parsed {ticker}: Buy={buy}, Sell={sell}")
                        except Exception as e:
                            logger.error(f"Error parsing values for {ticker}: {e}")
                i += 1
            
            logger.info(f"Total records parsed: {len(parsed_data)}")
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error in direct format parsing: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def parse_content(self, content):
        """Parse email content into structured data"""
        try:
            # Save the raw email content for debugging
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / 'data'
            data_dir.mkdir(exist_ok=True)
            with open(data_dir / 'daily_email_raw.html', 'w', encoding='utf-8') as f:
                f.write(content)
                logger.debug(f"Saved raw email HTML to: {data_dir / 'daily_email_raw.html'}")
            
            # First try the direct format parser
            logger.info("Attempting direct format parsing first")
            parsed_data = self.parse_direct_format(content)
            if parsed_data and len(parsed_data) > 0:
                logger.info(f"Direct format parsing successful, found {len(parsed_data)} records")
                return parsed_data
            
            # If direct parsing fails, try HTML-based parsing
            logger.info("Direct format parsing failed, trying HTML-based parsing")
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract text content for fallback parsing
            text_content = soup.get_text()
            with open(data_dir / 'daily_email_text.txt', 'w', encoding='utf-8') as f:
                f.write(text_content)
                logger.debug(f"Saved text content to: {data_dir / 'daily_email_text.txt'}")
            
            # Try direct format parsing on the extracted text
            logger.info("Attempting direct format parsing on extracted text")
            parsed_data = self.parse_direct_format(text_content)
            if parsed_data and len(parsed_data) > 0:
                logger.info(f"Text-based direct format parsing successful, found {len(parsed_data)} records")
                return parsed_data
            
            # Method 1: Try to find the data in HTML structure
            parsed_data = []
            
            # Look for tables in the content
            tables = soup.find_all('table')
            logger.info(f"Found {len(tables)} tables in the content")
            
            # Try to find the right table with our data
            for i, table in enumerate(tables):
                table_data = []
                
                # Check if this table has rows
                rows = table.find_all('tr')
                if not rows:
                    continue
                
                logger.info(f"Analyzing table {i} with {len(rows)} rows")
                
                # Check the header row
                header_cells = rows[0].find_all(['th', 'td'])
                header_text = ' '.join([cell.get_text(strip=True) for cell in header_cells])
                
                logger.debug(f"Table {i} header: {header_text}")
                
                # Skip tables without proper headers
                if not ('BUY' in header_text and 'SELL' in header_text):
                    continue
                
                # Find the indices for BUY TRADE and SELL TRADE
                buy_idx = -1
                sell_idx = -1
                
                for j, cell in enumerate(header_cells):
                    cell_text = cell.get_text(strip=True).upper()
                    if 'BUY' in cell_text:
                        buy_idx = j
                    elif 'SELL' in cell_text:
                        sell_idx = j
                
                if buy_idx == -1 or sell_idx == -1:
                    logger.warning(f"Could not identify BUY and SELL columns in table {i}")
                    continue
                
                logger.info(f"Found potential data table {i} with BUY at column {buy_idx} and SELL at column {sell_idx}")
                
                # Process data rows
                for row_idx, row in enumerate(rows[1:], 1):  # Skip header row
                    cells = row.find_all(['td', 'th'])
                    if len(cells) <= max(buy_idx, sell_idx):
                        continue
                    
                    try:
                        # Extract ticker and sentiment from first column
                        ticker_cell = cells[0].get_text(strip=True)
                        ticker_match = re.search(r'([A-Z0-9/]+)\s*\((BULLISH|BEARISH|NEUTRAL)\)', ticker_cell)
                        
                        if not ticker_match:
                            continue
                        
                        ticker = ticker_match.group(1).strip()
                        sentiment = ticker_match.group(2).strip()
                        
                        # Extract buy and sell values
                        buy_text = cells[buy_idx].get_text(strip=True)
                        sell_text = cells[sell_idx].get_text(strip=True)
                        
                        # Convert to float
                        buy = 0.0
                        if re.search(r'\d', buy_text):
                            buy = float(re.sub(r'[^\d.]', '', buy_text))
                        
                        sell = 0.0
                        if re.search(r'\d', sell_text):
                            sell = float(re.sub(r'[^\d.]', '', sell_text))
                        
                        # Add to table data
                        mapped_ticker = self.ticker_mappings.get(ticker, ticker)
                        table_data.append({
                            'ticker': mapped_ticker,
                            'sentiment': sentiment,
                            'buy_trade': buy,
                            'sell_trade': sell,
                            'category': 'daily'
                        })
                        logger.debug(f"Parsed from table: {ticker} - Buy: {buy}, Sell: {sell}")
                    except Exception as e:
                        logger.error(f"Error parsing row {row_idx} in table {i}: {e}")
                
                # If we found data in this table, add it to our results
                if table_data:
                    logger.info(f"Successfully parsed {len(table_data)} records from table {i}")
                    parsed_data.extend(table_data)
                    break  # Stop after finding one good table
            
            # If we found data from HTML tables, return it
            if parsed_data:
                logger.info(f"HTML table parsing successful, found {len(parsed_data)} records")
                return parsed_data
            
            # Method 2: Last resort - try text-based parsing with more flexible patterns
            logger.info("HTML parsing didn't yield results, trying flexible text-based parsing")
            
            # Look for the RISK RANGE SIGNALS section
            signal_section_idx = -1
            lines = text_content.split('\n')
            
            for i, line in enumerate(lines):
                if re.search(r'RISK RANGE\s*(?:™)?\s*SIGNALS:', line, re.IGNORECASE):
                    signal_section_idx = i
                    logger.info(f"Found RISK RANGE SIGNALS at line {i}: {line}")
                    break
            
            if signal_section_idx != -1:
                # Create a subset of lines starting from the signals section
                subset_content = '\n'.join(lines[signal_section_idx:])
                
                # Try direct format parsing on this subset
                logger.info("Attempting direct format parsing on signals section subset")
                parsed_data = self.parse_direct_format(subset_content)
                if parsed_data and len(parsed_data) > 0:
                    logger.info(f"Signals section parsing successful, found {len(parsed_data)} records")
                    return parsed_data
            
            logger.warning("All parsing methods failed")
            return None
            
        except Exception as e:
            logger.error(f"Error parsing content: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

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

    def create_test_data(self):
        """Create test data for debugging purposes"""
        test_data = """
        <html>
        <body>
        <p>RISK RANGE™ SIGNALS:</p>
        <table>
        <tr>
        <th>TICKER</th>
        <th>BUY TRADE</th>
        <th>SELL TRADE</th>
        <th>PREV. CLOSE</th>
        </tr>
        <tr>
        <td>SPX (BULLISH)</td>
        <td>5100.25</td>
        <td>5250.75</td>
        <td>5175.50</td>
        </tr>
        <tr>
        <td>UST10Y (BEARISH)</td>
        <td>4.25</td>
        <td>4.50</td>
        <td>4.35</td>
        </tr>
        </table>
        </body>
        </html>
        """
        
        # Save test data to file
        project_root = Path(__file__).parent.parent.parent
        data_dir = project_root / 'data'
        data_dir.mkdir(exist_ok=True)
        test_file = data_dir / 'daily_test.html'
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_data)
        
        logger.info(f"Created test data file at: {test_file}")
        
        # Parse the test data
        parsed_data = self.parse_content(test_data)
        
        if parsed_data:
            logger.info("Test parsing successful!")
            for item in parsed_data:
                logger.info(f"Ticker: {item['ticker']}, Buy: {item['buy_trade']}, Sell: {item['sell_trade']}")
            
            # Save to CSV
            self.save_to_csv(parsed_data)
            return True
        else:
            logger.error("Test parsing failed!")
            return False

    def test_with_sample(self):
        """Test the extractor with the exact sample data provided by the user"""
        logger.info("Testing with the exact sample data...")
        
        # Sample data exactly as provided by the user
        sample_data = """
        <html>
        <body>
        <p>RISK RANGE SIGNALS:</p>
        <table>
        <tr>
        <th>TICKER</th>
        <th>BUY TRADE</th>
        <th>SELL TRADE</th>
        <th>PREV. CLOSE</th>
        </tr>
        <tr>
        <td>SPX (BULLISH)</td>
        <td>5100.25</td>
        <td>5250.75</td>
        <td>5175.50</td>
        </tr>
        <tr>
        <td>UST10Y (BEARISH)</td>
        <td>4.25</td>
        <td>4.50</td>
        <td>4.35</td>
        </tr>
        </table>
        </body>
        </html>
        """
        
        # Parse the sample data directly
        parsed_data = self.parse_direct_format(sample_data)
        
        if parsed_data:
            logger.info("Sample data parsing successful!")
            for item in parsed_data:
                logger.info(f"Ticker: {item['ticker']}, Buy: {item['buy_trade']}, Sell: {item['sell_trade']}")
            
            return True
        else:
            logger.error("Sample data parsing failed!")
            return False
    
    def test_with_real_email(self):
        """Test the extractor with a real email from the last 7 days"""
        try:
            logger.info("Testing with a real email from the last 7 days...")
            
            # Ensure MCP connection is active
            if not self.mcp_client.check_connection():
                logger.error("MCP connection is not available. Cannot proceed with test.")
                return False
            
            # Try to find an email from the last 7 days
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y/%m/%d')
            query = f'subject:"RISK RANGE" after:{seven_days_ago}'
            logger.info(f"Searching for RISK RANGE email with query: {query}")
            
            content = self.mcp_client.get_email_content(query)
            
            if not content:
                logger.warning("No RISK RANGE emails found in the last 7 days")
                return False
            
            logger.info(f"Found email content, length: {len(content)}")
            
            # Parse the content
            parsed_data = self.parse_content(content)
            
            if not parsed_data:
                logger.warning("Parsing returned no data")
                return False
            
            # Print the results
            logger.info(f"Successfully parsed {len(parsed_data)} records")
            for item in parsed_data[:5]:  # Show first 5 items
                logger.info(f"Ticker: {item['ticker']}, Buy: {item['buy_trade']}, Sell: {item['sell_trade']}")
            
            # Save to CSV
            self.save_to_csv(parsed_data)
            
            return True
        except Exception as e:
            logger.error(f"Error in test_with_real_email: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def cleanup_temp_files(self):
        """Clean up any temporary files created during extraction"""
        try:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / 'data'
            
            # List of temporary files to clean up
            temp_files = [
                data_dir / 'daily_email_raw.html',
                data_dir / 'daily_email_raw.txt',
                data_dir / 'daily_email_text.txt'
            ]
            
            for file_path in temp_files:
                if file_path.exists():
                    try:
                        # Comment out the actual deletion for safety
                        # file_path.unlink()
                        logger.debug(f"Would delete temporary file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Could not delete temporary file {file_path}: {e}")
            
            logger.debug("Temporary files cleanup completed")
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")


if __name__ == "__main__":
    logger.info(f"Starting daily extraction from Gmail via MCP at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    
    extractor = DailyExtractor()
    results = extractor.extract()
    
    if results:
        logger.info(f"Successfully extracted {len(results)} records")
        for item in results[:5]:  # Show first 5 items
            logger.info(f"Ticker: {item['ticker']}, Buy: {item['buy_trade']}, Sell: {item['sell_trade']}")
    else:
        logger.error("Extraction failed or returned no data")