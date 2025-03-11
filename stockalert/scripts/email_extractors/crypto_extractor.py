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
from io import BytesIO
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from stockalert.utils.env_loader import get_env

# Load environment variables
# env_path = Path(__file__).parent.parent.parent.parent / '.env'
# load_dotenv(dotenv_path=env_path)

# Add the project root to Python path when running directly
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.append(str(project_root))

from scripts.email_extractors import BaseEmailExtractor


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


class CryptoEmailExtractor(BaseEmailExtractor):
    def __init__(self):
        super().__init__()
        
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

    def extract_image_from_email(self):
        """Extract the crypto table image from the most recent email with 'CRYPTO QUANT' in subject"""
        try:
            # Search for emails from the last 7 days (daily emails)
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y/%m/%d')
            query = f'subject:"CRYPTO QUANT" after:{seven_days_ago}'
            print(f"Searching for emails with query: {query}")
            
            # Get the email content
            email_content = self.get_email_content(query)
            
            if not email_content:
                print("No CRYPTO QUANT emails found in the last 7 days")
                return None
            
            print(f"Found email content, length: {len(email_content)}")
            
            # Save the raw email HTML for debugging
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / 'data'
            data_dir.mkdir(exist_ok=True)
            with open(data_dir / 'crypto_email_raw.html', 'w', encoding='utf-8') as f:
                f.write(email_content)
            print(f"Saved raw email HTML to: {data_dir / 'crypto_email_raw.html'}")
            
            # Parse the HTML content
            soup = BeautifulSoup(email_content, 'html.parser')
            
            # Method 1: Look for cloudfront.net images (specific to Hedgeye emails)
            crypto_image_data = None
            largest_image_size = 0
            
            print("Looking for cloudfront.net images...")
            # Find all img tags with cloudfront.net in the src
            cloudfront_images = []
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if 'cloudfront.net' in src:
                    cloudfront_images.append(src)
                    print(f"Found cloudfront image: {src}")
            
            # Also look for cloudfront links in the text
            cloudfront_pattern = r'https?://[^"\'>\s]+cloudfront\.net[^"\'>\s]+'
            cloudfront_matches = re.findall(cloudfront_pattern, email_content)
            for url in cloudfront_matches:
                if url not in cloudfront_images:
                    cloudfront_images.append(url)
                    print(f"Found cloudfront URL in text: {url}")
            
            # Download and check each cloudfront image
            import requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            for img_url in cloudfront_images:
                try:
                    print(f"Downloading cloudfront image: {img_url}")
                    response = requests.get(img_url, headers=headers, timeout=15)
                    if response.status_code == 200:
                        image_data = response.content
                        if len(image_data) > largest_image_size:
                            largest_image_size = len(image_data)
                            crypto_image_data = image_data
                            print(f"Downloaded larger cloudfront image, size: {len(image_data)} bytes")
                            
                            # Save the image for inspection
                            img_filename = f"crypto_cloudfront_image_{largest_image_size}.png"
                            with open(data_dir / img_filename, 'wb') as f:
                                f.write(image_data)
                            print(f"Saved cloudfront image to: {data_dir / img_filename}")
                except Exception as e:
                    print(f"Error downloading cloudfront image: {e}")
            
            # Method 2: Look for "View it in your browser" links
            if not crypto_image_data:
                print("Looking for 'View it in your browser' links...")
                browser_links = []
                for a in soup.find_all('a'):
                    text = a.text.lower() if a.text else ""
                    href = a.get('href', '')
                    if ('view' in text and 'browser' in text) or 'view online' in text or 'web version' in text:
                        browser_links.append(href)
                        print(f"Found 'View in browser' link: {href}")
                
                for link in browser_links:
                    try:
                        print(f"Fetching content from browser link: {link}")
                        response = requests.get(link, headers=headers, timeout=15)
                        if response.status_code == 200:
                            # Save the web page content for debugging
                            with open(data_dir / 'crypto_webpage.html', 'w', encoding='utf-8') as f:
                                f.write(response.text)
                            print(f"Saved web page content to: {data_dir / 'crypto_webpage.html'}")
                            
                            # Parse the web page content
                            web_content = response.text
                            web_soup = BeautifulSoup(web_content, 'html.parser')
                            
                            # Look for cloudfront images in the web page
                            for img in web_soup.find_all('img'):
                                src = img.get('src', '')
                                if src and 'cloudfront.net' in src:
                                    try:
                                        print(f"Downloading cloudfront image from browser page: {src}")
                                        img_response = requests.get(src, headers=headers, timeout=10)
                                        if img_response.status_code == 200:
                                            image_data = img_response.content
                                            if len(image_data) > largest_image_size:
                                                largest_image_size = len(image_data)
                                                crypto_image_data = image_data
                                                print(f"Downloaded larger cloudfront image from browser page, size: {len(image_data)} bytes")
                                                
                                                # Save the image for inspection
                                                img_filename = f"crypto_browser_cloudfront_{largest_image_size}.png"
                                                with open(data_dir / img_filename, 'wb') as f:
                                                    f.write(image_data)
                                                print(f"Saved browser cloudfront image to: {data_dir / img_filename}")
                                    except Exception as e:
                                        print(f"Error downloading cloudfront image from browser page: {e}")
                            
                            # Look for other images in the web page
                            if not crypto_image_data:
                                for img in web_soup.find_all('img'):
                                    src = img.get('src', '')
                                    if src:
                                        # Handle relative URLs
                                        if src.startswith('/'):
                                            from urllib.parse import urlparse
                                            parsed_url = urlparse(link)
                                            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                                            src = base_url + src
                                        elif not (src.startswith('http://') or src.startswith('https://')):
                                            from urllib.parse import urlparse, urljoin
                                            src = urljoin(link, src)
                                        
                                        try:
                                            print(f"Downloading image from browser page: {src}")
                                            img_response = requests.get(src, headers=headers, timeout=10)
                                            if img_response.status_code == 200:
                                                image_data = img_response.content
                                                if len(image_data) > largest_image_size and len(image_data) > 10000:  # Only consider images larger than 10KB
                                                    largest_image_size = len(image_data)
                                                    crypto_image_data = image_data
                                                    print(f"Downloaded larger image from browser page, size: {len(image_data)} bytes")
                                                    
                                                    # Save the image for inspection
                                                    img_filename = f"crypto_browser_image_{largest_image_size}.png"
                                                    with open(data_dir / img_filename, 'wb') as f:
                                                        f.write(image_data)
                                                    print(f"Saved browser image to: {data_dir / img_filename}")
                                        except Exception as e:
                                            print(f"Error downloading image from browser page: {e}")
                    except Exception as e:
                        print(f"Error fetching content from browser link: {e}")
            
            # Method 3: Look for any images in the email
            if not crypto_image_data:
                print("Looking for images in the email...")
                images = soup.find_all('img')
                print(f"Found {len(images)} img tags in the email")
                
                for img in images:
                    # Get the image source
                    src = img.get('src', '')
                    if src and not src.startswith('data:'):
                        try:
                            print(f"Downloading image from: {src}")
                            response = requests.get(src, headers=headers, timeout=10)
                            if response.status_code == 200:
                                image_data = response.content
                                if len(image_data) > largest_image_size and len(image_data) > 10000:  # Only consider images larger than 10KB
                                    largest_image_size = len(image_data)
                                    crypto_image_data = image_data
                                    print(f"Downloaded larger image, size: {len(image_data)} bytes")
                                    
                                    # Save the image for inspection
                                    img_filename = f"crypto_email_image_{largest_image_size}.png"
                                    with open(data_dir / img_filename, 'wb') as f:
                                        f.write(image_data)
                                    print(f"Saved email image to: {data_dir / img_filename}")
                        except Exception as e:
                            print(f"Error downloading image from email: {e}")
            
            if crypto_image_data:
                print(f"Successfully extracted image from email, size: {largest_image_size} bytes")
                
                # Save the final extracted image
                with open(data_dir / 'crypto_table.png', 'wb') as f:
                    f.write(crypto_image_data)
                print(f"Saved extracted image to: {data_dir / 'crypto_table.png'}")
                
                return crypto_image_data
            else:
                print("Could not find any suitable images in the email")
                return None
                
        except Exception as e:
            print(f"Error extracting image from email: {e}")
            import traceback
            traceback.print_exc()
            return None

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
        elif "DIRECT & DERIVATIVE EXPOSURES" in ocr_text or "DIRECT \& DERIVATIVE EXPOSURES" in ocr_text:
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

    def get_hardcoded_assets(self):
        """Return hardcoded assets as a fallback when extraction fails"""
        # This method is being deprecated as we're focusing on extracting real data from emails
        print("WARNING: get_hardcoded_assets is deprecated and should not be used")
        return []

    def cleanup_temp_files(self):
        """Clean up temporary files created during extraction"""
        try:
            # Get the data directory
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / 'data'
            
            # Files to clean up
            files_to_clean = [
                data_dir / 'crypto_email_raw.html',
                data_dir / 'crypto_table.png',
                data_dir / 'crypto_webpage.html'
            ]
            
            # Delete each file if it exists
            for file_path in files_to_clean:
                if file_path.exists():
                    file_path.unlink()
                    print(f"Cleaned up temporary file: {file_path}")
            
            # Also check for any other crypto_*.png files that might have been created
            for file_path in data_dir.glob('crypto_*.png'):
                if file_path.exists():
                    file_path.unlink()
                    print(f"Cleaned up temporary file: {file_path}")
            
        except Exception as e:
            print(f"Error cleaning up temporary files: {e}")
    
    def extract(self):
        """Main method to extract crypto data from email"""
        try:
            # Get the image from email
            image_data = self.extract_image_from_email()
            
            if not image_data:
                print("Failed to get crypto image from email")
                return None
                
            # Process the image
            crypto_data = self.process_image(image_data)
            
            if not crypto_data:
                print("Failed to extract crypto data")
                return None
                
            print(f"Successfully extracted {len(crypto_data)} crypto records")
            return crypto_data
            
        except Exception as e:
            print(f"Error in extract: {e}")
            return None

    def extract_crypto_data(self):
        """Main method to extract crypto data from emails"""
        try:
            print(f"Starting crypto extraction from Gmail at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
            
            # Extract image from email
            image_data = self.extract_image_from_email()
            if not image_data:
                print("Failed to extract image from email")
                return False
            
            # Process the image
            crypto_assets = self.process_image(image_data)
            if not crypto_assets:
                print("Failed to extract crypto data from image")
                return False
            
            # Create DataFrame and save to CSV
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / 'data'
            data_dir.mkdir(exist_ok=True)
            
            # Create CSV file
            df = pd.DataFrame(crypto_assets)
            csv_path = data_dir / 'digitalassets.csv'
            df.to_csv(csv_path, index=False)
            
            # Print summary
            print("Crypto Extraction Summary:")
            print(f"Total cryptocurrencies: {len(df)}")
            print(f"BULLISH: {len(df[df['sentiment'] == 'BULLISH'])}")
            print(f"BEARISH: {len(df[df['sentiment'] == 'BEARISH'])}")
            
            # Clean up temporary files
            self.cleanup_temp_files()
            
            # Print CSV location
            print(f"CSV saved to: {csv_path}")
            
            return True
            
        except Exception as e:
            print(f"Error in extract_crypto_data: {e}")
            import traceback
            traceback.print_exc()
            return False

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

    def extract_from_local_images(self):
        """Extract crypto data directly from local image files"""
        print(f"Starting crypto extraction from local images at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
        
        # Define the path to the local images
        project_root = Path(__file__).parent.parent.parent
        data_dir = project_root / 'data'
        
        # Process both crypto images and combine results
        all_crypto_assets = []
        temp_files = []
        
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
        
        # Create CSV data with ticker mapping
        csv_data = [
            {
                "ticker": self.ticker_mappings.get(asset["ticker"], asset["ticker"]),
                "sentiment": asset["sentiment"],
                "buy_trade": asset["buy_trade"],
                "sell_trade": asset["sell_trade"],
                "category": asset["category"]
            }
            for asset in all_crypto_assets
        ]
        
        # Create a DataFrame and save to CSV
        df = pd.DataFrame(csv_data)
        csv_path = data_dir / 'digitalassets.csv'
        df.to_csv(csv_path, index=False)
        
        # Print summary
        print("Crypto Extraction Summary:")
        print(f"Total cryptocurrencies: {len(csv_data)}")
        print(f"BULLISH: {len([a for a in all_crypto_assets if a['sentiment'] == 'BULLISH'])}")
        print(f"BEARISH: {len([a for a in all_crypto_assets if a['sentiment'] == 'BEARISH'])}")
        print(f"CSV saved to: {csv_path}")
        
        # Clean up temporary files
        temp_files = list(data_dir.glob('crypto_*.*'))
        for temp_file in temp_files:
            if temp_file.name != 'crypto1.png' and temp_file.name != 'crypto2.png':
                try:
                    os.remove(temp_file)
                    print(f"Cleaned up temporary file: {temp_file}")
                except Exception as e:
                    print(f"Error cleaning up {temp_file}: {e}")
        
        return all_crypto_assets

if __name__ == "__main__":
    # Create the extractor
    extractor = CryptoEmailExtractor()
    
    # Extract from local images if available, otherwise from email
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / 'data'
    crypto1_path = data_dir / 'crypto1.png'
    crypto2_path = data_dir / 'crypto2.png'
    
    if os.path.exists(crypto1_path) or os.path.exists(crypto2_path):
        print(f"Found local crypto image files. Using these for extraction.")
        crypto_data = extractor.extract_from_local_images()
    else:
        print("No local crypto image files found. Extracting from email.")
        crypto_data = extractor.extract_crypto_data()
    
    # Print summary
    if crypto_data:
        print("Crypto extraction completed successfully")
        print(f"CSV contains {len(crypto_data)} cryptocurrencies")
        
        # Save to CSV
        csv_path = data_dir / 'digitalassets.csv'
        print(f"CSV saved to: {csv_path}")
    else:
        print("Crypto extraction failed")