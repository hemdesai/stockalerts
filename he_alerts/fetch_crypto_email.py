"""
Fetch and process the latest crypto email specifically.
"""
import asyncio
from datetime import datetime
from app.services.email.gmail_client import GmailClient
from app.services.email_processor import EmailProcessor
from app.core.database import AsyncSessionLocal

async def fetch_latest_crypto_email():
    """Fetch and process the latest crypto email."""
    gmail_client = GmailClient()
    email_processor = EmailProcessor()
    
    # Authenticate with Gmail
    if not await gmail_client.authenticate():
        print("Failed to authenticate with Gmail")
        return
    
    print("[OK] Authenticated with Gmail")
    
    # Fetch recent emails (last 48 hours)
    recent_emails = await gmail_client.fetch_recent_emails(hours=48)
    
    # Filter for crypto emails
    crypto_emails = [e for e in recent_emails if e.get('email_type') == 'crypto']
    
    print(f"\nFound {len(crypto_emails)} crypto emails")
    
    if crypto_emails:
        latest_crypto = crypto_emails[0]  # Already sorted by date
        print(f"\nLatest crypto email:")
        # Replace unicode characters that might cause issues
        subject = latest_crypto['subject'].encode('ascii', 'replace').decode('ascii')
        print(f"  Subject: {subject}")
        print(f"  Date: {latest_crypto['received_date']}")
        print(f"  Message ID: {latest_crypto['message_id']}")
        
        # Process the email
        async with AsyncSessionLocal() as db:
            result = await email_processor.process_specific_email(
                db=db,
                message_id=latest_crypto['message_id'],
                email_type='crypto'
            )
            
            if result.get('success'):
                print(f"\n[OK] Successfully processed: {result.get('extracted_count', 0)} stocks")
                
                # Show extracted data
                if result.get('result', {}).get('extracted_items'):
                    items = result['result']['extracted_items']
                    print(f"\nExtracted {len(items)} items:")
                    print("="*80)
                    
                    # Group by type
                    cryptos = [item for item in items if item['ticker'] in ['BTC', 'ETH', 'SOL', 'AVAX', 'AAVE']]
                    stocks = [item for item in items if item['ticker'] not in ['BTC', 'ETH', 'SOL', 'AVAX', 'AAVE']]
                    
                    if cryptos:
                        print("\nCRYPTOCURRENCIES:")
                        print(f"{'Ticker':8} {'Sentiment':10} {'Buy':>12} {'Sell':>12}")
                        print("-"*50)
                        for item in sorted(cryptos, key=lambda x: x['ticker']):
                            print(f"{item['ticker']:8} {item['sentiment']:10} ${item['buy_trade']:>11.2f} ${item['sell_trade']:>11.2f}")
                    
                    if stocks:
                        print("\nCRYPTO STOCKS (Derivative Exposures):")
                        print(f"{'Ticker':8} {'Sentiment':10} {'Buy':>12} {'Sell':>12}")
                        print("-"*50)
                        for item in sorted(stocks, key=lambda x: x['ticker']):
                            print(f"{item['ticker']:8} {item['sentiment']:10} ${item['buy_trade']:>11.2f} ${item['sell_trade']:>11.2f}")
            else:
                print(f"\n[ERROR] {result.get('message', 'Unknown error')}")

if __name__ == "__main__":
    asyncio.run(fetch_latest_crypto_email())