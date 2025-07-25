"""
Generate a validation report for email extraction WITHOUT updating the database.
Based on the working fetch_latest_emails.py script.
"""
import asyncio
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any

from app.services.email.gmail_client import GmailClient
from app.services.email_processor import EmailProcessor
from app.core.database import AsyncSessionLocal
from app.services.database.stock_service import StockService
from app.core.logging import get_logger

logger = get_logger(__name__)


async def generate_validation_report():
    """Generate validation report for email extraction."""
    gmail_client = GmailClient()
    email_processor = EmailProcessor()
    
    # Authenticate with Gmail
    if not await gmail_client.authenticate():
        print("Failed to authenticate with Gmail")
        return
    
    print("[OK] Authenticated with Gmail")
    
    # Fetch recent emails (last 72 hours)
    hours = 72
    recent_emails = await gmail_client.fetch_recent_emails(hours=hours)
    print(f"Found {len(recent_emails)} emails from the last {hours} hours")
    
    # Group emails by type
    email_groups = {}
    for email in recent_emails:
        email_type = email.get('email_type', 'unknown')
        if email_type not in email_groups:
            email_groups[email_type] = []
        email_groups[email_type].append(email)
    
    print("\nEmails by type:")
    for email_type, emails in email_groups.items():
        print(f"  {email_type}: {len(emails)} emails")
    
    # We're interested in daily and crypto emails
    target_types = ['daily', 'crypto']
    
    all_extracted_stocks = []
    extraction_summary = {}
    
    # Don't update database - just extract and compare
    async with AsyncSessionLocal() as db:
        for email_type in target_types:
            if email_type not in email_groups:
                print(f"\nNo {email_type} emails found")
                continue
            
            # Get latest email of this type
            latest_email = email_groups[email_type][0]  # Already sorted by date
            
            print(f"\n{'='*80}")
            print(f"Processing {email_type.upper()} email")
            print(f"Message ID: {latest_email['message_id']}")
            
            # Clean subject for display
            subject = latest_email['subject'].encode('ascii', 'replace').decode('ascii')
            print(f"Subject: {subject}")
            
            # Process the email using EmailProcessor
            result = await email_processor.process_recent_emails(
                db,
                email_types=[email_type],
                hours=hours,
                update_database=False  # Important: Don't update DB
            )
            
            if result['success']:
                processed = result['results'].get(email_type, {})
                if processed.get('success'):
                    stocks = processed.get('extracted_items', [])
                    print(f"\nExtracted {len(stocks)} stocks:")
                    
                    # Show sample
                    for i, stock in enumerate(stocks[:5]):
                        print(f"  {stock['ticker']:6} | {stock.get('sentiment', 'N/A'):8} | "
                              f"Buy: ${stock.get('buy_trade', 0):>7.2f} | "
                              f"Sell: ${stock.get('sell_trade', 0):>7.2f}")
                    
                    if len(stocks) > 5:
                        print(f"  ... and {len(stocks) - 5} more")
                    
                    # Store for later processing
                    extraction_summary[email_type] = {
                        'count': len(stocks),
                        'stocks': stocks,
                        'email_id': latest_email['message_id']
                    }
                    
                    # Add category to each stock
                    for stock in stocks:
                        stock['category'] = 'digitalassets' if email_type == 'crypto' else email_type
                    
                    all_extracted_stocks.extend(stocks)
                else:
                    print(f"ERROR: {processed.get('message', 'Unknown error')}")
            else:
                print(f"ERROR: {result.get('message', 'Unknown error')}")
    
    # Generate validation report
    if all_extracted_stocks:
        print(f"\n{'='*80}")
        print("VALIDATION REPORT")
        print("="*80)
        
        # Compare with database
        async with AsyncSessionLocal() as db:
            stock_service = StockService()
            
            new_stocks = []
            changed_stocks = []
            unchanged_stocks = []
            suspicious_changes = []
            
            for stock in all_extracted_stocks:
                existing = await stock_service.get_stock_by_ticker_and_category(
                    db,
                    stock['ticker'],
                    stock['category']
                )
                
                if not existing:
                    new_stocks.append(stock)
                else:
                    # Check for changes
                    changes = {}
                    
                    # Check buy price
                    if existing.buy_trade != stock.get('buy_trade'):
                        old_val = existing.buy_trade or 0
                        new_val = stock.get('buy_trade', 0)
                        if old_val > 0:
                            pct = abs((new_val - old_val) / old_val * 100)
                        else:
                            pct = 100 if new_val > 0 else 0
                        
                        changes['buy_trade'] = {
                            'old': old_val,
                            'new': new_val,
                            'pct': pct
                        }
                        
                        if pct > 20:
                            stock['suspicious'] = True
                    
                    # Check sell price
                    if existing.sell_trade != stock.get('sell_trade'):
                        old_val = existing.sell_trade or 0
                        new_val = stock.get('sell_trade', 0)
                        if old_val > 0:
                            pct = abs((new_val - old_val) / old_val * 100)
                        else:
                            pct = 100 if new_val > 0 else 0
                        
                        changes['sell_trade'] = {
                            'old': old_val,
                            'new': new_val,
                            'pct': pct
                        }
                        
                        if pct > 20:
                            stock['suspicious'] = True
                    
                    # Check sentiment
                    if existing.sentiment != stock.get('sentiment'):
                        changes['sentiment'] = {
                            'old': existing.sentiment,
                            'new': stock.get('sentiment')
                        }
                        
                        # Sentiment flip is suspicious
                        if (existing.sentiment == 'bullish' and stock.get('sentiment') == 'bearish') or \
                           (existing.sentiment == 'bearish' and stock.get('sentiment') == 'bullish'):
                            stock['suspicious'] = True
                    
                    if changes:
                        stock['changes'] = changes
                        if stock.get('suspicious'):
                            suspicious_changes.append(stock)
                        else:
                            changed_stocks.append(stock)
                    else:
                        unchanged_stocks.append(stock)
        
        # Print summary
        print(f"\nSummary:")
        print(f"  Total extracted: {len(all_extracted_stocks)}")
        print(f"  New stocks: {len(new_stocks)}")
        print(f"  Changed stocks: {len(changed_stocks)}")
        print(f"  Unchanged stocks: {len(unchanged_stocks)}")
        print(f"  Suspicious changes: {len(suspicious_changes)}")
        
        # Show suspicious changes
        if suspicious_changes:
            print(f"\n⚠️  SUSPICIOUS CHANGES (>20% price change or sentiment flip):")
            print("-" * 80)
            for stock in suspicious_changes[:10]:
                print(f"\n{stock['ticker']} ({stock['category']}):")
                for field, change in stock.get('changes', {}).items():
                    if field == 'sentiment':
                        print(f"  {field}: {change['old']} → {change['new']} ⚠️")
                    else:
                        print(f"  {field}: ${change['old']:.2f} → ${change['new']:.2f} "
                              f"({change['pct']:.1f}% change)")
            
            if len(suspicious_changes) > 10:
                print(f"\n... and {len(suspicious_changes) - 10} more suspicious changes")
        
        # Show new stocks
        if new_stocks:
            print(f"\n✨ NEW STOCKS:")
            print("-" * 80)
            print(f"{'Ticker':8} {'Category':15} {'Sentiment':10} {'Buy':>10} {'Sell':>10}")
            print("-" * 60)
            
            for stock in new_stocks[:10]:
                print(f"{stock['ticker']:8} {stock['category']:15} "
                      f"{stock.get('sentiment', 'N/A'):10} "
                      f"${stock.get('buy_trade', 0):>9.2f} "
                      f"${stock.get('sell_trade', 0):>9.2f}")
            
            if len(new_stocks) > 10:
                print(f"\n... and {len(new_stocks) - 10} more new stocks")
        
        # Export to CSV
        df = pd.DataFrame(all_extracted_stocks)
        
        # Add validation columns
        df['status'] = df.apply(lambda row: 'NEW' if row['ticker'] in [s['ticker'] for s in new_stocks]
                                else 'SUSPICIOUS' if row.get('suspicious', False)
                                else 'CHANGED' if row.get('changes')
                                else 'UNCHANGED', axis=1)
        
        # Generate timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f'validation_report_{timestamp}.csv'
        
        # Export
        df.to_csv(csv_filename, index=False)
        
        print(f"\n{'='*80}")
        print("VALIDATION COMPLETE")
        print("="*80)
        print(f"\nValidation report exported to: {csv_filename}")
        print("\nTo review:")
        print(f"1. Open {csv_filename} in Excel or similar")
        print("2. Review stocks marked as 'NEW' or 'SUSPICIOUS'")
        print("3. Check that extraction values are correct")
        print("\nNOTE: No database updates were made. This is a validation report only.")
        print("\nTo update the database after review:")
        print("  python he_alerts/fetch_latest_emails.py")
        
        return csv_filename
    else:
        print("\nNo stocks were extracted from emails.")
        return None


if __name__ == "__main__":
    asyncio.run(generate_validation_report())