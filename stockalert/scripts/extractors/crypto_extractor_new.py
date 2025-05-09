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
            'XRP': 'XRP-USD'
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
        lines = ocr_md.split('\n')
        ticker_blocks = []
        known_tickers = ["BTC", "ETH", "SOL", "AVAX", "XRP"]
        
        print("Searching for ticker blocks...")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('|'):
                for ticker in known_tickers:
                    if f"| {ticker} |" in stripped:
                        if not any(b['start_line'] == i for b in ticker_blocks):
                            ticker_blocks.append({'ticker': ticker, 'start_line': i})
                            print(f"Found potential block for {ticker} starting at line {i}: {stripped}")
                        break
        
        if not ticker_blocks:
            print("No ticker blocks identified.")
            return []
        
        for idx, block in enumerate(ticker_blocks):
            current_ticker = block['ticker']
            start_line = block['start_line']
            end_line = len(lines)
            if idx + 1 < len(ticker_blocks):
                end_line = ticker_blocks[idx + 1]['start_line']
            
            search_end_line = min(start_line + 7, end_line)
            print(f"Processing block for {current_ticker} from line {start_line} to {search_end_line-1}")
            
            buy_trade = None
            sell_trade = None
            sentiment = "NEUTRAL"
            
            for i in range(start_line, search_end_line):
                line = lines[i]
                if '|' in line and "TRADE" in line and "Buy Trade" not in line and "Sell Trade" not in line:
                    print(f"  Processing TRADE row: {line}")
                    parts = [part.strip() for part in line.split('|') if part.strip()]
                    if len(parts) >= 3:
                        try:
                            buy_match = re.search(r'(-?\d+\.?\d*)', parts[1].replace(',', ''))
                            sell_match = re.search(r'(-?\d+\.?\d*)', parts[2].replace(',', ''))
                            if buy_match and sell_match:
                                buy_trade = float(buy_match.group(1))
                                sell_trade = float(sell_match.group(1))
                                print(f"  Extracted buy={buy_trade}, sell={sell_trade}")
                            else:
                                print(f"  Could not extract buy/sell from TRADE parts: {parts}")
                        except (ValueError, IndexError) as e:
                            print(f"  Error extracting TRADE values: {e} from line: {line}")
                
                elif '|' in line and "TREND" in line:
                    print(f"  Processing TREND row: {line}")
                    trend_upper = line.upper()
                    if "BEARISH" in trend_upper:
                        sentiment = "BEARISH"
                    elif "BULLISH" in trend_upper:
                        sentiment = "BULLISH"
                    elif "NEUTRAL" in trend_upper:
                        sentiment = "NEUTRAL"
                    print(f"  Extracted sentiment={sentiment}")
            
            if buy_trade is not None and sell_trade is not None:
                mapped_ticker = self.ticker_mappings.get(current_ticker, current_ticker)
                assets.append({
                    "ticker": mapped_ticker,
                    "sentiment": sentiment,
                    "buy_trade": buy_trade,
                    "sell_trade": sell_trade,
                    "category": "digitalassets"
                })
                print(f"Added {mapped_ticker} with buy={buy_trade}, sell={sell_trade}, sentiment={sentiment}")
            else:
                print(f"Could not find valid TRADE data for {current_ticker}.")
        
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
