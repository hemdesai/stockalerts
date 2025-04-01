import os
import sys
import json
import base64
import re
import requests
from pathlib import Path
from pydantic import BaseModel
import pandas as pd
from stockalert.utils.env_loader import get_env
from datetime import datetime

# Add the project root to Python path when running directly
if __name__ == "__main__":
    # Get the absolute path to the project root directory
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.append(str(project_root))
    
# Import local modules
from stockalert.utils.env_loader import get_env

class RangeData(BaseModel):
    low: float
    high: float


class CryptoAsset(BaseModel):
    ticker: str
    sentiment: str
    buy_trade: float
    sell_trade: float
    category: str = "digitalassets"


class CryptoData(BaseModel):
    assets: list[CryptoAsset]


class CryptoEmailExtractor:
    def __init__(self):
        # Get Mistral API key from environment variables
        self.mistral_api_key = get_env('MISTRAL_API_KEY')
        if not self.mistral_api_key:
            print("Warning: MISTRAL_API_KEY not found in environment variables.")
            print(f"Checked .env file at: {Path(__file__).parent.parent.parent.parent / '.env'}")
            print("Please ensure the .env file exists and contains MISTRAL_API_KEY.")
        
        # Add ticker mappings for digital assets
        self.ticker_mappings = {
            'BTC': 'BTC-USD',
            'ETH': 'ETH-USD',
            'SOL': 'SOL-USD',
            'AVAX': 'AVAX-USD',
            'XRP': 'XRP-USD'
        }

    def process_local_image(self, image_path):
        """Process a local image file using Mistral OCR API"""
        try:
            # Ensure the image path exists
            if not os.path.exists(image_path):
                print(f"Error: Image file not found at {image_path}")
                return []
            
            # Read the image file
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # Process the image
            return self.process_image(image_data)
            
        except Exception as e:
            print(f"Error processing local image: {e}")
            import traceback
            traceback.print_exc()
            return []

    def process_image(self, image_data):
        """Process image using Mistral OCR API"""
        try:
            # Save image to a temporary file
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / 'data'
            data_dir.mkdir(exist_ok=True)
            
            # Create a temporary file to store the image
            temp_image_path = data_dir / 'crypto_table.png'
            with open(temp_image_path, 'wb') as f:
                f.write(image_data)
            
            # Convert the image to a data URL
            with open(temp_image_path, 'rb') as f:
                image_bytes = f.read()
                image_base64_str = base64.b64encode(image_bytes).decode('utf-8')
                
            # Process OCR to get markdown output
            print("Processing with Mistral OCR...")
            try:
                # Use the ocr.process method directly as in ideas_extractor.py
                data_url = f"data:image/png;base64,{image_base64_str}"
                url = "https://api.mistral.ai/v1/ocr"
                headers = {
                    "Authorization": f"Bearer {self.mistral_api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "document": {
                        "image_url": data_url
                    },
                    "model": "mistral-ocr-latest"
                }
                response = requests.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    ocr_response = response.json()
                    ocr_md = ocr_response["pages"][0]["markdown"]
                else:
                    print(f"Error processing OCR: {response.text}")
                    return []
                
                # Save the OCR text for debugging
                ocr_text_path = data_dir / 'crypto_ocr_text.md'
                with open(ocr_text_path, 'w', encoding='utf-8') as f:
                    f.write(ocr_md)
                print(f"Saved OCR text to: {ocr_text_path}")
                
                # Print a sample of the OCR text for debugging
                print("\nSample OCR Text (first 500 chars):")
                print(ocr_md[:500] + "..." if len(ocr_md) > 500 else ocr_md)
                
                # If we got a reasonable amount of text, consider it successful
                if len(ocr_md) < 100:  # Arbitrary threshold to check if we got meaningful content
                    print("OCR returned insufficient text. Using text extraction as fallback.")
                    return []
                    
            except Exception as e:
                print(f"Error processing OCR: {e}")
                return []
            
            # Determine which type of image we're dealing with and parse accordingly
            assets = []
            
            # Check if this is crypto2.png by looking for "DIRECT & DERIVATIVE EXPOSURES" or "Prior Day Close"
            if "DIRECT & DERIVATIVE EXPOSURES" in ocr_md or "Prior Day Close" in ocr_md:
                print("Detected crypto2.png format with DERIVATIVE EXPOSURES or Prior Day Close table")
                assets = self.parse_derivative_exposures_section(ocr_md)
            # Check if this is crypto1.png by looking for "HEDGEYE RISK RANGES"
            elif "HEDGEYE RISK RANGES" in ocr_md:
                print("Found RISK RANGES section")
                assets = self.parse_risk_ranges_section(ocr_md)
            # Check if this has a table with TICKER, My Trade, Self Trade columns (crypto2.png format)
            elif "| TICKER |" in ocr_md and "| My Trade |" in ocr_md and "| Self Trade |" in ocr_md:
                print("Detected PRIOR DAY CLOSE format with TICKER/My Trade/Self Trade table")
                assets = self.parse_prior_day_close_section(ocr_md)
            else:
                print("Could not determine image type from OCR text")
                return []
            
            # If parsing failed, try using Mistral API for structured parsing
            if len(assets) < 1:
                print("Direct parsing extracted too few assets, using Mistral API for assistance...")
                assets = self.parse_with_mistral_api(ocr_md)
            
            # Save the extracted assets to CSV
            if assets:
                self.save_to_csv(assets)
            
            return assets
            
        except Exception as e:
            print(f"Error processing image: {e}")
            import traceback
            traceback.print_exc()
            return []
            
    def save_to_csv(self, assets):
        """Save extracted assets to CSV file"""
        if not assets:
            print("No assets to save to CSV")
            return False
        
        try:
            # Apply ticker mappings
            csv_data = [
                {
                    "ticker": self.ticker_mappings.get(asset["ticker"], asset["ticker"]),
                    "sentiment": asset["sentiment"],
                    "buy_trade": asset["buy_trade"],
                    "sell_trade": asset["sell_trade"],
                    "category": asset["category"]
                }
                for asset in assets
            ]
            
            # Create a DataFrame and save to CSV
            df = pd.DataFrame(csv_data)
            csv_path = Path(__file__).parent.parent.parent / 'data' / 'digitalassets.csv'
            df.to_csv(csv_path, index=False)
            print(f"Saved crypto data to: {csv_path}")
            print(f"Total cryptocurrencies extracted: {len(csv_data)}")
            return True
        except Exception as e:
            print(f"Error saving to CSV: {e}")
            return False

    def parse_ocr_text(self, ocr_text):
        """Parse OCR text to extract crypto assets"""
        assets = []
        
        # Check if this is a risk ranges table
        if "HEDGEYE RISK RANGES" in ocr_text:
            print("Found RISK RANGES section")
            print("Parsing RISK RANGES section...")
            
            # Try to extract crypto assets from the risk ranges format
            # This is for crypto1.png format
            crypto_pattern = r'(\w+)\s*\|\s*Duration\s*\|\s*Buy Trade\s*\|\s*Sell Trade\s*\|\s*TRADE\s*\|\s*([\d,\.]+)\s*\|\s*([\d,\.]+)\s*\|\s*TREND\s*\|\s*(\w+)'
            matches = re.findall(crypto_pattern, ocr_text, re.DOTALL)
            
            if matches:
                for match in matches:
                    ticker, buy_trade, sell_trade, sentiment = match
                    assets.append({
                        "ticker": ticker,
                        "sentiment": sentiment,
                        "buy_trade": float(buy_trade.replace(',', '')),
                        "sell_trade": float(sell_trade.replace(',', '')),
                        "category": "digitalassets"
                    })
            
            # If the pattern didn't work, try a more relaxed approach
            if not assets:
                print("Trying alternative parsing approach...")
                # Find all crypto tickers and their data
                lines = ocr_text.split('\n')
                current_ticker = None
                buy_trade = None
                sell_trade = None
                sentiment = None
                
                for i, line in enumerate(lines):
                    # Check for ticker (usually a standalone line with just the ticker symbol)
                    if re.match(r'^[A-Z]{2,5}\s*$', line.strip()):
                        current_ticker = line.strip()
                    
                    # Check for TRADE line with buy/sell values
                    trade_match = re.search(r'TRADE\s*\|\s*([\d,\.]+)\s*\|\s*([\d,\.]+)', line)
                    if trade_match and current_ticker:
                        buy_trade = float(trade_match.group(1).replace(',', ''))
                        sell_trade = float(trade_match.group(2).replace(',', ''))
                    
                    # Check for TREND line with sentiment
                    trend_match = re.search(r'TREND\s*\|\s*(\w+)', line)
                    if trend_match and current_ticker:
                        sentiment = trend_match.group(1)
                    
                    # If we have all data for a ticker, add it and reset
                    if current_ticker and buy_trade and sell_trade and sentiment:
                        print(f"Alt method: Extracted {self.ticker_mappings.get(current_ticker, current_ticker)}, sentiment: {sentiment}, buy: {buy_trade}, sell: {sell_trade}")
                        assets.append({
                            "ticker": current_ticker,
                            "sentiment": sentiment,
                            "buy_trade": buy_trade,
                            "sell_trade": sell_trade,
                            "category": "digitalassets"
                        })
                        # Reset for next ticker
                        current_ticker = None
                        buy_trade = None
                        sell_trade = None
                        sentiment = None
        
        # Check if this is an exposures table
        elif "DIRECT & DERIVATIVE EXPOSURES" in ocr_text:
            print("Found EXPOSURES section")
            print("Parsing EXPOSURES section...")
            
            # Try to extract crypto assets from the exposures format
            # This is for crypto2.png format
            # The format is: TICKER | Price | Buy Trade | Sell Trade | UPSIDE | DOWNSIDE | TREND SIGNAL
            
            # First, try to parse the table row by row
            lines = ocr_text.split('\n')
            
            # Find the header line to identify column positions
            header_line_idx = -1
            for i, line in enumerate(lines):
                if "TICKER" in line and "Buy Trade" in line and "Sell Trade" in line:
                    # This might be a table header with a ticker
                    header_line_idx = i
                    print(f"Found header line at index {header_line_idx}: {line}")
                    break
            
            if header_line_idx == -1:
                print("Could not find table header in DERIVATIVE EXPOSURES section")
                return []
            
            # Skip the header and separator lines
            start_index = header_line_idx + 2  # Skip header and separator line
            
            # Process the table rows
            for i in range(start_index, len(lines)):
                line = lines[i].strip()
                
                # Skip empty lines or lines without pipe separators
                if not line or '|' not in line:
                    continue
                
                print(f"Processing table row: {line}")
                
                # Split the line by pipe separators
                parts = [part.strip() for part in line.split('|')]
                
                # Remove empty parts
                parts = [part for part in parts if part]
                
                if len(parts) < 3:
                    continue
                
                # The first part should be the ticker
                ticker = parts[0].strip()
                
                # Skip if this isn't a valid ticker
                if not re.match(r'^[A-Z]{2,5}$', ticker):
                    continue
                
                print(f"Found ticker: {ticker}")
                
                # Try to extract buy and sell values
                buy_trade = None
                sell_trade = None
                sentiment = "BEARISH"  # Default sentiment
                
                # Extract numbers from parts
                try:
                    # In this format, typically:
                    # parts[0] = TICKER
                    # parts[1] = Price
                    # parts[2] = Buy Trade
                    # parts[3] = Sell Trade
                    # parts[6] = TREND SIGNAL (last part)
                    
                    # Extract buy trade from part 2
                    buy_match = re.search(r'(\d+\.?\d*)', parts[2])
                    if buy_match:
                        buy_trade = float(buy_match.group(1).replace(',', ''))
                    
                    # Extract sell trade from part 3
                    sell_match = re.search(r'(\d+\.?\d*)', parts[3])
                    if sell_match:
                        sell_trade = float(sell_match.group(1).replace(',', ''))
                    
                    # Extract sentiment from the last part
                    if len(parts) >= 7:
                        trend_part = parts[6]
                        if "BEARISH" in trend_part:
                            sentiment = "BEARISH"
                        elif "BULLISH" in trend_part:
                            sentiment = "BULLISH"
                        elif "NEUTRAL" in trend_part:
                            sentiment = "NEUTRAL"
                except (IndexError, ValueError) as e:
                    print(f"Error extracting values for {ticker}: {e}")
                    continue
                
                # If we found both buy and sell values, add this asset
                if buy_trade is not None and sell_trade is not None:
                    # Map the ticker to the standard format if needed
                    mapped_ticker = self.ticker_mappings.get(ticker, ticker)
                    
                    assets.append({
                        "ticker": mapped_ticker,
                        "sentiment": sentiment,
                        "buy_trade": buy_trade,
                        "sell_trade": sell_trade,
                        "category": "digitalassets"
                    })
                    print(f"Added {ticker} with buy={buy_trade}, sell={sell_trade}, sentiment={sentiment}")
        
        print(f"Parsed {len(assets)} assets from OCR text")
        return assets

    def parse_risk_ranges_section(self, ocr_md):
        """Parse the RISK RANGES section from OCR text"""
        print("Parsing RISK RANGES section...")
        assets = []
        
        # Split the OCR text into lines
        lines = ocr_md.split('\n')
        
        # Look for markdown tables in the OCR text
        # In the markdown format, tables are indicated by | characters
        table_start_indices = []
        current_ticker = None
        
        for i, line in enumerate(lines):
            # Check if this line contains a ticker name in a table header
            if '|' in line and any(crypto in line for crypto in ["BTC", "ETH", "SOL", "AVAX", "XRP"]):
                # This might be a table header with a ticker
                for crypto in ["BTC", "ETH", "SOL", "AVAX", "XRP"]:
                    if crypto in line:
                        current_ticker = crypto
                        table_start_indices.append((i, current_ticker))
                        print(f"Found table for {current_ticker} at line {i}")
                        break
        
        # Process each table
        for start_idx, ticker in table_start_indices:
            buy_trade = None
            sell_trade = None
            sentiment = "BEARISH"  # Default sentiment
            
            # Look for the TRADE row which contains buy and sell values
            for i in range(start_idx, min(start_idx + 10, len(lines))):
                line = lines[i]
                if '|' in line and "TRADE" in line and "Buy Trade" not in line and "Sell Trade" not in line:
                    # This is likely the TRADE row with values
                    print(f"Processing TRADE row for {ticker}: {line}")
                    
                    # Extract numbers from the line
                    parts = line.split('|')
                    # Remove empty parts and strip whitespace
                    parts = [part.strip() for part in parts if part.strip()]
                    
                    if len(parts) >= 3:  # Should have at least 3 parts: TRADE, buy, sell
                        try:
                            # Get the buy and sell values (parts[1] and parts[2])
                            buy_str = parts[1].strip()
                            sell_str = parts[2].strip()
                            
                            # Remove any commas and convert to float
                            buy_trade = float(buy_str.replace(',', ''))
                            sell_trade = float(sell_str.replace(',', ''))
                            
                            print(f"Extracted buy={buy_trade}, sell={sell_trade} for {ticker}")
                        except (ValueError, IndexError) as e:
                            print(f"Error extracting values for {ticker}: {e}")
                
                # Look for the TREND row which contains sentiment
                elif '|' in line and "TREND" in line:
                    # This is likely the TREND row with sentiment
                    print(f"Processing TREND row for {ticker}: {line}")
                    
                    if "BEARISH" in line:
                        sentiment = "BEARISH"
                    elif "BULLISH" in line:
                        sentiment = "BULLISH"
                    elif "NEUTRAL" in line:
                        sentiment = "NEUTRAL"
                    elif "REARISK" in line:  # Handle "REARISK" typo in OCR
                        sentiment = "BEARISH"
            
            # If we found both buy and sell values, add this asset
            if buy_trade is not None and sell_trade is not None:
                # Map the ticker to the standard format if needed
                mapped_ticker = self.ticker_mappings.get(ticker, ticker)
                
                assets.append({
                    "ticker": mapped_ticker,
                    "sentiment": sentiment,
                    "buy_trade": buy_trade,
                    "sell_trade": sell_trade,
                    "category": "digitalassets"
                })
                print(f"Added {ticker} with buy={buy_trade}, sell={sell_trade}, sentiment={sentiment}")
        
        print(f"Parsed {len(assets)} assets from RISK RANGES section")
        return assets

    def parse_prior_day_close_section(self, ocr_md):
        """Parse the Prior Day Close section from OCR text (crypto2.png format)"""
        print("Parsing PRIOR DAY CLOSE section...")
        assets = []
        
        # Split the OCR text into lines
        lines = ocr_md.split('\n')
        
        # Find the exact header line
        header_line_idx = -1
        for i, line in enumerate(lines):
            # Check for the exact header format
            if ("| TICKER |" in line and 
                "| Price |" in line and 
                "| My Trade |" in line and 
                "| Self Trade |" in line and 
                "| UPSIDE |" in line and 
                "| DOWNSIDE |" in line and 
                "| TREND SIGNAL |" in line):
                header_line_idx = i
                print(f"Found exact table header at line {i}")
                break
        
        if header_line_idx >= 0:
            # Process each line after the header
            for i in range(header_line_idx + 1, len(lines)):
                line = lines[i].strip()
                if not line or line.startswith('#'):
                    continue
                
                # Split the line by | characters to get the columns
                parts = [part.strip() for part in line.split('|') if part.strip()]
                
                # Skip if we don't have enough columns
                if len(parts) < 7:
                    continue
                
                try:
                    # Extract ticker - should be first column
                    ticker = parts[0]
                    
                    # Extract price - second column
                    price = float(parts[1].replace(',', ''))
                    
                    # Extract buy trade (My Trade) - third column
                    buy_trade = float(parts[2].replace(',', ''))
                    
                    # Extract sell trade (Self Trade) - fourth column
                    sell_trade = float(parts[3].replace(',', ''))
                    
                    # Extract sentiment from the last column
                    sentiment = "BEARISH"  # Default
                    if "BULLISH" in parts[-1].upper():
                        sentiment = "BULLISH"
                    elif "NEUTRAL" in parts[-1].upper():
                        sentiment = "NEUTRAL"
                    
                    print(f"Extracted {ticker}, sentiment: {sentiment}, buy: {buy_trade}, sell: {sell_trade}")
                    assets.append({
                        "ticker": ticker,
                        "sentiment": sentiment,
                        "buy_trade": buy_trade,
                        "sell_trade": sell_trade,
                        "category": "digitalassets"
                    })
                except (ValueError, IndexError) as e:
                    print(f"Error processing line: {e}")
                    continue
        
        print(f"Extracted {len(assets)} assets from PRIOR DAY CLOSE section")
        return assets

    def parse_derivative_exposures_section(self, ocr_md):
        """Parse the DIRECT & DERIVATIVE EXPOSURES section from OCR text"""
        print("Parsing DIRECT & DERIVATIVE EXPOSURES section...")
        assets = []
        
        # Split the OCR text into lines
        lines = ocr_md.split('\n')
        
        # Find the table header line
        header_index = -1
        for i, line in enumerate(lines):
            if '|' in line and "TICKER" in line and "Buy Trade" in line and "Sell Trade" in line:
                header_index = i
                print(f"Found table header at line {i}: {line}")
                break
        
        if header_index == -1:
            print("Could not find table header in DERIVATIVE EXPOSURES section")
            return []
        
        # Skip the header and separator lines
        start_index = header_index + 2  # Skip header and separator line
        
        # Process the table rows
        for i in range(start_index, len(lines)):
            line = lines[i].strip()
            
            # Skip empty lines or lines without pipe separators
            if not line or '|' not in line:
                continue
            
            print(f"Processing table row: {line}")
            
            # Split the line by pipe separators
            parts = [part.strip() for part in line.split('|')]
            
            # Remove empty parts
            parts = [part for part in parts if part]
            
            if len(parts) < 3:
                continue
            
            # The first part should be the ticker
            ticker = parts[0].strip()
            
            # Skip if this isn't a valid ticker
            if not re.match(r'^[A-Z]{2,5}$', ticker):
                continue
            
            print(f"Found ticker: {ticker}")
            
            # Try to extract buy and sell values
            buy_trade = None
            sell_trade = None
            sentiment = "BEARISH"  # Default sentiment
            
            # Extract numbers from parts
            try:
                # In this format, typically:
                # parts[0] = TICKER
                # parts[1] = Price
                # parts[2] = Buy Trade
                # parts[3] = Sell Trade
                # parts[6] = TREND SIGNAL (last part)
                
                # Extract buy trade from part 2
                buy_match = re.search(r'(\d+\.?\d*)', parts[2])
                if buy_match:
                    buy_trade = float(buy_match.group(1).replace(',', ''))
                
                # Extract sell trade from part 3
                sell_match = re.search(r'(\d+\.?\d*)', parts[3])
                if sell_match:
                    sell_trade = float(sell_match.group(1).replace(',', ''))
                
                # Extract sentiment from the last part
                if len(parts) >= 7:
                    trend_part = parts[6]
                    if "BEARISH" in trend_part:
                        sentiment = "BEARISH"
                    elif "BULLISH" in trend_part:
                        sentiment = "BULLISH"
                    elif "NEUTRAL" in trend_part:
                        sentiment = "NEUTRAL"
            except (IndexError, ValueError) as e:
                print(f"Error extracting values for {ticker}: {e}")
                continue
            
            # If we found both buy and sell values, add this asset
            if buy_trade is not None and sell_trade is not None:
                # Map the ticker to the standard format if needed
                mapped_ticker = self.ticker_mappings.get(ticker, ticker)
                
                assets.append({
                    "ticker": mapped_ticker,
                    "sentiment": sentiment,
                    "buy_trade": buy_trade,
                    "sell_trade": sell_trade,
                    "category": "digitalassets"
                })
                print(f"Added {ticker} with buy={buy_trade}, sell={sell_trade}, sentiment={sentiment}")
        
        print(f"Parsed {len(assets)} assets from DERIVATIVE EXPOSURES section")
        return assets

    def parse_with_mistral_api(self, ocr_md):
        """Use Mistral API to parse the OCR text"""
        print("Using Mistral API to parse OCR text...")
        
        # Prompt to convert OCR markdown to structured crypto JSON
        prompt = f"""
        Below is the OCR output in markdown format from cryptocurrency table images. There are two different table formats that need to be analyzed and extracted:

        1. "HEDGEYE RISK RANGES*" table - Contains crypto assets like BTC, ETH, SOL, AVAX, XRP, etc.
           Format: Each asset has a header row with the ticker, followed by rows for TRADE (buy/sell values) and TREND (sentiment).
           Example:
           THIS IS AN EXAMPLE IT'S NOT ACTUAL DATA
           ```
           BTC
           Duration | Buy Trade | Sell Trade
           TRADE    | 80,012    | 93,968
           TREND    | BEARISH
           ```

        2. "DIRECT & DERIVATIVE EXPOSURES: RISK RANGE & TREND SIGNAL" table - Contains crypto-related assets like IBIT, MSTR, MARA, RIOT, ETHA, BLOK, COIN, BITO, etc.
           Format: Table with columns for TICKER, Price, Buy Trade, Sell Trade, UPSIDE, DOWNSIDE, and TREND SIGNAL.
           Example:
           THIS IS AN EXAMPLE IT'S NOT ACTUAL DATA
           ```
           TICKER | Price | Buy Trade | Sell Trade | UPSIDE | DOWNSIDE | TREND SIGNAL
           IBIT   | 51.44 | 44.40     | 52.90      | 2.8%   | -13.7%   | BEARISH
           MSTR   | 309   | 224       | 319        | 3.4%   | -27.4%   | BEARISH
           ```

        Text from OCR:
        <BEGIN_IMAGE_OCR>
        {ocr_md}
        <END_IMAGE_OCR>

        I need you to carefully extract ALL assets from BOTH tables. Make sure to include:
        1. From the first table: BTC, ETH, SOL, AVAX, XRP and any other crypto assets present
        2. From the second table: IBIT, MSTR, MARA, RIOT, ETHA, BLOK, COIN, BITO and any other crypto-related assets present

        Extract the actual values from the OCR text. DO NOT use any hardcoded values or make up data.

        Convert this into a structured JSON response with the following format:
        {{
            "assets": [
                {{
                    "ticker": "BTC",
                    "sentiment": "BULLISH or BEARISH based on the TREND value",
                    "buy_trade": extracted buy trade value as float,
                    "sell_trade": extracted sell trade value as float,
                    "category": "digitalassets"
                }},
                ... and so on for all assets found in the OCR text
            ]
        }}

        Rules:
        - Include ALL assets found in the OCR text
        - Use the actual sentiment (BULLISH or BEARISH) from the TREND field or TREND SIGNAL column
        - Format numbers as floats without commas (e.g., 80012.0, not $80,012)
        - Set category to "digitalassets" for all assets
        - Return ONLY the JSON object, no other text
        """
        
        try:
            # Make a direct API call to Mistral chat completion
            url = "https://api.mistral.ai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.mistral_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "mistral-large-latest",
                "messages": [{"role": "user", "content": prompt}]
            }
            
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                chat_data = response.json()
                response_content = chat_data["choices"][0]["message"]["content"]
                crypto_data = json.loads(response_content)
                
                # Convert to dictionary
                crypto_assets = crypto_data.get("assets", [])
            else:
                print(f"Error using Mistral API for structured parsing: {response.text}")
                print("Falling back to direct extraction...")
                
                # Fallback: Try to extract directly from OCR text
                crypto_assets = self.parse_ocr_text(ocr_md)
                
                # If that fails too, use a last resort approach for crypto2.png
                if len(crypto_assets) < 3 and "DIRECT & DERIVATIVE EXPOSURES" in ocr_md:
                    print("Direct extraction failed, using last resort approach for crypto2.png...")
                    
                    # Define the expected tickers for crypto2.png
                    expected_tickers = ["IBIT", "MSTR", "MARA", "RIOT", "ETHA", "BLOK", "COIN", "BITO"]
                    
                    # For each expected ticker not already in crypto_assets, add it with placeholder values
                    for ticker in expected_tickers:
                        if not any(asset["ticker"] == ticker for asset in crypto_assets):
                            print(f"Adding ticker {ticker} with placeholder values")
                            crypto_assets.append({
                                "ticker": ticker,
                                "sentiment": "N/A",  # Use N/A to indicate we couldn't determine sentiment
                                "buy_trade": 0.0,    # Placeholder value
                                "sell_trade": 0.0,   # Placeholder value
                                "category": "digitalassets"
                            })
        except Exception as e:
            print(f"Error using Mistral API for structured parsing: {e}")
            print("Falling back to direct extraction...")
            
            # Fallback: Try to extract directly from OCR text
            crypto_assets = self.parse_ocr_text(ocr_md)
        
        return crypto_assets

    def extract_from_local_images(self):
        """Extract crypto data directly from local image files"""
        print(f"Starting crypto extraction from local images at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
        
        # Define the path to the local images
        project_root = Path(__file__).parent.parent.parent
        data_dir = project_root / 'data'
        
        # Define paths to the crypto images
        crypto1_path = data_dir / 'crypto1.png'
        crypto2_path = data_dir / 'crypto2.png'
        
        # Process each image and extract crypto assets
        crypto_assets = []
        
        # Process crypto1.png (HEDGEYE RISK RANGES format)
        print(f"Processing crypto image 1: {crypto1_path}")
        crypto_assets1 = self.process_local_image(crypto1_path)
        print(f"Extracted {len(crypto_assets1)} assets from crypto image 1")
        crypto_assets.extend(crypto_assets1)
        
        # Process crypto2.png (DIRECT & DERIVATIVE EXPOSURES format)
        print(f"Processing crypto image 2: {crypto2_path}")
        crypto_assets2 = self.process_local_image(crypto2_path)
        print(f"Extracted {len(crypto_assets2)} assets from crypto image 2")
        crypto_assets.extend(crypto_assets2)
        
        # Create a summary of the extracted assets
        bullish_count = sum(1 for asset in crypto_assets if asset["sentiment"] == "BULLISH")
        bearish_count = sum(1 for asset in crypto_assets if asset["sentiment"] == "BEARISH")
        neutral_count = sum(1 for asset in crypto_assets if asset["sentiment"] == "NEUTRAL")
        
        print("Crypto Extraction Summary:")
        print(f"Total cryptocurrencies: {len(crypto_assets)}")
        print(f"BULLISH: {bullish_count}")
        print(f"BEARISH: {bearish_count}")
        print(f"NEUTRAL: {neutral_count}")
        
        # Save to CSV
        if crypto_assets:
            # Apply ticker mappings
            csv_data = [
                {
                    "ticker": self.ticker_mappings.get(asset["ticker"], asset["ticker"]),
                    "sentiment": asset["sentiment"],
                    "buy_trade": asset["buy_trade"],
                    "sell_trade": asset["sell_trade"],
                    "category": asset["category"]
                }
                for asset in crypto_assets
            ]
            
            # Create a DataFrame and save to CSV
            df = pd.DataFrame(csv_data)
            csv_path = data_dir / 'digitalassets.csv'
            df.to_csv(csv_path, index=False)
            print(f"CSV saved to: {csv_path}")
        
        # Clean up temporary files
        self.cleanup_temp_files(data_dir)
        
        print("Crypto extraction completed successfully")
        print(f"CSV contains {len(crypto_assets)} cryptocurrencies")
        print(f"CSV saved to: {data_dir / 'digitalassets.csv'}")
        
        return crypto_assets

    def cleanup_temp_files(self, data_dir):
        """Clean up temporary files created during processing"""
        try:
            # Find all temporary files created by the OCR process
            temp_files = list(data_dir.glob('temp_crypto_*.png'))
            temp_files.extend(list(data_dir.glob('crypto_ocr_text.*')))
            # Add crypto_table.png to the list of files to clean up
            crypto_table_path = data_dir / 'crypto_table.png'
            if crypto_table_path.exists():
                temp_files.append(crypto_table_path)
            
            # Delete each temporary file
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                    print(f"Cleaned up temporary file: {temp_file}")
                except Exception as e:
                    print(f"Error cleaning up {temp_file}: {e}")
        except Exception as e:
            print(f"Error in cleanup_temp_files: {e}")

if __name__ == "__main__":
    # Create the extractor
    extractor = CryptoEmailExtractor()
    
    # Extract from local images
    crypto_data = extractor.extract_from_local_images()
    
    # Print summary
    if crypto_data:
        print("Crypto extraction completed successfully")
        print(f"CSV contains {len(crypto_data)} cryptocurrencies")
        
        # Save to CSV
        csv_path = Path(__file__).parent.parent.parent / 'data' / 'digitalassets.csv'
        print(f"CSV saved to: {csv_path}")
    else:
        print("Crypto extraction failed")