import os
import sys
import json
import base64
import re
import requests
from pathlib import Path
from pydantic import BaseModel
import pandas as pd
from datetime import datetime

# Add project root to path when running directly
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.append(str(project_root))
    from stockalert.utils.env_loader import get_env
else:
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
        self.mistral_api_key = get_env('MISTRAL_API_KEY')
        if not self.mistral_api_key:
            print("Warning: MISTRAL_API_KEY not found in environment variables.")
            print(f"Checked .env file at: {Path(__file__).parent.parent.parent.parent / '.env'}")
            print("Please ensure the .env file exists and contains MISTRAL_API_KEY.")
        self.ticker_mappings = {
            'BTC': 'BTC-USD',
            'ETH': 'ETH-USD',
            'SOL': 'SOL-USD',
            'AVAX': 'AVAX-USD',
            'AAVE': 'AAVE-USD'
        }

    def process_local_image(self, image_path):
        if not os.path.exists(image_path):
            print(f"Error: Image file not found at {image_path}")
            return []
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            return self.process_image(image_data)
        except Exception as e:
            print(f"Error processing local image: {e}")
            return []

    def process_image(self, image_data):
        try:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / 'data'
            data_dir.mkdir(exist_ok=True)
            temp_image_path = data_dir / 'crypto_table.png'
            with open(temp_image_path, 'wb') as f:
                f.write(image_data)
            with open(temp_image_path, 'rb') as f:
                image_bytes = f.read()
            image_base64_str = base64.b64encode(image_bytes).decode('utf-8')
            print("Processing with Mistral OCR...")
            data_url = f"data:image/png;base64,{image_base64_str}"
            url = "https://api.mistral.ai/v1/ocr"
            headers = {
                "Authorization": f"Bearer {self.mistral_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "document": {"image_url": data_url},
                "model": "mistral-ocr-latest"
            }
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                ocr_response = response.json()
                ocr_md = ocr_response["pages"][0]["markdown"]
            else:
                print(f"Error processing OCR: {response.text}")
                return []
            ocr_text_path = data_dir / 'crypto_ocr_text.md'
            with open(ocr_text_path, 'w', encoding='utf-8') as f:
                f.write(ocr_md)
            print(f"Saved OCR text to: {ocr_text_path}")
            print("\nSample OCR Text (first 500 chars):")
            print(ocr_md[:500] + "..." if len(ocr_md) > 500 else ocr_md)

            assets = []
            # More flexible detection patterns
            has_derivative_format = any([
                "DIRECT & DERIVATIVE EXPOSURES" in ocr_md,
                "Prior Day Close" in ocr_md,
                "TICKER" in ocr_md and "Buy Trade" in ocr_md and "TREND SIGNAL" in ocr_md,
                # LaTeX formatted headers detection
                r"\begin{gathered}" in ocr_md and "Buy Trade" in ocr_md and "TREND SIGNAL" in ocr_md
            ])
            
            if has_derivative_format:
                print("Detected crypto2.png format with derivative exposures table")
                assets = self.parse_derivative_exposures_section(ocr_md)
            else:
                print("Detected crypto1.png format with risk ranges")
                assets = self.parse_risk_ranges_section(ocr_md)
                
            # If direct parsing failed, try using Mistral API for structured extraction
            if not assets:
                print("Direct parsing failed, trying Mistral API for structured extraction...")
                assets = self.parse_with_mistral_api(ocr_md)
                
            return assets
        except Exception as e:
            print(f"Error in process_image: {e}")
            return []

    def save_to_csv(self, assets):
        try:
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / 'data'
            data_dir.mkdir(exist_ok=True)
            
            # Convert assets to DataFrame
            csv_data = []
            for asset in assets:
                ticker = asset["ticker"]
                # Apply ticker mappings if available
                mapped_ticker = self.ticker_mappings.get(ticker, ticker)
                csv_data.append({
                    "ticker": mapped_ticker,
                    "sentiment": asset["sentiment"],
                    "buy_trade": asset["buy_trade"],
                    "sell_trade": asset["sell_trade"],
                    "category": asset.get("category", "digitalassets")
                })
            
            df = pd.DataFrame(csv_data)
            csv_path = data_dir / 'digitalassets.csv'
            df.to_csv(csv_path, index=False)
            print(f"CSV saved to: {csv_path}")
            return True
        except Exception as e:
            print(f"Error saving to CSV: {e}")
            return False

    def parse_ocr_text(self, ocr_text):
        print("Parsing OCR text directly...")
        assets = []
        lines = ocr_text.split('\n')
        
        # Try to detect format
        has_table_format = any('|' in line for line in lines)
        
        if has_table_format:
            # Process as table format
            for line in lines:
                if not line or '|' not in line:
                    continue
                
                parts = [part.strip() for part in line.split('|') if part.strip()]
                if len(parts) < 3:  # Need at least ticker, buy, sell
                    continue
                
                ticker = parts[0].strip()
                if not re.match(r'^[A-Z]{1,5}$', ticker) or ticker == "TICKER":  # Skip header row
                    continue
                
                try:
                    # Extract numbers, handling various formats
                    number_pattern = r'(\d+\.?\d*)'
                    
                    # Find all numbers in the line
                    all_numbers = []
                    for part in parts:
                        found_numbers = re.findall(number_pattern, part)
                        all_numbers.extend([float(n) for n in found_numbers if n])
                    
                    if len(all_numbers) >= 2:  # Need at least buy and sell
                        # Usually the first or second number is buy trade and next is sell trade
                        buy_idx = 0 if len(all_numbers) == 2 else 1
                        sell_idx = 1 if len(all_numbers) == 2 else 2
                        
                        buy_trade = all_numbers[buy_idx]
                        sell_trade = all_numbers[sell_idx]
                        
                        # Determine sentiment from the last part
                        sentiment = "NEUTRAL"
                        last_part = parts[-1].upper()
                        if "BULLISH" in last_part:
                            sentiment = "BULLISH"
                        elif "BEARISH" in last_part:
                            sentiment = "BEARISH"
                        
                        assets.append({
                            "ticker": ticker,
                            "sentiment": sentiment,
                            "buy_trade": buy_trade,
                            "sell_trade": sell_trade,
                            "category": "digitalassets"
                        })
                        print(f"Added {ticker} with buy={buy_trade}, sell={sell_trade}, sentiment={sentiment}")
                
                except Exception as e:
                    print(f"Error processing line for {ticker}: {e}")
                    continue
        else:
            # Non-table format, try to extract by patterns
            ticker_pattern = r'([A-Z]{1,5})[\s\-\:]+'
            buy_sell_pattern = r'(?:BUY|TRADE|BUY TRADE)[\s\:]*(\d+\.?\d*)[\s\,]+(?:SELL|SELL TRADE)[\s\:]*(\d+\.?\d*)'
            sentiment_pattern = r'(?:TREND|SIGNAL|TREND SIGNAL)[\s\:]*([A-Z]+)'
            
            for i in range(len(lines) - 2):  # Look for patterns across multiple lines
                chunk = '\n'.join(lines[i:i+3])
                ticker_match = re.search(ticker_pattern, chunk)
                buy_sell_match = re.search(buy_sell_pattern, chunk)
                sentiment_match = re.search(sentiment_pattern, chunk)
                
                if ticker_match and buy_sell_match:
                    ticker = ticker_match.group(1)
                    buy_trade = float(buy_sell_match.group(1))
                    sell_trade = float(buy_sell_match.group(2))
                    
                    sentiment = "NEUTRAL"
                    if sentiment_match:
                        sentiment_text = sentiment_match.group(1)
                        if "BULL" in sentiment_text:
                            sentiment = "BULLISH"
                        elif "BEAR" in sentiment_text:
                            sentiment = "BEARISH"
                    
                    assets.append({
                        "ticker": ticker,
                        "sentiment": sentiment,
                        "buy_trade": buy_trade,
                        "sell_trade": sell_trade,
                        "category": "digitalassets"
                    })
                    print(f"Added {ticker} with buy={buy_trade}, sell={sell_trade}, sentiment={sentiment}")
        
        print(f"Parsed {len(assets)} assets from OCR text")
        return assets

    def parse_risk_ranges_section(self, ocr_md):
        print("Parsing RISK RANGES section...")
        assets = []
        lines = [line.strip() for line in ocr_md.split('\n')]
        
        # Look for the HEDGEYE RISK RANGES header
        risk_ranges_start = -1
        for i, line in enumerate(lines):
            if "HEDGEYE RISK RANGES" in line.upper():
                risk_ranges_start = i
                print(f"Found HEDGEYE RISK RANGES at line {i}")
                break

        if risk_ranges_start == -1:
            print("Could not find HEDGEYE RISK RANGES section header")
            return []

        # Dynamically find the start of the data table
        data_start = -1
        for i in range(risk_ranges_start + 1, min(risk_ranges_start + 10, len(lines))):
            # A data line should contain at least 3 pipe characters
            if lines[i].count('|') > 3:
                data_start = i
                print(f"Found data start at line {data_start}")
                break

        if data_start == -1:
            print("Could not find the start of the data table.")
            return []

        # Process each line that might contain crypto data
        for i in range(data_start, min(data_start + 20, len(lines))):
            line = lines[i]
            if not line or '|' not in line:
                # Stop if we hit an empty line after the data has started
                if assets:
                    break
                continue
            
            columns = [col.strip() for col in line.split('|')]
            if len(columns) < 5:  # Need at least empty, TICKER, Price, Buy, Sell
                continue
            
            # Dynamically extract ticker - should be 3-5 uppercase letters
            ticker_match = re.search(r'\b([A-Z]{3,5})\b', columns[1])
            if ticker_match:
                current_ticker = ticker_match.group(1)
                print(f"Found ticker: {current_ticker}")
                
                try:
                    # Extract buy and sell values (indices 3 and 4 for Buy and Sell Trade)
                    buy_trade_str = columns[3].replace(',', '')
                    sell_trade_str = columns[4].replace(',', '')

                    # Check for non-numeric values that might be headers or empty
                    if not re.match(r'^-?[0-9,.]+$', buy_trade_str) or not re.match(r'^-?[0-9,.]+$', sell_trade_str):
                        print(f"Skipping non-data row for {current_ticker}: {line}")
                        continue

                    buy_trade = float(buy_trade_str)
                    sell_trade = float(sell_trade_str)
                    
                    # Determine sentiment (BULLISH in this case, as per original logic)
                    sentiment = "BULLISH"
                    
                    mapped_ticker = self.ticker_mappings.get(current_ticker, current_ticker)
                    assets.append({
                        "ticker": mapped_ticker,
                        "sentiment": sentiment,
                        "buy_trade": buy_trade,
                        "sell_trade": sell_trade,
                        "category": "digitalassets"
                    })
                    print(f"  Added {mapped_ticker} with buy={buy_trade}, sell={sell_trade}, sentiment={sentiment}")
                    
                except (ValueError, IndexError) as e:
                    print(f"Error processing trade data for {current_ticker}: {e}")
        
        print(f"Parsed {len(assets)} assets from RISK RANGES section")
        return assets

    def parse_derivative_exposures_section(self, ocr_md):
        print("Parsing DIRECT & DERIVATIVE EXPOSURES section...")
        assets = []
        lines = ocr_md.split('\n')
        
        # Skip separator rows and empty lines
        data_lines = [line.strip() for line in lines if line.strip() and not line.strip().startswith('| :--:')]
        
        # Track if we've found the header row to help identify missing tickers
        header_found = False
        first_data_row = False
        
        for i, line in enumerate(data_lines):
            if not line or '|' not in line:
                continue
                
            parts = [part.strip() for part in line.split('|') if part.strip()]
            if len(parts) < 4:  # Need at least ticker, price, buy, sell
                continue
            
            # Check if this is the header row
            if any(header_term in line.upper() for header_term in ["TICKER", "PRICE", "BUY TRADE", "SELL TRADE", "TREND SIGNAL"]):
                header_found = True
                continue
                
            # First data row after header might be missing the IBIT ticker
            if header_found and not first_data_row:
                first_data_row = True
                
            ticker = parts[0].strip()
            
            # Handle case where ticker is missing but we have price data
            # This is specifically for the IBIT row which might be missing the ticker
            if (not re.match(r'^[A-Z]{1,5}$', ticker) or ticker == "") and first_data_row:
                # Check if this row has numbers that look like price data
                number_pattern = r'(?:\$?(?:\\begin\{gathered\})?(?:\\text\s*\{[^}]*\})?[\s\\\{\}]*)?(\d+\.?\d*)(?:[\s\\\}\%]*\\end\{gathered\})?'
                all_numbers = []
                for part in parts:
                    found_numbers = re.findall(number_pattern, part)
                    all_numbers.extend([float(n) for n in found_numbers if n])
                    
                if len(all_numbers) >= 3:  # If we have enough numbers for price, buy, sell
                    print("Detected first row with missing ticker, assuming IBIT")
                    ticker = "IBIT"
                else:
                    continue
            elif not re.match(r'^[A-Z]{1,5}$', ticker) or ticker == "TICKER":  # Skip header row
                continue
                
            try:
                # Extract numbers, handling LaTeX formatting
                number_pattern = r'(?:\$?(?:\\begin\{gathered\})?(?:\\text\s*\{[^}]*\})?[\s\\\{\}]*)?(\d+\.?\d*)(?:[\s\\\}\%]*\\end\{gathered\})?'
                
                # Find all numbers in the line
                all_numbers = []
                for part in parts:
                    found_numbers = re.findall(number_pattern, part)
                    all_numbers.extend([float(n) for n in found_numbers if n])
                
                if len(all_numbers) >= 3:  # Need price, buy, sell at minimum
                    # Usually the second number is buy trade and third is sell trade
                    buy_trade = all_numbers[1]  # Buy trade is usually the second number
                    sell_trade = all_numbers[2]  # Sell trade is usually the third number
                    
                    # Determine sentiment from the last part which contains TREND SIGNAL
                    sentiment = "NEUTRAL"
                    trend_part = parts[-1].upper() if len(parts) > 3 else ""
                    if "BULLISH" in trend_part:
                        sentiment = "BULLISH"
                    elif "BEARISH" in trend_part:
                        sentiment = "BEARISH"
                    
                    mapped_ticker = self.ticker_mappings.get(ticker, ticker)
                    assets.append({
                        "ticker": mapped_ticker,
                        "sentiment": sentiment,
                        "buy_trade": buy_trade,
                        "sell_trade": sell_trade,
                        "category": "digitalassets"
                    })
                    print(f"Added {mapped_ticker} with buy={buy_trade}, sell={sell_trade}, sentiment={sentiment}")
            
            except Exception as e:
                print(f"Error processing row for {ticker}: {e}")
                continue
            
        print(f"Parsed {len(assets)} assets from DERIVATIVE EXPOSURES section")
        return assets

    def parse_with_mistral_api(self, ocr_md):
        print("Using Mistral API to parse OCR text...")
        prompt = f"""
Below is the OCR output in markdown format from cryptocurrency table images. There are two different table formats that need to be analyzed and extracted:

1. "HEDGEYE RISK RANGES*" table - Contains crypto assets like BTC, ETH, SOL, AVAX, XRP, etc.
Format: Each asset has a header row with the ticker, followed by rows for TRADE (buy/sell values) and TREND (sentiment).
Example: BTC Duration | Buy Trade | Sell Trade TRADE | 80012 | 93968 TREND | BEARISH

2. "DIRECT & DERIVATIVE EXPOSURES: RISK RANGE & TREND SIGNAL" table - Contains crypto-related assets like IBIT, MSTR, MARA, RIOT, ETHA, BLOK, COIN, BITO, etc.
Format: Table with columns for TICKER, Price, Buy Trade, Sell Trade, UPSIDE, DOWNSIDE, and TREND SIGNAL.
Example: TICKER | Price | Buy Trade | Sell Trade | UPSIDE | DOWNSIDE | TREND SIGNAL IBIT | 51.44 | 44.40 | 52.90 | 2.8% | -13.7% | BEARISH

Text from OCR:
<BEGIN_IMAGE_OCR>
{ocr_md}
<END_IMAGE_OCR>

I need you to extract ALL assets from BOTH tables and return a JSON object with the format:
{{
    "assets": [
        {{
            "ticker": "BTC",
            "sentiment": "BULLISH or BEARISH",
            "buy_trade": <float>,
            "sell_trade": <float>,
            "category": "digitalassets"
        }},
        ...
    ]
}}

Important notes:
1. The first row in the second table format might be missing the ticker, which should be "IBIT".
2. Extract all tickers, even if they don't have a standard format.
3. For sentiment, use only "BULLISH", "BEARISH", or "NEUTRAL".
4. Return numeric values as floats without commas or dollar signs.
5. If you can't determine a value, use null.
6. Only return the JSON object, nothing else.
"""
        try:
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
                crypto_assets = crypto_data.get("assets", [])
            else:
                print(f"Error using Mistral API for structured parsing: {response.text}")
                crypto_assets = self.parse_ocr_text(ocr_md)
        except Exception as e:
            print(f"Error using Mistral API for structured parsing: {e}")
            print("Falling back to direct extraction...")
            crypto_assets = self.parse_ocr_text(ocr_md)
        return crypto_assets

    def extract_from_local_images(self):
        print(f"Starting crypto extraction from local images at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
        project_root = Path(__file__).parent.parent.parent
        data_dir = project_root / 'data'
        crypto1_path = data_dir / 'crypto1.png'
        crypto2_path = data_dir / 'crypto2.png'
        crypto_assets = []
        
        print(f"Processing crypto image 1: {crypto1_path}")
        crypto_assets1 = self.process_local_image(crypto1_path)
        print(f"Extracted {len(crypto_assets1)} assets from crypto image 1")
        crypto_assets.extend(crypto_assets1)
        
        print(f"Processing crypto image 2: {crypto2_path}")
        crypto_assets2 = self.process_local_image(crypto2_path)
        print(f"Extracted {len(crypto_assets2)} assets from crypto image 2")
        crypto_assets.extend(crypto_assets2)
        
        bullish_count = sum(1 for asset in crypto_assets if asset["sentiment"] == "BULLISH")
        bearish_count = sum(1 for asset in crypto_assets if asset["sentiment"] == "BEARISH")
        neutral_count = sum(1 for asset in crypto_assets if asset["sentiment"] == "NEUTRAL")
        
        print("Crypto Extraction Summary:")
        print(f"Total cryptocurrencies: {len(crypto_assets)}")
        print(f"BULLISH: {bullish_count}")
        print(f"BEARISH: {bearish_count}")
        print(f"NEUTRAL: {neutral_count}")
        
        if crypto_assets:
            csv_data = [{
                "ticker": self.ticker_mappings.get(asset["ticker"], asset["ticker"]),
                "sentiment": asset["sentiment"],
                "buy_trade": asset["buy_trade"],
                "sell_trade": asset["sell_trade"],
                "category": asset["category"]
            } for asset in crypto_assets]
            df = pd.DataFrame(csv_data)
            csv_path = data_dir / 'digitalassets.csv'
            df.to_csv(csv_path, index=False)
            print(f"CSV saved to: {csv_path}")
        
        self.cleanup_temp_files(data_dir)
        print("Crypto extraction completed successfully")
        print(f"CSV contains {len(crypto_assets)} cryptocurrencies")
        print(f"CSV saved to: {data_dir / 'digitalassets.csv'}")
        return crypto_assets

    def cleanup_temp_files(self, data_dir):
        try:
            temp_files = list(data_dir.glob('temp_crypto_*.png'))
            temp_files.extend(list(data_dir.glob('crypto_ocr_text.*')))
            crypto_table_path = data_dir / 'crypto_table.png'
            if crypto_table_path.exists():
                temp_files.append(crypto_table_path)
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                    print(f"Cleaned up temporary file: {temp_file}")
                except Exception as e:
                    print(f"Error cleaning up {temp_file}: {e}")
        except Exception as e:
            print(f"Error in cleanup_temp_files: {e}")

if __name__ == "__main__":
    extractor = CryptoEmailExtractor()
    extractor.extract_from_local_images()