"""Test email processing directly."""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import AsyncSessionLocal
from app.services.email_processor import EmailProcessor
from app.services.database import EmailService, StockService


async def test_email_processing():
    """Test the email processing workflow."""
    print("=" * 60)
    print("TESTING EMAIL PROCESSING")
    print("=" * 60)
    
    # Create database session
    async with AsyncSessionLocal() as db:
        # Initialize processor
        processor = EmailProcessor()
        
        # Process emails from last 24 hours
        print(f"\n1. Processing emails from last 24 hours...")
        print(f"   Started at: {datetime.now()}")
        
        try:
            results = await processor.process_recent_emails(
                db=db,
                email_types=["daily", "crypto"],  # Process daily and crypto emails
                hours=24
            )
            
            print(f"\n2. Processing Results:")
            print(f"   - Total processed: {results['total_processed']}")
            print(f"   - Total extracted: {results['total_extracted']}")
            print(f"   - Total errors: {results['total_errors']}")
            print(f"   - Processing time: {results['processing_time']:.2f} seconds")
            
            # Show results by type
            print(f"\n3. Results by Email Type:")
            for email_type, type_result in results['by_type'].items():
                print(f"\n   {email_type.upper()}:")
                print(f"   - Processed: {type_result['processed_count']}")
                print(f"   - Extracted: {type_result['extracted_count']}")
                print(f"   - Errors: {type_result['error_count']}")
            
            # Get processing summary
            print(f"\n4. Database Summary:")
            summary = await processor.get_processing_summary(db)
            
            print(f"   Stock Counts by Category:")
            for category, count in summary.get('stock_counts', {}).items():
                print(f"   - {category}: {count} stocks")
            
            print(f"\n   Email Processing Stats:")
            email_stats = summary.get('email_processing', {})
            print(f"   - Total emails: {email_stats.get('total_emails', 0)}")
            print(f"   - Processed: {email_stats.get('processed_emails', 0)}")
            print(f"   - Successful: {email_stats.get('successful_extractions', 0)}")
            
            # Show some extracted stocks
            print(f"\n5. Sample Extracted Stocks:")
            for category in ["daily", "digitalassets"]:
                stocks = await StockService.get_stocks_by_category(db, category, limit=5)
                if stocks:
                    print(f"\n   {category.upper()} (showing first {len(stocks)}):")
                    for stock in stocks:
                        print(f"   - {stock.ticker}: Buy=${stock.buy_trade}, Sell=${stock.sell_trade}, Sentiment={stock.sentiment}")
            
        except Exception as e:
            print(f"\n   ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_email_processing())