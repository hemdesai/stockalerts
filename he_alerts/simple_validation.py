"""
Simple validation script that shows what would be extracted without updating DB.
"""
import asyncio
import pandas as pd
from datetime import datetime

from app.services.email.gmail_client import GmailClient
from app.services.email_processor import EmailProcessor
from app.core.database import AsyncSessionLocal
from app.services.database.stock_service import StockService


async def simple_validation():
    """Run simple validation of email extraction."""
    
    print("HEDGEYE EMAIL EXTRACTION VALIDATION")
    print("=" * 80)
    print("This script will:")
    print("1. Fetch the latest Daily and Crypto emails")
    print("2. Extract stock data from them")
    print("3. Compare with current database values")
    print("4. Export a CSV for your review")
    print("5. NOT update the database")
    print("=" * 80)
    
    # Use the same approach as fetch_latest_emails.py
    gmail_client = GmailClient()
    email_processor = EmailProcessor()
    
    # Authenticate
    if not await gmail_client.authenticate():
        print("\n[ERROR] Failed to authenticate with Gmail")
        return
    
    print("\n[OK] Authenticated with Gmail")
    
    # Process emails but store results instead of updating DB
    extraction_results = {}
    
    async with AsyncSessionLocal() as db:
        # Process daily and crypto emails
        for email_type in ['daily', 'crypto']:
            print(f"\n[INFO] Processing {email_type} emails...")
            
            result = await email_processor.process_recent_emails(
                db,
                email_types=[email_type],
                hours=72
            )
            
            if result['success']:
                type_result = result['results'].get(email_type, {})
                if type_result.get('success'):
                    items = type_result.get('extracted_items', [])
                    extraction_results[email_type] = items
                    print(f"[OK] Extracted {len(items)} stocks from {email_type}")
                else:
                    print(f"[ERROR] Failed to extract from {email_type}: {type_result.get('message')}")
            else:
                print(f"[ERROR] Failed to process {email_type}: {result.get('message')}")
    
    # Now compare with database
    if extraction_results:
        print("\n" + "="*80)
        print("COMPARING WITH DATABASE")
        print("="*80)
        
        all_comparisons = []
        
        async with AsyncSessionLocal() as db:
            stock_service = StockService()
            
            for email_type, items in extraction_results.items():
                category = 'digitalassets' if email_type == 'crypto' else email_type
                
                for item in items:
                    comparison = {
                        'ticker': item['ticker'],
                        'category': category,
                        'new_sentiment': item.get('sentiment'),
                        'new_buy': item.get('buy_trade'),
                        'new_sell': item.get('sell_trade'),
                        'status': 'UNKNOWN'
                    }
                    
                    # Get existing stock
                    existing = await stock_service.get_stock_by_ticker_and_category(
                        db, item['ticker'], category
                    )
                    
                    if not existing:
                        comparison['status'] = 'NEW'
                        comparison['old_sentiment'] = ''
                        comparison['old_buy'] = ''
                        comparison['old_sell'] = ''
                        comparison['changes'] = 'NEW STOCK'
                    else:
                        comparison['old_sentiment'] = existing.sentiment
                        comparison['old_buy'] = existing.buy_trade
                        comparison['old_sell'] = existing.sell_trade
                        
                        changes = []
                        
                        # Check sentiment
                        if existing.sentiment != item.get('sentiment'):
                            changes.append(f"sentiment: {existing.sentiment}→{item.get('sentiment')}")
                            if (existing.sentiment == 'bullish' and item.get('sentiment') == 'bearish') or \
                               (existing.sentiment == 'bearish' and item.get('sentiment') == 'bullish'):
                                comparison['status'] = 'SUSPICIOUS'
                        
                        # Check buy price
                        if existing.buy_trade != item.get('buy_trade'):
                            old = existing.buy_trade or 0
                            new = item.get('buy_trade') or 0
                            if old > 0 and new > 0:
                                pct = abs((new - old) / old * 100)
                                if pct > 20:
                                    comparison['status'] = 'SUSPICIOUS'
                                changes.append(f"buy: ${old:.2f}→${new:.2f} ({pct:.1f}%)")
                            else:
                                changes.append(f"buy: ${old:.2f}→${new:.2f}")
                        
                        # Check sell price
                        if existing.sell_trade != item.get('sell_trade'):
                            old = existing.sell_trade or 0
                            new = item.get('sell_trade') or 0
                            if old > 0 and new > 0:
                                pct = abs((new - old) / old * 100)
                                if pct > 20:
                                    comparison['status'] = 'SUSPICIOUS'
                                changes.append(f"sell: ${old:.2f}→${new:.2f} ({pct:.1f}%)")
                            else:
                                changes.append(f"sell: ${old:.2f}→${new:.2f}")
                        
                        if changes:
                            comparison['changes'] = '; '.join(changes)
                            if comparison['status'] == 'UNKNOWN':
                                comparison['status'] = 'CHANGED'
                        else:
                            comparison['status'] = 'UNCHANGED'
                            comparison['changes'] = ''
                    
                    all_comparisons.append(comparison)
        
        # Show summary
        status_counts = {}
        for comp in all_comparisons:
            status = comp['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("\nSummary:")
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")
        
        # Show suspicious/new items
        suspicious = [c for c in all_comparisons if c['status'] == 'SUSPICIOUS']
        new_stocks = [c for c in all_comparisons if c['status'] == 'NEW']
        
        if suspicious:
            print(f"\n⚠️  SUSPICIOUS CHANGES ({len(suspicious)}):")
            for comp in suspicious[:5]:
                print(f"  {comp['ticker']}: {comp['changes']}")
            if len(suspicious) > 5:
                print(f"  ... and {len(suspicious) - 5} more")
        
        if new_stocks:
            print(f"\n✨ NEW STOCKS ({len(new_stocks)}):")
            for comp in new_stocks[:5]:
                print(f"  {comp['ticker']} ({comp['category']})")
            if len(new_stocks) > 5:
                print(f"  ... and {len(new_stocks) - 5} more")
        
        # Export to CSV
        df = pd.DataFrame(all_comparisons)
        
        # Reorder columns for better readability
        columns = ['ticker', 'category', 'status', 'changes',
                  'old_sentiment', 'new_sentiment',
                  'old_buy', 'new_buy', 
                  'old_sell', 'new_sell']
        df = df[columns]
        
        # Sort by status and ticker
        df = df.sort_values(['status', 'ticker'])
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_file = f'email_validation_{timestamp}.csv'
        
        df.to_csv(csv_file, index=False)
        
        print(f"\n{'='*80}")
        print("VALIDATION COMPLETE")
        print(f"{'='*80}")
        print(f"\nValidation report saved to: {csv_file}")
        print("\nPlease review the CSV file, especially:")
        print("- Stocks marked as NEW")
        print("- Stocks marked as SUSPICIOUS (large price changes or sentiment flips)")
        print("\nThis was a DRY RUN - no database updates were made.")
        print("\nTo update the database after your review:")
        print("  python he_alerts/fetch_latest_emails.py")


if __name__ == "__main__":
    asyncio.run(simple_validation())