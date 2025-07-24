import os
import sys
import json
import base64
import re
from pathlib import Path
from pydantic import BaseModel
import pandas as pd
import requests, json
from dotenv import load_dotenv
from stockalert.utils.env_loader import get_env

# Add the project root to the Python path to allow absolute imports
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from stockalert.scripts.base_email_extractor import BaseEmailExtractor
from io import BytesIO
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# Remove load_dotenv() call since we're using the centralized environment loader
# load_dotenv()

# Define Pydantic models for ETF data
class RangeData(BaseModel):
    low: float
    high: float

class ETFAsset(BaseModel):
    ticker: str
    sentiment: str
    buy_trade: float
    sell_trade: float
    category: str = "etfs"

class ETFData(BaseModel):
    assets: list[ETFAsset]

class ETFEmailExtractor(BaseEmailExtractor):
    def __init__(self):
        super().__init__()
        self.root_dir = Path(__file__).parent.parent.parent
        self.data_dir = self.root_dir / 'data'
        self.output_file = self.data_dir / 'etfs.csv'
        
        # Create data directory if it doesn't exist
        self.data_dir.mkdir(exist_ok=True)
        
        self.mistral_api_key = get_env('MISTRAL_API_KEY')

    def extract_image_from_email(self):
        """Extract the ETF table image from the most recent email with 'ETF Pro Plus - Levels' in subject"""
        try:
            # Search for emails from the last 30 days (to ensure we get the most recent weekly email)
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y/%m/%d')
            query = f'subject:"ETF Pro Plus - Levels" after:{thirty_days_ago}'
            print(f"Searching for emails with query: {query}")
            
            # Get the email content
            email_content = self.get_email_content(query)
            
            if not email_content:
                print("No ETF Pro Plus emails found in the last 30 days")
                return None
            
            print(f"Found email content, length: {len(email_content)}")
            
            # Save the raw email HTML for debugging
            with open(self.data_dir / 'etf_email_raw.html', 'w', encoding='utf-8') as f:
                f.write(email_content)
            print(f"Saved raw email HTML to: {self.data_dir / 'etf_email_raw.html'}")
            
            # Parse the HTML content
            soup = BeautifulSoup(email_content, 'html.parser')
            
            # Method 1: Look for cloudfront.net images (specific to ETF Pro Plus emails)
            etf_image_data = None
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
                            etf_image_data = image_data
                            print(f"Downloaded larger cloudfront image, size: {len(image_data)} bytes")
                            
                            # Save the image for inspection
                            img_filename = f"etf_cloudfront_image_{largest_image_size}.png"
                            with open(self.data_dir / img_filename, 'wb') as f:
                                f.write(image_data)
                            print(f"Saved cloudfront image to: {self.data_dir / img_filename}")
                except Exception as e:
                    print(f"Error downloading cloudfront image: {e}")
            
            # Method 2: Look for "VIEW LARGER IMAGE" links
            if not etf_image_data:
                print("Looking for 'VIEW LARGER IMAGE' links...")
                view_larger_links = []
                for a in soup.find_all('a'):
                    if 'VIEW LARGER IMAGE' in a.text:
                        view_larger_links.append(a.get('href'))
                        print(f"Found 'VIEW LARGER IMAGE' link: {a.get('href')}")
            
                for link in view_larger_links:
                    try:
                        print(f"Fetching content from VIEW LARGER IMAGE link: {link}")
                        response = requests.get(link, headers=headers, timeout=15)
                        if response.status_code == 200:
                            # Check if this is an image
                            content_type = response.headers.get('Content-Type', '')
                            if 'image' in content_type:
                                image_data = response.content
                                if len(image_data) > largest_image_size:
                                    largest_image_size = len(image_data)
                                    etf_image_data = image_data
                                    print(f"Downloaded larger image from VIEW LARGER IMAGE link, size: {len(image_data)} bytes")
                                    
                                    # Save the image for inspection
                                    img_filename = f"etf_larger_image_{largest_image_size}.png"
                                    with open(self.data_dir / img_filename, 'wb') as f:
                                        f.write(image_data)
                                    print(f"Saved larger image to: {self.data_dir / img_filename}")
                            else:
                                # This might be a page with the image
                                web_content = response.text
                                web_soup = BeautifulSoup(web_content, 'html.parser')
                                
                                # Look for images on the page
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
                                            print(f"Downloading image from VIEW LARGER IMAGE page: {src}")
                                            img_response = requests.get(src, headers=headers, timeout=10)
                                            if img_response.status_code == 200:
                                                image_data = img_response.content
                                                if len(image_data) > largest_image_size:
                                                    largest_image_size = len(image_data)
                                                    etf_image_data = image_data
                                                    print(f"Downloaded larger image from VIEW LARGER IMAGE page, size: {len(image_data)} bytes")
                                                    
                                                    # Save the image for inspection
                                                    img_filename = f"etf_page_image_{largest_image_size}.png"
                                                    with open(self.data_dir / img_filename, 'wb') as f:
                                                        f.write(image_data)
                                                    print(f"Saved page image to: {self.data_dir / img_filename}")
                                        except Exception as e:
                                            print(f"Error downloading image from VIEW LARGER IMAGE page: {e}")
                    except Exception as e:
                        print(f"Error fetching content from VIEW LARGER IMAGE link: {e}")
            
            # Method 3: Look for "View it in your browser" links
            if not etf_image_data:
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
                            with open(self.data_dir / 'etf_webpage.html', 'w', encoding='utf-8') as f:
                                f.write(response.text)
                            print(f"Saved web page content to: {self.data_dir / 'etf_webpage.html'}")
                            
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
                                                etf_image_data = image_data
                                                print(f"Downloaded larger cloudfront image from browser page, size: {len(image_data)} bytes")
                                                
                                                # Save the image for inspection
                                                img_filename = f"etf_browser_cloudfront_{largest_image_size}.png"
                                                with open(self.data_dir / img_filename, 'wb') as f:
                                                    f.write(image_data)
                                                print(f"Saved browser cloudfront image to: {self.data_dir / img_filename}")
                                    except Exception as e:
                                        print(f"Error downloading cloudfront image from browser page: {e}")
                            
                            # Look for other images in the web page
                            if not etf_image_data:
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
                                                    etf_image_data = image_data
                                                    print(f"Downloaded larger image from browser page, size: {len(image_data)} bytes")
                                                    
                                                    # Save the image for inspection
                                                    img_filename = f"etf_browser_image_{largest_image_size}.png"
                                                    with open(self.data_dir / img_filename, 'wb') as f:
                                                        f.write(image_data)
                                                    print(f"Saved browser image to: {self.data_dir / img_filename}")
                                        except Exception as e:
                                            print(f"Error downloading image from browser page: {e}")
                    except Exception as e:
                        print(f"Error fetching content from browser link: {e}")
        
            if etf_image_data:
                print(f"Successfully extracted image from email, size: {largest_image_size} bytes")
                
                # Save the final extracted image
                with open(self.data_dir / 'etf_table.png', 'wb') as f:
                    f.write(etf_image_data)
                print(f"Saved extracted image to: {self.data_dir / 'etf_table.png'}")
                
                return etf_image_data
            else:
                print("Could not find any suitable images in the email")
                return None
            
        except Exception as e:
            print(f"Error extracting image from email: {e}")
            import traceback
            traceback.print_exc()
            return None

    def process_image(self, image_data):
        """Process image using Mistral OCR API and return parsed ETF data"""
        try:
            # Save the image for debugging
            temp_image_path = self.data_dir / 'etf_table.png'
            with open(temp_image_path, 'wb') as f:
                f.write(image_data)

            # Send image to Mistral OCR API using the same payload as crypto_extractor
            headers = {
                "Authorization": f"Bearer {self.mistral_api_key}",
                "Content-Type": "application/json"
            }
            print("Processing with Mistral OCR...")
            image_base64_str = base64.b64encode(image_data).decode('utf-8')
            data_url = f"data:image/png;base64,{image_base64_str}"
            payload = {
                "document": {"image_url": data_url},
                "model": "mistral-ocr-latest"
            }
            ocr_response = requests.post(
                "https://api.mistral.ai/v1/ocr",
                headers=headers,
                json=payload
            )
            if ocr_response.status_code != 200:
                print(f"OCR API Error: {ocr_response.status_code} - {ocr_response.text}")
                return []
            ocr_data = ocr_response.json()
            ocr_md = ocr_data['pages'][0]['markdown']
            # Save OCR markdown for debugging
            ocr_text_path = self.data_dir / 'etf_ocr_text.md'
            with open(ocr_text_path, 'w', encoding='utf-8') as f:
                f.write(ocr_md)
            print(f"Saved OCR text to: {ocr_text_path}")
            print("\nSample OCR Text (first 500 chars):")
            print(ocr_md[:500] + "..." if len(ocr_md) > 500 else ocr_md)

            # Try direct parsing, fallback to LLM if needed
            assets = self.parse_markdown_table(ocr_md)
            if len(assets) < 1:
                print("Direct parsing extracted too few assets, using Mistral API for assistance...")
                assets = self.parse_with_mistral_api(ocr_md)
            # Save to CSV
            if assets:
                df = pd.DataFrame(assets)
                df.to_csv(self.output_file, index=False)
                print(f"\nSaved ETF data to: {self.output_file}")
            return assets
        except Exception as e:
            print(f"Error processing image: {e}")
            return []

    def clean_number(self, s):
        """Helper to clean and convert number strings to float"""
        if not s or not isinstance(s, str):
            return None
        # Remove any non-numeric characters except decimal point and minus sign
        s = re.sub(r'[^\d.-]', '', s)
        try:
            return float(s) if s else None
        except ValueError:
            return None

    def parse_markdown_table(self, markdown_table):
        """Parse ETF markdown table into structured data"""
        assets = []
        lines = [line.strip() for line in markdown_table.split('\n') if line.strip()]
        
        # Find the header row that contains 'TICKER' and 'TREND RANGES'
        header_line = -1
        for i, line in enumerate(lines):
            if 'TICKER' in line and 'TREND RANGES' in line:
                header_line = i
                break
        
        if header_line == -1:
            print("Could not find table header with 'TICKER' and 'TREND RANGES' in markdown")
            return assets
        
        # Print the header and first few rows for debugging
        print("\nDebug - First few rows of the table:")
        for i, line in enumerate(lines[header_line:min(header_line+5, len(lines))]):
            print(f"{i}: {line}")
        
        # Get the data rows (skip header and separator rows)
        for line in lines[header_line+2:]:  # +2 to skip header and separator
            if not line.startswith('|'):
                continue
                
            # Split the row into cells and clean them up
            cells = [cell.strip() for cell in line.split('|')[1:-1]]  # Remove empty first/last cells
            
            # We expect 6 columns: BUILDIN, TICKER, DATE ADDED, RECEIVED PRICE, BUY, SELL, ASSET CLASS
            if len(cells) < 6:
                print(f"Skipping row with insufficient columns ({len(cells)} < 6): {line}")
                continue
                
            try:
                # The actual data is in this format:
                # | BUILDIN | TICKER | DATE ADDED | RECEIVED PRICE | BUY | SELL | ASSET CLASS |
                ticker = cells[1].strip()
                
                # The buy and sell prices are now in the 5th and 6th columns (0-based index 4 and 5)
                buy_trade = self.clean_number(cells[4])  # 5th column (0-based index 4)
                sell_trade = self.clean_number(cells[5])  # 6th column (0-based index 5)
                
                # Only add if we have valid values
                if ticker and buy_trade is not None and sell_trade is not None:
                    # Try to determine sentiment from the asset class or ticker
                    asset_class = cells[6].lower() if len(cells) > 6 else ''
                    sentiment = "NEUTRAL"
                    if any(word in asset_class for word in ['bear', 'short', 'inverse']):
                        sentiment = "BEARISH"
                    elif any(word in asset_class for word in ['bull', 'long']):
                        sentiment = "BULLISH"
                    
                    asset = {
                        "ticker": ticker,
                        "sentiment": sentiment,
                        "buy_trade": buy_trade,
                        "sell_trade": sell_trade,
                        "category": "etfs"
                    }
                    print(f"Parsed asset: {asset}")
                    assets.append(asset)
                else:
                    print(f"Skipping row with missing data - Ticker: {ticker}, Buy: {buy_trade}, Sell: {sell_trade}")
                
            except (IndexError, ValueError, AttributeError) as e:
                print(f"Skipping malformed row: {line} - Error: {e}")
                continue
                
        print(f"Successfully parsed {len(assets)} ETF assets from markdown table")
        return assets

    def parse_with_mistral_api(self, ocr_md):
        print("Using Mistral API to parse OCR text...")
        prompt = f"""
Below is the OCR output in markdown format from an ETF table image. Extract all ETF assets and return a JSON object with the format:
{{
    "assets": [
        {{
            "ticker": "SPY",
            "sentiment": "BULLISH or BEARISH",
            "buy_trade": <float>,
            "sell_trade": <float>,
            "category": "etfs"
        }},
        ...
    ]
}}
Text from OCR:
<BEGIN_IMAGE_OCR>
{ocr_md}
<END_IMAGE_OCR>
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
                etf_data = json.loads(response_content)
                etf_assets = etf_data.get("assets", [])
            else:
                print(f"Error using Mistral API for structured parsing: {response.text}")
                etf_assets = self.parse_markdown_table(ocr_md)
        except Exception as e:
            print(f"Error using Mistral API for structured parsing: {e}")
            print("Falling back to direct extraction...")
            etf_assets = self.parse_markdown_table(ocr_md)
        return etf_assets
            
    def cleanup_temp_files(self):
        """Clean up temporary files created during extraction"""
        try:
            # Files to clean up
            files_to_clean = [
                self.data_dir / 'etf_email_raw.html',
                self.data_dir / 'etf_table.png',
                self.data_dir / 'etf_webpage.html'
            ]
            
            # Delete each file if it exists
            for file_path in files_to_clean:
                if file_path.exists():
                    file_path.unlink()
                    print(f"Cleaned up temporary file: {file_path}")
            
            # Also check for any other etf_*.png files that might have been created
            for file_path in self.data_dir.glob('etf_*.png'):
                if file_path.exists():
                    file_path.unlink()
                    print(f"Cleaned up temporary file: {file_path}")
            
        except Exception as e:
            print(f"Error cleaning up temporary files: {e}")
    
    def extract(self):
        """Main method to extract ETF data from email"""
        try:
            # Get the image from email
            image_data = self.extract_image_from_email()
            
            if not image_data:
                print("Failed to get ETF image from email")
                return None
                
            # Process the image
            etf_data = self.process_image(image_data)
            
            if not etf_data:
                print("Failed to extract ETF data")
                return None
                
            print(f"Successfully extracted {len(etf_data)} ETF records")
            
            # Clean up temporary files
            self.cleanup_temp_files()
            
            return etf_data
            
        except Exception as e:
            print(f"Error in extract: {e}")
            # Try to clean up even if there was an error
            try:
                self.cleanup_temp_files()
            except Exception as cleanup_error:
                print(f"Error during cleanup after extraction failure: {cleanup_error}")
            return None


if __name__ == "__main__":
    """Run the ETF extractor when script is executed directly"""
    import sys
    from datetime import datetime
    
    print(f"Starting ETF extraction from Gmail at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
    
    # Initialize the ETF extractor
    extractor = ETFEmailExtractor()
    
    # Extract ETF data from Gmail
    etf_data = extractor.extract()
    
    if not etf_data:
        print("ETF extraction from Gmail failed")
        sys.exit(1)
    
    # Print summary
    bullish_count = sum(1 for asset in etf_data if asset['sentiment'] == 'BULLISH')
    bearish_count = sum(1 for asset in etf_data if asset['sentiment'] == 'BEARISH')
    
    print(f"\nETF Extraction Summary:")
    print(f"Total ETFs: {len(etf_data)}")
    print(f"BULLISH: {bullish_count}")
    print(f"BEARISH: {bearish_count}")
    
    print(f"CSV saved to: {extractor.output_file}")
    
    sys.exit(0)