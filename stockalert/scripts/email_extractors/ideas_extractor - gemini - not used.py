from . import BaseEmailExtractor
import google.generativeai as genai
import os
from dotenv import load_dotenv
import base64
import re

load_dotenv()

class IdeasEmailExtractor(BaseEmailExtractor):
    def __init__(self):
        super().__init__()
        self.GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyA2IF0zSd0ePLe_UcTeGiwRKTo-dFWkoew')
        self.setup_gemini()
        
    def setup_gemini(self):
        """Setup Gemini API"""
        genai.configure(api_key=self.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp-01-21')
    
    def extract_image_from_email(self):
        """Extract image from email with 'Investing Ideas Newsletter' in subject"""
        query = "subject:Investing Ideas Newsletter"
        content = self.get_email_content(query)
        if not content:
            return None
            
        # Extract base64 image from email content
        # Implementation depends on email format
        return content
    
    def process_image_with_gemini(self, image_data):
        """Process image using Gemini 2.0 thinking model"""
        try:
            prompt = """
            Analyze this investment table systematically:

            Step 1: Identify the table structure
            - Locate the 'TREND RANGES' columns (rightmost two columns)
            - Note: These contain the target numbers we need to extract

            Step 2: For each row, extract EXACTLY:
            a) Ticker symbol from first column
            b) Two numbers from TREND RANGES columns only
            c) Section context (Longs = BULLISH, Shorts = BEARISH)

            Step 3: Format each line precisely as:
            TICKER (SENTIMENT): first_range_number, second_range_number

            Critical rules:
            - Use ONLY numbers from TREND RANGES columns
            - Extract numbers EXACTLY as shown (no rounding or calculations)
            - Include ALL stocks from both sections
            - Maintain original decimal places
            - Verify each number matches the image exactly

            Example of correct extraction:
            TKO (BULLISH): 153.00, 170.00
            RH (BULLISH): 381.00, 454.00
            MPW (BEARISH): 3.99, 5.06
            EWCZ (BEARISH): 6.12, 6.99
            Process each row methodically and verify accuracy before returning.
            """
            
            response = self.model.generate_content([prompt, image_data])
            print("\nGemini Raw Response:")
            print(response.text)
            return response.text
            
        except Exception as e:
            print(f"Error processing image with Gemini: {e}")
            return None
    
    def parse_gemini_response(self, response_text):
        """Parse Gemini response into structured data"""
        parsed_data = []
        
        print("\nProcessing Gemini response...")
        
        for line in response_text.split('\n'):
            line = line.strip()
            # Skip empty lines, headers, and other formatting
            if not line or 'Longs' in line or 'Shorts' in line or '**' in line and ':' not in line:
                continue
                
            try:
                # Remove markdown formatting
                line = line.replace('*', '').strip()
                
                # Look for pattern: TICKER (SENTIMENT): number, number
                match = re.search(r'([A-Z]+)\s*\((BULLISH|BEARISH)\):\s*([\d,\.]+),\s*([\d,\.]+)', line)
                if match:
                    ticker = match.group(1)
                    sentiment = match.group(2)
                    buy_trade = float(match.group(3).replace(',', ''))
                    sell_trade = float(match.group(4).replace(',', ''))
                    
                    parsed_data.append({
                        'ticker': ticker,
                        'sentiment': sentiment,
                        'buy_trade': buy_trade,
                        'sell_trade': sell_trade,
                        'category': 'ideas'
                    })
                    print(f"✓ {ticker:<6} {sentiment:<8} Buy: {buy_trade:>8.2f}, Sell: {sell_trade:>8.2f}")
            except ValueError as e:
                print(f"Error parsing line '{line}': {e}")
                continue
        
        print(f"\nTotal stocks extracted: {len(parsed_data)}")
        return parsed_data
    
    def get_ideas(self):
        """Main method to extract and process ideas"""
        try:
            # Extract image from email
            print("Attempting to extract image from email...")
            image_data = self.extract_image_from_email()
            if not image_data:
                print("No image found in email")
                return None
            print("Successfully extracted image data")
            
            # Process image with Gemini
            print("Sending image to Gemini for processing...")
            gemini_response = self.process_image_with_gemini(image_data)
            if not gemini_response:
                print("No response from Gemini")
                return None
            print(f"Gemini response received: {gemini_response[:200]}...")  # First 200 chars
            
            # Parse response into structured data
            parsed_data = self.parse_gemini_response(gemini_response)
            print(f"Extracted {len(parsed_data)} ideas")
            
            return parsed_data
            
        except Exception as e:
            print(f"Error getting ideas: {e}")
            return None