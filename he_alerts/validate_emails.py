"""
Validation mode for email extraction - shows what would be extracted without updating DB.
"""
import asyncio
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any

from app.services.email.gmail_client import GmailClient
from app.services.email import get_extractor
from app.core.database import AsyncSessionLocal
from app.services.database.stock_service import StockService
from app.core.logging import get_logger

logger = get_logger(__name__)


async def validate_email_extraction():
    """Validate email extraction without database updates."""
    
    print("="*80)
    print("EMAIL EXTRACTION VALIDATION")
    print("="*80)
    print("This will show what would be extracted from the latest emails")
    print("WITHOUT updating the database.")
    print("="*80)
    
    gmail_client = GmailClient()
    
    # Authenticate
    if not await gmail_client.authenticate():
        print("\n[ERROR] Failed to authenticate with Gmail")
        return
    
    print("\n[OK] Authenticated with Gmail")
    
    # Fetch recent emails
    hours = 72
    recent_emails = await gmail_client.fetch_recent_emails(hours=hours)
    print(f"\nFound {len(recent_emails)} emails from the last {hours} hours")
    
    # Group by type
    email_groups = {}
    for email in recent_emails:
        email_type = email.get('email_type', 'unknown')
        if email_type not in email_groups:
            email_groups[email_type] = []
        email_groups[email_type].append(email)
    
    print("\nEmails by type:")
    for email_type, emails in email_groups.items():
        print(f"  {email_type}: {len(emails)} emails")
    
    # Process daily and crypto emails
    all_extracted = []
    
    for email_type in ['daily', 'crypto']:
        if email_type not in email_groups:
            print(f"\n[WARNING] No {email_type} emails found")
            continue
        
        # Get latest email
        latest = email_groups[email_type][0]
        
        print(f"\n{'='*60}")
        print(f"Processing {email_type.upper()} email")
        print(f"Message ID: {latest['message_id']}")
        
        # Clean subject for display
        subject = latest['subject'].encode('ascii', 'replace').decode('ascii')
        print(f"Subject: {subject}")
        
        # Get the extractor
        extractor = get_extractor(email_type)
        if not extractor:
            print(f"[ERROR] No extractor found for {email_type}")
            continue
        
        # Extract from the email
        try:
            email_data = await gmail_client.get_email_by_id(latest['message_id'])
            result = await extractor.extract_from_email(email_data)
            
            if result and result.get('extracted_items'):
                items = result['extracted_items']
                print(f"\nExtracted {len(items)} stocks:")
                
                # Add metadata to each item
                for item in items:
                    item['email_type'] = email_type
                    item['category'] = 'digitalassets' if email_type == 'crypto' else email_type
                    item['source_email_id'] = latest['message_id']
                
                # Show sample
                for i, item in enumerate(items[:5]):
                    print(f"  {item['ticker']:6} | {item.get('sentiment', 'N/A'):8} | "
                          f"Buy: ${item.get('buy_trade', 0):>7.2f} | "
                          f"Sell: ${item.get('sell_trade', 0):>7.2f}")
                
                if len(items) > 5:
                    print(f"  ... and {len(items) - 5} more")
                
                all_extracted.extend(items)
            else:
                print(f"[WARNING] No items extracted from {email_type} email")
                
        except Exception as e:
            print(f"[ERROR] Failed to extract from {email_type}: {e}")
            logger.error(f"Extraction error for {email_type}", exc_info=True)
    
    # Compare with database
    if all_extracted:
        print(f"\n{'='*80}")
        print("DATABASE COMPARISON")
        print("="*80)
        
        comparisons = []
        
        async with AsyncSessionLocal() as db:
            stock_service = StockService()
            
            for item in all_extracted:
                comp = {
                    'ticker': item['ticker'],
                    'category': item['category'],
                    'email_type': item['email_type'],
                    'new_sentiment': item.get('sentiment'),
                    'new_buy': item.get('buy_trade'),
                    'new_sell': item.get('sell_trade')
                }
                
                # Get existing stock
                existing = await stock_service.get_stock_by_ticker_and_category(
                    db, item['ticker'], item['category']
                )
                
                if not existing:
                    comp['status'] = 'NEW'
                    comp['old_sentiment'] = ''
                    comp['old_buy'] = ''
                    comp['old_sell'] = ''
                    comp['notes'] = 'New stock to be added'
                else:
                    comp['old_sentiment'] = existing.sentiment
                    comp['old_buy'] = existing.buy_trade
                    comp['old_sell'] = existing.sell_trade
                    
                    changes = []
                    suspicious = False
                    
                    # Check sentiment
                    if existing.sentiment != item.get('sentiment'):
                        changes.append(f"sentiment: {existing.sentiment}→{item.get('sentiment')}")
                        if (existing.sentiment == 'bullish' and item.get('sentiment') == 'bearish') or \
                           (existing.sentiment == 'bearish' and item.get('sentiment') == 'bullish'):
                            suspicious = True
                    
                    # Check buy price
                    if existing.buy_trade != item.get('buy_trade'):
                        old = existing.buy_trade or 0
                        new = item.get('buy_trade') or 0
                        if old > 0 and new > 0:
                            pct = abs((new - old) / old * 100)
                            if pct > 20:
                                suspicious = True
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
                                suspicious = True
                            changes.append(f"sell: ${old:.2f}→${new:.2f} ({pct:.1f}%)")
                        else:
                            changes.append(f"sell: ${old:.2f}→${new:.2f}")
                    
                    if changes:
                        comp['status'] = 'SUSPICIOUS' if suspicious else 'CHANGED'
                        comp['notes'] = '; '.join(changes)
                    else:
                        comp['status'] = 'UNCHANGED'
                        comp['notes'] = ''
                
                comparisons.append(comp)
        
        # Summary
        status_counts = {}
        for comp in comparisons:
            status = comp['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("\nSummary:")
        for status in ['NEW', 'SUSPICIOUS', 'CHANGED', 'UNCHANGED']:
            if status in status_counts:
                print(f"  {status}: {status_counts[status]}")
        
        # Show details for important items
        suspicious = [c for c in comparisons if c['status'] == 'SUSPICIOUS']
        new_stocks = [c for c in comparisons if c['status'] == 'NEW']
        
        if suspicious:
            print(f"\n⚠️  SUSPICIOUS CHANGES:")
            for comp in suspicious[:10]:
                print(f"  {comp['ticker']}: {comp['notes']}")
            if len(suspicious) > 10:
                print(f"  ... and {len(suspicious) - 10} more")
        
        if new_stocks:
            print(f"\n✨ NEW STOCKS:")
            for comp in new_stocks[:10]:
                print(f"  {comp['ticker']} ({comp['category']})")
            if len(new_stocks) > 10:
                print(f"  ... and {len(new_stocks) - 10} more")
        
        # Export to CSV
        df = pd.DataFrame(comparisons)
        
        # Reorder columns
        columns = ['ticker', 'category', 'email_type', 'status', 'notes',
                  'old_sentiment', 'new_sentiment',
                  'old_buy', 'new_buy',
                  'old_sell', 'new_sell']
        df = df[columns]
        
        # Sort
        df = df.sort_values(['status', 'category', 'ticker'])
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_file = f'email_validation_{timestamp}.csv'
        
        df.to_csv(csv_file, index=False)
        
        print(f"\n{'='*80}")
        print("VALIDATION COMPLETE")
        print("="*80)
        print(f"\nValidation report saved to: {csv_file}")
        print("\nPlease review the CSV file, focusing on:")
        print("- NEW stocks (will be added to database)")
        print("- SUSPICIOUS stocks (large changes or sentiment flips)")
        print("\nThis was a DRY RUN - no database updates were made.")
        print("\nAfter reviewing, to update the database run:")
        print("  python he_alerts/fetch_latest_emails.py")
        
        return csv_file
    else:
        print("\nNo stocks were extracted from emails.")
        return None


if __name__ == "__main__":
    asyncio.run(validate_email_extraction())