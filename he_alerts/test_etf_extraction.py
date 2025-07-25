"""Test ETF email extraction."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.email_processor import EmailProcessor
from app.core.database import AsyncSessionLocal
from app.services.database import StockService


async def test_etf_extraction():
    print('=' * 60)
    print('TESTING ETF EMAIL EXTRACTION')
    print('=' * 60)
    
    async with AsyncSessionLocal() as db:
        processor = EmailProcessor()
        
        # Process ETF emails from last 7 days (they're weekly)
        results = await processor.process_recent_emails(
            db=db,
            email_types=['etf'],
            hours=168  # 7 days
        )
        
        print('\nETF EXTRACTION RESULTS:')
        print('-' * 40)
        
        etf_result = results['by_type'].get('etf', {})
        print(f'Processed: {etf_result.get("processed_count", 0)}')
        print(f'Extracted: {etf_result.get("extracted_count", 0)}')
        print(f'Errors: {etf_result.get("error_count", 0)}')
        
        # Show extracted ETFs
        if etf_result.get('extracted_count', 0) > 0:
            etf_stocks = await StockService.get_stocks_by_category(db, 'etfs', limit=20)
            if etf_stocks:
                print('\nExtracted ETFs:')
                for stock in etf_stocks:
                    sentiment = stock.sentiment or "neutral"
                    buy_price = f"${stock.buy_trade}" if stock.buy_trade else "N/A"
                    sell_price = f"${stock.sell_trade}" if stock.sell_trade else "N/A"
                    print(f'  {stock.ticker:<8} | {sentiment:<8} | Buy: {buy_price:<10} | Sell: {sell_price:<10}')


if __name__ == "__main__":
    asyncio.run(test_etf_extraction())