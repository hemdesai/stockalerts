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


async def fetch_and_process_latest_emails():
    """Fetch latest Daily and Crypto emails and update database."""
    print("=" * 60)
    print("Fetching Latest Daily and Crypto Emails")
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
        
        # Filter for Daily and Crypto emails
        daily_emails = [e for e in recent_emails if e.get('email_type') == 'daily']
        crypto_emails = [e for e in recent_emails if e.get('email_type') == 'crypto']
        
        print(f"  - Daily emails: {len(daily_emails)}")
        print(f"  - Crypto emails: {len(crypto_emails)}")
        
        # Process the most recent of each type
        async with AsyncSessionLocal() as db:
            # Process Daily email
            if daily_emails:
                latest_daily = daily_emails[0]  # Already sorted by date
                print(f"\nProcessing DAILY email: {latest_daily['subject']}")
                print(f"  Date: {latest_daily['received_date']}")
                
                result = await email_processor.process_specific_email(
                    db=db,
                    message_id=latest_daily['message_id'],
                    email_type='daily'
                )
                
                if result.get('success'):
                    print(f"  [OK] Successfully processed: {result.get('extracted_count', 0)} stocks")
                    if result.get('result', {}).get('extracted_items'):
                        print("  Sample stocks:")
                        for stock in result['result']['extracted_items'][:3]:
                            print(f"    - {stock['ticker']}: Buy ${stock['buy_trade']}, Sell ${stock['sell_trade']}, {stock['sentiment']}")
                else:
                    print(f"  [ERROR] {result.get('message', 'Unknown error')}")
            
            # Process Crypto email
            if crypto_emails:
                latest_crypto = crypto_emails[0]  # Already sorted by date
                print(f"\nProcessing CRYPTO email: {latest_crypto['subject']}")
                print(f"  Date: {latest_crypto['received_date']}")
                
                result = await email_processor.process_specific_email(
                    db=db,
                    message_id=latest_crypto['message_id'],
                    email_type='crypto'
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
    # Fetch and process latest emails
    await fetch_and_process_latest_emails()
    
    # Export updated CSV
    csv_file = await export_updated_csv()
    
    print(f"\n{'='*60}")
    print("Update Complete!")
    print(f"CSV file: {csv_file}")


if __name__ == "__main__":
    asyncio.run(main())