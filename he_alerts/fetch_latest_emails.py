"""
Fetch latest Daily and Crypto emails and update the database.
"""
import asyncio
from datetime import datetime, timedelta
import pytz
from app.services.email.gmail_client import GmailClient
from app.services.email_processor import EmailProcessor
from app.core.database import AsyncSessionLocal
from app.services.database.stock_service import StockService
from sqlalchemy import select
from app.models.stock import Stock


async def fetch_and_process_latest_emails(email_types: list = None):
    """Fetch latest emails and update database.
    
    Args:
        email_types: List of email types to process. 
                    Defaults to ['daily', 'crypto'] if not specified.
                    Can include: ['daily', 'crypto', 'etfs', 'ideas']
    """
    if email_types is None:
        email_types = ['daily', 'crypto']
    
    print("=" * 60)
    print(f"Fetching Latest Emails: {', '.join(email_types)}")
    print("=" * 60)
    
    gmail_client = GmailClient()
    email_processor = EmailProcessor()
    
    # Authenticate with Gmail
    if not await gmail_client.authenticate():
        print("Failed to authenticate with Gmail")
        return
    
    print("[OK] Authenticated with Gmail")
    
    # Fetch recent emails (last 48 hours)
    hours = 48
    print(f"\nFetching emails from last {hours} hours...")
    
    try:
        recent_emails = await gmail_client.fetch_recent_emails(hours=hours)
        
        if not recent_emails:
            print("No recent emails found")
            return
        
        print(f"Found {len(recent_emails)} total emails")
        
        # Filter emails by requested types
        emails_by_type = {}
        for email_type in email_types:
            filtered = [e for e in recent_emails if e.get('email_type') == email_type]
            if filtered:
                emails_by_type[email_type] = filtered
                print(f"  - {email_type.capitalize()} emails: {len(filtered)}")
        
        # Process the most recent of each type
        async with AsyncSessionLocal() as db:
            for email_type in email_types:
                if email_type in emails_by_type and emails_by_type[email_type]:
                    latest_email = emails_by_type[email_type][0]  # Already sorted by date
                    print(f"\nProcessing {email_type.upper()} email: {latest_email['subject']}")
                    print(f"  Date: {latest_email['received_date']}")
                    
                    result = await email_processor.process_specific_email(
                        db=db,
                        message_id=latest_email['message_id'],
                        email_type=email_type
                    )
                    
                    if result.get('success'):
                        print(f"  [OK] Successfully processed: {result.get('extracted_count', 0)} stocks")
                        if result.get('result', {}).get('extracted_items'):
                            print("  Sample stocks:")
                            for stock in result['result']['extracted_items'][:3]:
                                print(f"    - {stock['ticker']}: Buy ${stock['buy_trade']}, Sell ${stock['sell_trade']}, {stock['sentiment']}")
                    else:
                        print(f"  [ERROR] {result.get('message', 'Unknown error')}")
                    
    except Exception as e:
        print(f"Error fetching/processing emails: {e}")
        import traceback
        traceback.print_exc()
    
    # Show database summary
    print("\n" + "=" * 60)
    print("Database Summary After Update")
    print("=" * 60)
    
    async with AsyncSessionLocal() as db:
        stock_service = StockService()
        
        # Get counts by category
        for category in ['daily', 'digitalassets', 'etfs', 'ideas']:
            stocks = await stock_service.get_stocks_by_category(db, category)
            active_count = len([s for s in stocks if s.is_active])
            
            print(f"\n{category.upper()}:")
            print(f"  Total stocks: {len(stocks)}")
            print(f"  Active stocks: {active_count}")
            
            # Show last update time
            if stocks:
                latest_update = max(s.updated_at for s in stocks)
                print(f"  Last updated: {latest_update.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Show sample stocks for daily and crypto
                if category in ['daily', 'digitalassets']:
                    print("  Sample stocks:")
                    for stock in sorted(stocks, key=lambda x: x.ticker)[:5]:
                        print(f"    - {stock.ticker}: Buy ${stock.buy_trade}, Sell ${stock.sell_trade}, {stock.sentiment}")


async def export_updated_csv():
    """Export updated database to CSV."""
    from datetime import datetime
    import pandas as pd
    
    async with AsyncSessionLocal() as db:
        stock_service = StockService()
        
        # Get all stocks by category
        all_stocks = []
        for category in ['daily', 'digitalassets', 'etfs', 'ideas']:
            stocks = await stock_service.get_stocks_by_category(db, category, active_only=False, limit=1000)
            all_stocks.extend(stocks)
        
        # Convert to DataFrame
        data = []
        for stock in all_stocks:
            data.append({
                'ticker': stock.ticker,
                'name': stock.name,
                'category': stock.category,
                'sentiment': stock.sentiment,
                'buy_trade': stock.buy_trade,
                'sell_trade': stock.sell_trade,
                'am_price': stock.am_price,
                'pm_price': stock.pm_price,
                'last_price_update': stock.last_price_update,
                'source_email_id': stock.source_email_id,
                'is_active': stock.is_active,
                'created_at': stock.created_at,
                'updated_at': stock.updated_at
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values(['category', 'ticker'])
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'stocks_updated_{timestamp}.csv'
        
        # Export
        df.to_csv(filename, index=False)
        print(f"\n[OK] Exported {len(df)} stocks to {filename}")
        
        # Show summary
        print("\nCategory Summary:")
        for category, count in df['category'].value_counts().items():
            print(f"  {category}: {count} stocks")
        
        # Show recent updates
        print("\nRecently Updated Stocks (last 24 hours):")
        recent_cutoff = datetime.now() - timedelta(hours=24)
        recent_stocks = df[pd.to_datetime(df['updated_at']) > recent_cutoff]
        if not recent_stocks.empty:
            print(f"  {len(recent_stocks)} stocks updated in last 24 hours")
            for category in recent_stocks['category'].unique():
                cat_stocks = recent_stocks[recent_stocks['category'] == category]
                print(f"  - {category}: {len(cat_stocks)} stocks")
                # Show tickers
                tickers = sorted(cat_stocks['ticker'].tolist())
                print(f"    {', '.join(tickers[:10])}{' ...' if len(tickers) > 10 else ''}")
        else:
            print("  No stocks updated in last 24 hours")
        
        return filename


async def main():
    """Main function."""
    import sys
    
    # Check if email types were specified
    email_types = None
    if len(sys.argv) > 1:
        email_types = sys.argv[1:]
        print(f"Processing specific email types: {email_types}")
    
    # Fetch and process latest emails
    await fetch_and_process_latest_emails(email_types)
    
    # Export updated CSV
    csv_file = await export_updated_csv()
    
    print(f"\n{'='*60}")
    print("Update Complete!")
    print(f"CSV file: {csv_file}")


if __name__ == "__main__":
    asyncio.run(main())