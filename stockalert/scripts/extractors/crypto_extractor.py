import os
import sys
import json
import base64
import re
from pathlib import Path
from pydantic import BaseModel
import pandas as pd
from mistralai import Mistral, ImageURLChunk
from dotenv import load_dotenv
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
        mistral_api_key = get_env('MISTRAL_API_KEY')
        if not mistral_api_key:
            print("Warning: MISTRAL_API_KEY not found in environment variables.")
            print(f"Checked .env file at: {Path(__file__).parent.parent.parent.parent / '.env'}")
            print("Please ensure the .env file exists and contains MISTRAL_API_KEY.")
        
        # Initialize Mistral client
        self.mistral_client = Mistral(api_key=mistral_api_key)
        
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
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                data_url = f"data:image/png;base64,{image_base64}"
            
            # Process OCR to get markdown output
            print("Processing with Mistral OCR...")
            ocr_response = self.mistral_client.ocr.process(
                document=ImageURLChunk(image_url=data_url), 
                model="mistral-ocr-latest"
            )
            ocr_md = ocr_response.pages[0].markdown
            
            # Save the OCR text for debugging
            ocr_text_path = data_dir / 'crypto_ocr_text.md'
            with open(ocr_text_path, 'w', encoding='utf-8') as f:
                f.write(ocr_md)
            print(f"Saved OCR text to: {ocr_text_path}")
            
            # Print a sample of the OCR text for debugging
            print("\nSample OCR Text (first 500 chars):")
            print(ocr_md[:500])
            
            # First try to parse the OCR text directly
            crypto_assets = self.parse_ocr_text(ocr_md)
            
            if not crypto_assets or len(crypto_assets) < 3:  # If we couldn't extract enough assets
                print("Direct parsing extracted too few assets, using Mistral API for assistance...")
                # Prompt to convert OCR markdown to structured crypto JSON
                prompt = f"""
                Below is the OCR output in markdown format from cryptocurrency table images. There are two different table formats that need to be analyzed and extracted:

                1. "HEDGEYE RISK RANGES*" table - Contains crypto assets like BTC, ETH, SOL, AVAX, XRP, etc.
                   Format: Each asset has a header row with the ticker, followed by rows for TRADE (buy/sell values) and TREND (sentiment).
                   Example: 
                   ```
                   BTC
                   Duration | Buy Trade | Sell Trade
                   TRADE    | 80,012    | 93,968
                   TREND    | BEARISH
                   ```

                2. "DIRECT & DERIVATIVE EXPOSURES: RISK RANGE & TREND SIGNAL" table - Contains crypto-related assets like IBIT, MSTR, MARA, RIOT, ETHA, BLOK, COIN, BITO, etc.
                   Format: Table with columns for TICKER, Price, Buy Trade, Sell Trade, UPSIDE, DOWNSIDE, and TREND SIGNAL.
                   Example:
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
                
                # Get structured data from Mistral
                chat_response = self.mistral_client.chat.parse(
                    model="ministral-8b-latest",
                    messages=[{"role": "user", "content": prompt}],
                    response_format=CryptoData,
                    temperature=0
                )
                
                # Get the parsed data
                crypto_data = chat_response.choices[0].message.parsed
                
                # Convert to dictionary
                crypto_dict = crypto_data.model_dump()
                crypto_assets = crypto_dict["assets"]
            
            # Create CSV data with ticker mapping
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
            print(f"Saved crypto data to: {csv_path}")
            print(f"Total cryptocurrencies extracted: {len(csv_data)}")
            
            return crypto_assets
            
        except Exception as e:
            print(f"Error processing image: {e}")
            import traceback
            traceback.print_exc()
            return []

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
        elif "DIRECT & DERIVATIVE EXPOSURES" in ocr_text or "DIRECT & DERIVATIVE EXPOSURES" in ocr_text:
            print("Found EXPOSURES section")
            print("Parsing EXPOSURES section...")
            
            # Try to extract crypto assets from the exposures format
            # This is for crypto2.png format
            # The format is: TICKER | Price | Buy Trade | Sell Trade | UPSIDE | DOWNSIDE | TREND SIGNAL
            exposures_pattern = r'\|\s*(\w+)\s*\|\s*([\d\.]+)\s*\|\s*([\d\.]+)\s*\|\s*([\d\.]+)\s*\|\s*.*?\|\s*.*?\|\s*(\w+)\s*\|'
            matches = re.findall(exposures_pattern, ocr_text)
            
            if matches:
                for match in matches:
                    ticker, price, buy_trade, sell_trade, sentiment = match
                    assets.append({
                        "ticker": ticker,
                        "sentiment": sentiment,
                        "buy_trade": float(buy_trade),
                        "sell_trade": float(sell_trade),
                        "category": "digitalassets"
                    })
            
            # If the pattern didn't work, try a more relaxed approach
            if not assets:
                print("Trying alternative parsing approach...")
                # Find all rows in the table
                lines = ocr_text.split('\n')
                
                # Look for the header line to identify column positions
                header_line_idx = -1
                for i, line in enumerate(lines):
                    if "TICKER" in line and "Buy Trade" in line and "Sell Trade" in line and "TREND SIGNAL" in line:
                        header_line_idx = i
                        break
                    elif "TICKER" in line and "Price" in line:
                        # This might be the first part of a split header
                        if i+1 < len(lines) and "Buy Trade" in lines[i+1] and "Sell Trade" in lines[i+1]:
                            header_line_idx = i
                            break
                
                if header_line_idx >= 0:
                    # Process data rows after the header
                    for i in range(header_line_idx + 2, len(lines)):
                        line = lines[i].strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        # Try to parse the row data
                        # Format: | TICKER | Price | Buy Trade | Sell Trade | UPSIDE | DOWNSIDE | TREND SIGNAL |
                        row_match = re.search(r'\|\s*(\w+)\s*\|\s*([\d\.]+)\s*\|\s*([\d\.]+)\s*\|\s*([\d\.]+)', line)
                        sentiment_match = re.search(r'(BULLISH|BEARISH)', line)
                        
                        if row_match:
                            ticker = row_match.group(1)
                            # Correctly identify columns: price is column 2, buy_trade is column 3, sell_trade is column 4
                            price = float(row_match.group(2))
                            buy_trade = float(row_match.group(3))
                            sell_trade = float(row_match.group(4))
                            sentiment = sentiment_match.group(1) if sentiment_match else "BEARISH"  # Default to BEARISH if not found
                            
                            print(f"Alt method: Extracted {ticker}, sentiment: {sentiment}, buy: {buy_trade}, sell: {sell_trade}")
                            assets.append({
                                "ticker": ticker,
                                "sentiment": sentiment,
                                "buy_trade": buy_trade,
                                "sell_trade": sell_trade,
                                "category": "digitalassets"
                            })
        
        print(f"Parsed {len(assets)} assets from OCR text")
        return assets

    def extract_from_local_images(self):
        """Extract crypto data directly from local image files"""
        print(f"Starting crypto extraction from local images at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
        
        # Define the path to the local images
        project_root = Path(__file__).parent.parent.parent
        data_dir = project_root / 'data'
        
        # Process both crypto images and combine results
        all_crypto_assets = []
        
        # Process crypto1.png
        crypto1_path = data_dir / 'crypto1.png'
        if os.path.exists(crypto1_path):
            print(f"Processing crypto image 1: {crypto1_path}")
            crypto_assets1 = self.process_local_image(crypto1_path)
            all_crypto_assets.extend(crypto_assets1)
            print(f"Extracted {len(crypto_assets1)} assets from crypto image 1")
        
        # Process crypto2.png
        crypto2_path = data_dir / 'crypto2.png'
        if os.path.exists(crypto2_path):
            print(f"Processing crypto image 2: {crypto2_path}")
            crypto_assets2 = self.process_local_image(crypto2_path)
            all_crypto_assets.extend(crypto_assets2)
            print(f"Extracted {len(crypto_assets2)} assets from crypto image 2")
        
        # If we found any crypto assets, save them to CSV
        if all_crypto_assets:
            # Apply ticker mappings before saving to CSV
            mapped_assets = []
            for asset in all_crypto_assets:
                mapped_asset = asset.copy()
                # Apply ticker mapping if available
                mapped_asset['ticker'] = self.ticker_mappings.get(asset['ticker'], asset['ticker'])
                mapped_assets.append(mapped_asset)
            
            # Create DataFrame and save to CSV
            df = pd.DataFrame(mapped_assets)
            csv_path = data_dir / 'digitalassets.csv'
            df.to_csv(csv_path, index=False)
            
            # Print summary
            print("Crypto Extraction Summary:")
            print(f"Total cryptocurrencies: {len(df)}")
            print(f"BULLISH: {len(df[df['sentiment'] == 'BULLISH'])}")
            print(f"BEARISH: {len(df[df['sentiment'] == 'BEARISH'])}")
            
            # Print CSV location
            print(f"CSV saved to: {csv_path}")
            
            # Clean up temporary files
            self.cleanup_temp_files(data_dir)
            
            return all_crypto_assets
        else:
            print("No crypto assets found in the local images.")
            return []

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