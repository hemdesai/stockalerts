"""
Fetch latest emails, extract stocks, and export for validation WITHOUT updating the database.
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


async def validate_and_export():
    """Fetch emails, extract stocks, compare with DB, and export for validation."""
    
    gmail_client = GmailClient()
    email_processor = EmailProcessor()
    
    # Authenticate with Gmail
    if not await gmail_client.authenticate():
        print("Failed to authenticate with Gmail")
        return
    
    print("[OK] Authenticated with Gmail")
    
    # Fetch recent emails
    recent_emails = await gmail_client.fetch_recent_emails(hours=72)
    print(f"Found {len(recent_emails)} emails from the last 72 hours")
    
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
    
    # Process latest email of each type
    all_extracted_stocks = []
    
    async with AsyncSessionLocal() as db:
        for email_type in ['daily', 'crypto']:  # Focus on the two daily emails
            if email_type not in email_groups:
                print(f"\nNo {email_type} emails found")
                continue
            
            # Get latest email
            latest_email = email_groups[email_type][0]
            
            print(f"\n{'='*80}")
            print(f"Processing {email_type.upper()} email")
            print(f"Message ID: {latest_email['message_id']}")
            
            # Clean subject for display
            subject = latest_email['subject'].encode('ascii', 'replace').decode('ascii')
            print(f"Subject: {subject}")
            
            try:
                # Get full email content
                email_data = await gmail_client.get_email_by_id(latest_email['message_id'])
                
                # Process the email
                result = await email_processor.process_specific_email(
                    email_data, 
                    email_type,
                    latest_email['message_id']
                )
                
                if result['success']:
                    stocks = result.get('stocks', [])
                    print(f"\nExtracted {len(stocks)} stocks")
                    
                    # Show sample
                    for i, stock in enumerate(stocks[:5]):
                        print(f"  {stock['ticker']:6} | {stock['sentiment']:8} | "
                              f"Buy: ${stock['buy_trade']:>7.2f} | Sell: ${stock['sell_trade']:>7.2f}")
                    
                    if len(stocks) > 5:
                        print(f"  ... and {len(stocks) - 5} more")
                    
                    all_extracted_stocks.extend(stocks)
                else:
                    print(f"ERROR: {result.get('message', 'Unknown error')}")
                    
            except Exception as e:
                print(f"ERROR processing email: {e}")
                logger.error(f"Error processing {email_type} email: {e}", exc_info=True)
    
    # Export to CSV for validation
    if all_extracted_stocks:
        print(f"\n{'='*80}")
        print("EXPORT FOR VALIDATION")
        print("="*80)
        
        # Create DataFrame
        df = pd.DataFrame(all_extracted_stocks)
        
        # Add validation columns
        df['validated'] = ''  # Empty column for manual validation
        df['notes'] = ''      # Empty column for notes
        
        # Sort by category and ticker
        df = df.sort_values(['category', 'ticker'])
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f'stocks_validation_{timestamp}.csv'
        
        # Export
        df.to_csv(csv_filename, index=False)
        
        print(f"\nExported {len(df)} stocks to: {csv_filename}")
        print("\nColumns in CSV:")
        for col in df.columns:
            print(f"  - {col}")
        
        # Show category summary
        print("\nStocks by category:")
        for category, count in df['category'].value_counts().items():
            print(f"  {category}: {count} stocks")
        
        # Compare with current database
        print(f"\n{'='*80}")
        print("DATABASE COMPARISON")
        print("="*80)
        
        async with AsyncSessionLocal() as db:
            stock_service = StockService()
            
            new_stocks = []
            changed_stocks = []
            suspicious_changes = []
            
            for _, row in df.iterrows():
                existing = await stock_service.get_stock_by_ticker_and_category(
                    db,
                    row['ticker'],
                    row['category']
                )
                
                if not existing:
                    new_stocks.append(row['ticker'])
                else:
                    # Check for changes
                    changes = []
                    
                    if existing.buy_trade != row['buy_trade']:
                        old_buy = existing.buy_trade or 0
                        new_buy = row['buy_trade'] or 0
                        if old_buy > 0:
                            pct_change = abs((new_buy - old_buy) / old_buy * 100)
                            if pct_change > 20:
                                suspicious_changes.append({
                                    'ticker': row['ticker'],
                                    'field': 'buy_trade',
                                    'old': old_buy,
                                    'new': new_buy,
                                    'pct_change': pct_change
                                })
                        changes.append(f"buy: ${old_buy:.2f} → ${new_buy:.2f}")
                    
                    if existing.sell_trade != row['sell_trade']:
                        old_sell = existing.sell_trade or 0
                        new_sell = row['sell_trade'] or 0
                        if old_sell > 0:
                            pct_change = abs((new_sell - old_sell) / old_sell * 100)
                            if pct_change > 20:
                                suspicious_changes.append({
                                    'ticker': row['ticker'],
                                    'field': 'sell_trade',
                                    'old': old_sell,
                                    'new': new_sell,
                                    'pct_change': pct_change
                                })
                        changes.append(f"sell: ${old_sell:.2f} → ${new_sell:.2f}")
                    
                    if existing.sentiment != row['sentiment']:
                        changes.append(f"sentiment: {existing.sentiment} → {row['sentiment']}")
                        if (existing.sentiment == 'bullish' and row['sentiment'] == 'bearish') or \
                           (existing.sentiment == 'bearish' and row['sentiment'] == 'bullish'):
                            suspicious_changes.append({
                                'ticker': row['ticker'],
                                'field': 'sentiment',
                                'old': existing.sentiment,
                                'new': row['sentiment'],
                                'pct_change': 0
                            })
                    
                    if changes:
                        changed_stocks.append((row['ticker'], changes))
        
        print(f"\nSummary:")
        print(f"  Total extracted: {len(df)}")
        print(f"  New stocks: {len(new_stocks)}")
        print(f"  Changed stocks: {len(changed_stocks)}")
        print(f"  Suspicious changes: {len(suspicious_changes)}")
        
        if new_stocks:
            print(f"\nNEW STOCKS ({len(new_stocks)}):")
            for ticker in new_stocks[:10]:
                print(f"  - {ticker}")
            if len(new_stocks) > 10:
                print(f"  ... and {len(new_stocks) - 10} more")
        
        if suspicious_changes:
            print(f"\n⚠️  SUSPICIOUS CHANGES ({len(suspicious_changes)}):")
            for change in suspicious_changes[:10]:
                print(f"  - {change['ticker']} {change['field']}: "
                      f"{change['old']} → {change['new']} "
                      f"({change['pct_change']:.1f}% change)")
            if len(suspicious_changes) > 10:
                print(f"  ... and {len(suspicious_changes) - 10} more")
        
        print(f"\n{'='*80}")
        print("VALIDATION INSTRUCTIONS")
        print("="*80)
        print(f"1. Open the CSV file: {csv_filename}")
        print("2. Review the extracted data, especially:")
        print("   - New stocks (not in database)")
        print("   - Stocks with suspicious changes (>20% price change)")
        print("   - Sentiment flips (bullish ↔ bearish)")
        print("3. Mark the 'validated' column with 'OK' for correct entries")
        print("4. Add notes in the 'notes' column for any issues")
        print("\n5. After validation, to update the database:")
        print("   python fetch_latest_emails.py")
        print("\nNOTE: This script does NOT update the database.")
        print("It only extracts and exports data for your review.")
        
    else:
        print("\nNo stocks extracted from emails.")


if __name__ == "__main__":
    asyncio.run(validate_and_export())