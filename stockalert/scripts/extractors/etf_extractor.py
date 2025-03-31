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
from stockalert.utils.env_loader import get_env

# Add the project root to Python path when running directly
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.append(str(project_root))

from stockalert.scripts.extractors import BaseEmailExtractor
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
        
        self.mistral_client = Mistral(api_key=get_env('MISTRAL_API_KEY'))

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
        """Process image using Mistral OCR API"""
        try:
            # Convert image to base64
            image_base64 = base64.b64encode(image_data).decode()
            data_url = f"data:image/png;base64,{image_base64}"
            
            # Process OCR to get markdown output
            print("Processing with Mistral OCR...")
            ocr_response = self.mistral_client.ocr.process(
                document=ImageURLChunk(image_url=data_url), 
                model="mistral-ocr-latest"
            )
            ocr_md = ocr_response.pages[0].markdown
            print("\nRaw OCR Text:")
            print(ocr_md)
            
            # Prompt to convert OCR markdown to structured ETF JSON
            prompt = f"""
            Below is the OCR output in markdown format from an ETF table image. The table is divided into two sections:
            1. BULLISH section (from start until "BEARISH" header)
            2. BEARISH section (from "BEARISH" header until end)

            Text from OCR:
            <BEGIN_IMAGE_OCR>
            {ocr_md}
            <END_IMAGE_OCR>

            Convert this into a structured JSON response. For each ETF entry:
            1. Extract ticker (3-4 letter code)
            2. Set sentiment based on which section it appears in (BULLISH/BEARISH)
            3. Get buy_trade (first $ amount in TREND RANGES)
            4. Get sell_trade (second $ amount in TREND RANGES)
            5. Set category to "etfs"

            Return the data in this exact JSON format:
            {{
                "assets": [
                    {{
                        "ticker": "XYZ",         # 3-4 letter code
                        "sentiment": "BULLISH",   # BULLISH if before BEARISH header, BEARISH if after
                        "buy_trade": 100.50,     # First $ amount in trend range
                        "sell_trade": 105.75,    # Second $ amount in trend range
                        "category": "etfs"       # Always "etfs"
                    }}
                ]
            }}

            Rules:
            - Pay careful attention to the BULLISH/BEARISH sections
            - Only include valid ETF entries with proper ticker symbols
            - Prices must be valid numbers
            - Format numbers as floats (e.g., 100.50, not $100.50)
            - Return ONLY the JSON object, no other text
            """
            
            # Get structured data from Mistral
            chat_response = self.mistral_client.chat.parse(
                model="ministral-8b-latest",
                messages=[{"role": "user", "content": prompt}],
                response_format=ETFData,
                temperature=0
            )
            
            # Get the parsed data
            etf_data = chat_response.choices[0].message.parsed
            
            # Convert to dictionary
            etf_dict = etf_data.model_dump()
            
            # Create CSV data
            csv_data = [
                {
                    "ticker": asset["ticker"],
                    "sentiment": asset["sentiment"],
                    "buy_trade": asset["buy_trade"],
                    "sell_trade": asset["sell_trade"],
                    "category": asset["category"]
                }
                for asset in etf_dict["assets"]
            ]
            
            # Save to CSV
            df = pd.DataFrame(csv_data)
            df.to_csv(self.output_file, index=False)
            print(f"\nSaved ETF data to: {self.output_file}")
            
            return etf_dict["assets"]
            
        except Exception as e:
            print(f"Error processing image: {e}")
            return []
            
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