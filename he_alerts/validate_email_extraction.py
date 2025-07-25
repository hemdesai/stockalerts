"""
Simple email validation script that fetches and displays extracted data for review.
"""
import asyncio
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any

from app.services.email.gmail_client import GmailClient
from app.services.email_processor import EmailProcessor
from app.core.database import AsyncSessionLocal
from app.services.database.stock_service import StockService


async def validate_email_extraction(hours: int = 48):
    """Fetch emails and show extraction results for validation."""
    
    gmail_client = GmailClient()
    email_processor = EmailProcessor()
    
    # Authenticate
    if not await gmail_client.authenticate():
        print("Failed to authenticate with Gmail")
        return
    
    print("[OK] Authenticated with Gmail")
    
    # Fetch recent emails
    recent_emails = await gmail_client.fetch_recent_emails(hours=hours)
    print(f"\nFound {len(recent_emails)} emails in the last {hours} hours")
    
    # Group by type
    by_type = {}
    for email in recent_emails:
        email_type = email.get('email_type', 'unknown')
        if email_type not in by_type:
            by_type[email_type] = []
        by_type[email_type].append(email)
    
    print("\nEmails by type:")
    for email_type, emails in by_type.items():
        print(f"  {email_type}: {len(emails)} emails")
    
    # Process each type
    all_stocks = []
    for email_type, emails in by_type.items():
        if email_type == 'unknown':
            continue
            
        # Get latest email
        latest = emails[0]
        print(f"\n{'='*80}")
        print(f"Processing {email_type} email")
        # Handle unicode characters in subject
        subject = latest['subject'].encode('ascii', 'replace').decode('ascii')
        print(f"Subject: {subject}")
        print(f"Date: {latest.get('date', 'N/A')}")
        
        try:
            # Get full email
            email_data = await gmail_client.get_email_by_id(latest['message_id'])
            
            # Process it
            result = await email_processor.process_specific_email(
                email_data,
                email_type,
                latest['message_id']
            )
            
            if result['success'] and result.get('stocks'):
                stocks = result['stocks']
                print(f"Extracted {len(stocks)} stocks:")
                
                # Show first few
                for i, stock in enumerate(stocks[:5]):
                    print(f"  {stock['ticker']:6} | {stock.get('sentiment', 'N/A'):8} | "
                          f"Buy: ${stock.get('buy_trade', 0):>7.2f} | "
                          f"Sell: ${stock.get('sell_trade', 0):>7.2f}")
                
                if len(stocks) > 5:
                    print(f"  ... and {len(stocks) - 5} more")
                
                # Add to all stocks
                all_stocks.extend(stocks)
            else:
                print(f"ERROR: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"ERROR: {e}")
    
    # Compare with database
    print(f"\n{'='*80}")
    print("DATABASE COMPARISON")
    print("="*80)
    
    async with AsyncSessionLocal() as db:
        stock_service = StockService()
        
        new_count = 0
        changed_count = 0
        
        for stock in all_stocks:
            existing = await stock_service.get_stock_by_ticker_and_category(
                db, 
                stock['ticker'],
                stock['category']
            )
            
            if not existing:
                new_count += 1
                print(f"NEW: {stock['ticker']} ({stock['category']})")
            else:
                # Check for changes
                if (existing.buy_trade != stock.get('buy_trade') or 
                    existing.sell_trade != stock.get('sell_trade') or
                    existing.sentiment != stock.get('sentiment')):
                    changed_count += 1
                    print(f"CHANGED: {stock['ticker']} ({stock['category']})")
                    
                    if existing.buy_trade != stock.get('buy_trade'):
                        print(f"  Buy: ${existing.buy_trade} → ${stock.get('buy_trade')}")
                    if existing.sell_trade != stock.get('sell_trade'):
                        print(f"  Sell: ${existing.sell_trade} → ${stock.get('sell_trade')}")
                    if existing.sentiment != stock.get('sentiment'):
                        print(f"  Sentiment: {existing.sentiment} → {stock.get('sentiment')}")
    
    print(f"\nSummary: {new_count} new, {changed_count} changed out of {len(all_stocks)} total")
    
    # Export to CSV
    if all_stocks:
        df = pd.DataFrame(all_stocks)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_file = f'stocks_validation_{timestamp}.csv'
        df.to_csv(csv_file, index=False)
        print(f"\nExported to: {csv_file}")
        
        print("\nNOTE: Review the CSV file and database comparison above.")
        print("This is a validation report only - no database updates have been made.")
        print("\nTo update the database, use the fetch_latest_emails.py script after review.")


if __name__ == "__main__":
    asyncio.run(validate_email_extraction(hours=72))