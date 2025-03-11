import os
from pathlib import Path
import sys

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scripts.email_extractors.daily_extractor import DailyExtractor
import pandas as pd
from datetime import datetime, timedelta
import pytz

def test_daily_extraction():
    print("Starting daily extraction test...")
    print(f"Current directory: {Path.cwd()}")
    
    try:
        extractor = DailyExtractor()
        print("Extractor initialized")
        
        # Test email search first
        today = datetime.now().strftime('%Y/%m/%d')
        three_days_ago = (datetime.now() - timedelta(days=3)).strftime('%Y/%m/%d')
        query = f'subject:"RISK RANGE" after:{three_days_ago}'
        
        print(f"Searching for emails with query: {query}")
        messages = extractor.gmail_service.users().messages().list(
            userId='me', q=query, maxResults=5
        ).execute()
        
        if 'messages' in messages:
            print(f"Found {len(messages['messages'])} messages")
            
            # Show subject lines of found messages
            for msg in messages['messages']:
                msg_data = extractor.gmail_service.users().messages().get(
                    userId='me', id=msg['id'], format='metadata',
                    metadataHeaders=['subject', 'date']
                ).execute()
                
                headers = msg_data['payload']['headers']
                subject = next(h['value'] for h in headers if h['name'] == 'Subject')
                date = next(h['value'] for h in headers if h['name'] == 'Date')
                print(f"Found email: {subject} from {date}")
        else:
            print("No messages found")
        
        # Continue with extraction
        data = extractor.extract()
        
        if data:
            df = pd.DataFrame(data)
            
            # Add timestamp
            est = pytz.timezone('US/Eastern')
            timestamp = datetime.now(est).strftime("%Y%m%d_%H%M%S")
            
            # Save to data directory with timestamp
            output_path = Path(__file__).parent.parent.parent / 'data' / f'daily_extract_{timestamp}.csv'
            df.to_csv(output_path, index=False)
            
            print("\nExtracted Daily Data Preview:")
            print(df[['ticker', 'sentiment', 'buy_trade', 'sell_trade']].head())
            print(f"\nTotal rows extracted: {len(df)}")
            print(f"Data saved to: {output_path}")
            
            # Print unique categories and sentiments for verification
            print("\nUnique Categories:", df['category'].unique())
            print("Sentiment Distribution:")
            print(df['sentiment'].value_counts())
            
            return df
        else:
            print("No data extracted")
            return None
    except Exception as e:
        print(f"Error in test_daily_extraction: {e}")
        return None

if __name__ == "__main__":
    test_daily_extraction() 