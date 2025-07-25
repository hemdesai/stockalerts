"""Test ideas email extraction."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.email_processor import EmailProcessor
from app.core.database import AsyncSessionLocal
from app.services.database import StockService


async def test_ideas_extraction():
    print('=' * 60)
    print('TESTING IDEAS EMAIL EXTRACTION')
    print('=' * 60)
    
    async with AsyncSessionLocal() as db:
        processor = EmailProcessor()
        
        # Process ideas emails from last 7 days (they're weekly)
        results = await processor.process_recent_emails(
            db=db,
            email_types=['ideas'],
            hours=168  # 7 days
        )
        
        print('\nIDEAS EXTRACTION RESULTS:')
        print('-' * 40)
        
        ideas_result = results['by_type'].get('ideas', {})
        print(f'Processed: {ideas_result.get("processed_count", 0)}')
        print(f'Extracted: {ideas_result.get("extracted_count", 0)}')
        print(f'Errors: {ideas_result.get("error_count", 0)}')
        
        # Show extracted ideas
        if ideas_result.get('extracted_count', 0) > 0:
            ideas_stocks = await StockService.get_stocks_by_category(db, 'ideas', limit=20)
            if ideas_stocks:
                print('\nExtracted Ideas:')
                bullish_count = bearish_count = 0
                for stock in ideas_stocks:
                    sentiment = stock.sentiment or "neutral"
                    if sentiment == "bullish":
                        bullish_count += 1
                    elif sentiment == "bearish":
                        bearish_count += 1
                    buy_price = f"${stock.buy_trade}" if stock.buy_trade else "N/A"
                    sell_price = f"${stock.sell_trade}" if stock.sell_trade else "N/A"
                    print(f'  {stock.ticker:<8} | {sentiment:<8} | Buy: {buy_price:<10} | Sell: {sell_price:<10}')
                
                print(f'\nSummary: {bullish_count} bullish, {bearish_count} bearish ideas')


if __name__ == "__main__":
    asyncio.run(test_ideas_extraction())