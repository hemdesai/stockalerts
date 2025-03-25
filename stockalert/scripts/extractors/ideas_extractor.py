import sys
import os
from pathlib import Path
from pydantic import BaseModel
import pandas as pd
from mistralai import Mistral, ImageURLChunk
from datetime import datetime
import base64
import re

# Add the project root to Python path when running directly
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.append(str(project_root))
    from stockalert.utils.env_loader import get_env
    from stockalert.scripts.extractors import BaseEmailExtractor
else:
    from stockalert.utils.env_loader import get_env
    from . import BaseEmailExtractor

class IdeasAsset(BaseModel):
    ticker: str
    sentiment: str
    buy_trade: float
    sell_trade: float
    category: str = "ideas"


class IdeasData(BaseModel):
    assets: list[IdeasAsset]


class IdeasEmailExtractor(BaseEmailExtractor):
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
    
    def process_image(self, image_path):
        """Process image using Mistral OCR API"""
        try:
            # Ensure the image path exists
            if not os.path.exists(image_path):
                print(f"Error: Image file not found at {image_path}")
                return []
                
            # Read the image file
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
                
            # Convert the image to a data URL for Mistral OCR
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            data_url = f"data:image/png;base64,{image_base64}"
            
            # Process OCR to get markdown output
            print("Processing with Mistral OCR...")
            ocr_response = self.mistral_client.ocr.process(
                document=ImageURLChunk(image_url=data_url), 
                model="mistral-ocr-latest"
            )
            ocr_md = ocr_response.pages[0].markdown
            
            # Print a sample of the OCR text for debugging
            print("\nSample OCR Text (first 500 chars):")
            print(ocr_md[:500])
            
            # Try manual parsing first
            ideas_data = self.manual_parse_ocr_text(ocr_md)
            
            # If manual parsing doesn't work, try the chat API
            if not ideas_data or len(ideas_data) < 3:
                print("Manual parsing extracted too few ideas, using Mistral API for assistance...")
                # Prompt to convert OCR markdown to structured ideas JSON
                prompt = f"""
                Below is the OCR output in markdown format from a stock ideas table image. The table is split into two sections: "Longs" (BULLISH stocks) and "Shorts" (BEARISH stocks).

                Each row in the table contains:
                - Stock ticker (e.g., AAPL, MSFT)
                - Closing price
                - Buy Trade price
                - Sell Trade price
                - Other information like upside/downside percentages

                Text from OCR:
                <BEGIN_IMAGE_OCR>
                {ocr_md}
                <END_IMAGE_OCR>

                I need you to carefully extract ALL stock tickers from BOTH the Longs and Shorts sections, along with their corresponding Buy Trade and Sell Trade values.

                Extract the actual values from the OCR text. DO NOT use any hardcoded values or make up data.

                Convert this into a structured JSON response with the following format:
                {{
                    "assets": [
                        {{
                            "ticker": "AAPL",
                            "sentiment": "BULLISH" if in Longs section, "BEARISH" if in Shorts section,
                            "buy_trade": extracted buy trade value as float,
                            "sell_trade": extracted sell trade value as float,
                            "category": "ideas"
                        }},
                        ... and so on for all stocks found in the OCR text
                    ]
                }}

                Rules:
                - Include ALL stocks found in the OCR text
                - Set sentiment to "BULLISH" for stocks in the Longs section and "BEARISH" for stocks in the Shorts section
                - Format numbers as floats without commas (e.g., 150.67, not $150.67)
                - Set category to "ideas" for all stocks
                - Return ONLY the JSON object, no other text
                """
                
                # Get structured data from Mistral
                chat_response = self.mistral_client.chat.parse(
                    model="ministral-8b-latest",
                    messages=[{"role": "user", "content": prompt}],
                    response_format=IdeasData,
                    temperature=0
                )
                
                # Get the parsed data
                ideas_data = chat_response.choices[0].message.parsed
                
                # Convert to dictionary
                ideas_dict = ideas_data.model_dump()
                ideas_data = ideas_dict["assets"]
            
            # Create CSV data
            csv_data = [
                {
                    "ticker": asset["ticker"],
                    "sentiment": asset["sentiment"],
                    "buy_trade": asset["buy_trade"],
                    "sell_trade": asset["sell_trade"],
                    "category": asset["category"]
                }
                for asset in ideas_data
            ]
            
            # Create a DataFrame and save to CSV
            df = pd.DataFrame(csv_data)
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / 'data'
            csv_path = data_dir / 'ideas.csv'
            df.to_csv(csv_path, index=False)
            print(f"Saved ideas data to: {csv_path}")
            print(f"Total tickers extracted: {len(csv_data)}")
            
            return ideas_data
            
        except Exception as e:
            print(f"Error processing image: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def manual_parse_ocr_text(self, ocr_text):
        """Manually parse OCR text to extract ideas assets"""
        assets = []
        
        # Split into sections
        sections = ocr_text.split('# Shorts')
        if len(sections) != 2:
            sections = ocr_text.split('Shorts')
        
        if len(sections) == 2:
            longs_section = sections[0]
            shorts_section = sections[1]
        else:
            print("Warning: Could not split into sections properly")
            # Try to find longs and shorts sections using regex
            longs_match = re.search(r'(?:# )?Longs', ocr_text, re.IGNORECASE)
            shorts_match = re.search(r'(?:# )?Shorts', ocr_text, re.IGNORECASE)
            
            if longs_match and shorts_match:
                longs_section = ocr_text[longs_match.end():shorts_match.start()]
                shorts_section = ocr_text[shorts_match.end():]
            else:
                # Default to treating all as longs
                longs_section = ocr_text
                shorts_section = ""
        
        # Parse longs (BULLISH)
        print("Parsing LONGS section...")
        longs_lines = longs_section.strip().split('\n')
        for line in longs_lines:
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
                parts = [p for p in parts if p]  # Remove empty parts
                
                if len(parts) >= 3:
                    try:
                        # Extract ticker
                        ticker = parts[0].strip()
                        
                        # Skip header rows and separator rows
                        if ticker.lower() in ['stock', '-----', ''] or '-' in ticker or 'closing' in ticker.lower() or 'trend' in ticker.lower():
                            continue
                        
                        # Extract trend ranges
                        trend_parts = []
                        for part in parts[2:]:
                            if '$' in part or any(c.isdigit() for c in part):
                                trend_parts.append(part)
                        
                        if len(trend_parts) >= 2:
                            # Clean up and convert to float
                            buy_str = trend_parts[0].replace('$', '').replace(',', '').strip()
                            sell_str = trend_parts[1].replace('$', '').replace(',', '').strip()
                            
                            # Extract just the numeric part
                            buy_match = re.search(r'([\d\.]+)', buy_str)
                            sell_match = re.search(r'([\d\.]+)', sell_str)
                            
                            if buy_match and sell_match:
                                buy_trade = float(buy_match.group(1))
                                sell_trade = float(sell_match.group(1))
                                
                                # Validate ticker format (2-5 uppercase letters)
                                if re.match(r'^[A-Z]{1,5}$', ticker):
                                    assets.append({
                                        "ticker": ticker,
                                        "sentiment": "BULLISH",
                                        "buy_trade": buy_trade,
                                        "sell_trade": sell_trade,
                                        "category": "ideas"
                                    })
                                    print(f"Extracted BULLISH ticker: {ticker}, buy: {buy_trade}, sell: {sell_trade}")
                    except Exception as e:
                        print(f"Error parsing line in longs section: {line}, Error: {e}")
        
        # Parse shorts (BEARISH)
        print("Parsing SHORTS section...")
        shorts_lines = shorts_section.strip().split('\n')
        for line in shorts_lines:
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
                parts = [p for p in parts if p]  # Remove empty parts
                
                if len(parts) >= 3:
                    try:
                        # Extract ticker
                        ticker = parts[0].strip()
                        
                        # Skip header rows and separator rows
                        if ticker.lower() in ['stock', '-----', ''] or '-' in ticker or 'closing' in ticker.lower() or 'trend' in ticker.lower():
                            continue
                        
                        # Extract trend ranges
                        trend_parts = []
                        for part in parts[2:]:
                            if '$' in part or any(c.isdigit() for c in part):
                                trend_parts.append(part)
                        
                        if len(trend_parts) >= 2:
                            # Clean up and convert to float
                            buy_str = trend_parts[0].replace('$', '').replace(',', '').strip()
                            sell_str = trend_parts[1].replace('$', '').replace(',', '').strip()
                            
                            # Extract just the numeric part
                            buy_match = re.search(r'([\d\.]+)', buy_str)
                            sell_match = re.search(r'([\d\.]+)', sell_str)
                            
                            if buy_match and sell_match:
                                buy_trade = float(buy_match.group(1))
                                sell_trade = float(sell_match.group(1))
                                
                                # Validate ticker format (2-5 uppercase letters)
                                if re.match(r'^[A-Z]{1,5}$', ticker):
                                    assets.append({
                                        "ticker": ticker,
                                        "sentiment": "BEARISH",
                                        "buy_trade": buy_trade,
                                        "sell_trade": sell_trade,
                                        "category": "ideas"
                                    })
                                    print(f"Extracted BEARISH ticker: {ticker}, buy: {buy_trade}, sell: {sell_trade}")
                    except Exception as e:
                        print(f"Error parsing line in shorts section: {line}, Error: {e}")
        
        # Try an alternative parsing approach if we didn't get enough assets
        if len(assets) < 5:
            print("Trying alternative parsing approach...")
            # Look for patterns like "TKO | $150.67 | $144.00 | $175.00"
            pattern = r'([A-Z]{1,5})\s*\|\s*\$?([\d\.,]+)\s*\|\s*\$?([\d\.,]+)\s*\|\s*\$?([\d\.,]+)'
            
            # Find all matches in the longs section
            longs_matches = re.findall(pattern, longs_section)
            for match in longs_matches:
                ticker = match[0].strip()
                try:
                    # Validate ticker format (1-5 uppercase letters)
                    if not re.match(r'^[A-Z]{1,5}$', ticker):
                        continue
                        
                    # Skip if we already have this ticker
                    if any(a["ticker"] == ticker for a in assets):
                        continue
                        
                    buy_trade = float(match[2].replace(',', ''))
                    sell_trade = float(match[3].replace(',', ''))
                    
                    assets.append({
                        "ticker": ticker,
                        "sentiment": "BULLISH",
                        "buy_trade": buy_trade,
                        "sell_trade": sell_trade,
                        "category": "ideas"
                    })
                    print(f"Alt method: Extracted BULLISH ticker: {ticker}, buy: {buy_trade}, sell: {sell_trade}")
                except Exception as e:
                    print(f"Error in alternative parsing for {ticker}: {e}")
            
            # Find all matches in the shorts section
            shorts_matches = re.findall(pattern, shorts_section)
            for match in shorts_matches:
                ticker = match[0].strip()
                try:
                    # Validate ticker format (1-5 uppercase letters)
                    if not re.match(r'^[A-Z]{1,5}$', ticker):
                        continue
                        
                    # Skip if we already have this ticker
                    if any(a["ticker"] == ticker for a in assets):
                        continue
                        
                    buy_trade = float(match[2].replace(',', ''))
                    sell_trade = float(match[3].replace(',', ''))
                    
                    assets.append({
                        "ticker": ticker,
                        "sentiment": "BEARISH",
                        "buy_trade": buy_trade,
                        "sell_trade": sell_trade,
                        "category": "ideas"
                    })
                    print(f"Alt method: Extracted BEARISH ticker: {ticker}, buy: {buy_trade}, sell: {sell_trade}")
                except Exception as e:
                    print(f"Error in alternative parsing for {ticker}: {e}")
        
        # Try a third approach with more relaxed pattern matching if we still don't have enough assets
        if len(assets) < 5:
            print("Trying third parsing approach with more relaxed pattern matching...")
            # Look for lines with ticker-like patterns (1-5 uppercase letters) followed by numbers
            ticker_pattern = r'\b([A-Z]{1,5})\b'
            ticker_matches = re.findall(ticker_pattern, ocr_text)
            
            # Process each potential ticker
            for ticker in ticker_matches:
                # Skip if we already have this ticker
                if any(a["ticker"] == ticker for a in assets):
                    continue
                
                # Validate ticker format (1-5 uppercase letters)
                if not re.match(r'^[A-Z]{1,5}$', ticker):
                    continue
                
                # Look for numbers near this ticker
                ticker_pos = ocr_text.find(ticker)
                if ticker_pos != -1:
                    # Look for numbers in the next 100 characters
                    context = ocr_text[ticker_pos:ticker_pos + 100]
                    # Find all numbers in this context
                    number_pattern = r'\$?([\d\.,]+)'
                    number_matches = re.findall(number_pattern, context)
                    
                    if len(number_matches) >= 2:
                        try:
                            # Assume the first two numbers are buy and sell
                            buy_trade = float(number_matches[0].replace(',', ''))
                            sell_trade = float(number_matches[1].replace(',', ''))
                            
                            # Determine sentiment based on position in the document
                            if ticker_pos < len(ocr_text) / 2:  # First half is usually longs
                                sentiment = "BULLISH"
                            else:  # Second half is usually shorts
                                sentiment = "BEARISH"
                            
                            assets.append({
                                "ticker": ticker,
                                "sentiment": sentiment,
                                "buy_trade": buy_trade,
                                "sell_trade": sell_trade,
                                "category": "ideas"
                            })
                            print(f"Third method: Extracted {sentiment} ticker: {ticker}, buy: {buy_trade}, sell: {sell_trade}")
                        except Exception as e:
                            print(f"Error in third parsing approach for {ticker}: {e}")
    
        print(f"Manually parsed {len(assets)} assets")
        return assets
    
    def extract(self):
        """Main method to extract ideas data from the local image"""
        try:
            print(f"Starting ideas extraction from local image at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
            
            # Define the path to the local image
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / 'data'
            image_path = data_dir / 'ideas.png'
            
            if not os.path.exists(image_path):
                print(f"Error: Image file not found at {image_path}")
                print("Please add ideas.png to the data folder.")
                return []
            
            # Process the image
            ideas_data = self.process_image(image_path)
            
            if ideas_data:
                # Read the CSV file to return the data
                csv_path = data_dir / 'ideas.csv'
                
                if csv_path.exists():
                    df = pd.read_csv(csv_path)
                    return df.to_dict('records')
                else:
                    print(f"CSV file not found at {csv_path}")
                    return []
            else:
                print("Ideas extraction failed")
                return []
        except Exception as e:
            print(f"Error in extract method: {e}")
            import traceback
            traceback.print_exc()
            return []


if __name__ == "__main__":
    # Create the extractor
    extractor = IdeasEmailExtractor()
    
    # Extract from local image
    ideas_data = extractor.extract()
    
    # Print the results
    if ideas_data:
        print("\nExtracted Ideas Data:")
        print(f"Total tickers: {len(ideas_data)}")
        bullish = [a for a in ideas_data if a['sentiment'] == 'BULLISH']
        bearish = [a for a in ideas_data if a['sentiment'] == 'BEARISH']
        print(f"BULLISH tickers: {len(bullish)}")
        print(f"BEARISH tickers: {len(bearish)}")
    else:
        print("No ideas data extracted.")