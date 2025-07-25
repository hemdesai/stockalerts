"""Show extraction results from database for all email types."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import AsyncSessionLocal
from app.services.database import StockService, EmailService

async def show_extractions():
    async with AsyncSessionLocal() as db:
        print('=' * 80)
        print('EXTRACTION RESULTS BY EMAIL TYPE')
        print('=' * 80)
        
        # Get all stocks by category
        for category in ['daily', 'ideas', 'etfs', 'digitalassets']:
            stocks = await StockService.get_stocks_by_category(db, category, limit=20)
            if stocks:
                print(f'\n{category.upper()} EMAILS - {len(stocks)} stocks extracted:')
                print('-' * 60)
                for stock in stocks:
                    sentiment = stock.sentiment or "N/A"
                    buy_trade = f"${stock.buy_trade}" if stock.buy_trade else "N/A"
                    sell_trade = f"${stock.sell_trade}" if stock.sell_trade else "N/A"
                    name = (stock.name or "")[:30]
                    print(f'  {stock.ticker:<8} | {sentiment:<8} | Buy: {buy_trade:<10} | Sell: {sell_trade:<10} | {name}')
            else:
                print(f'\n{category.upper()} EMAILS - No stocks extracted yet')
        
        # Show recent email processing logs
        print('\n' + '=' * 80)
        print('RECENT EMAIL PROCESSING LOGS')
        print('=' * 80)
        
        logs = await EmailService.get_recent_email_logs(db, limit=10)
        for log in logs:
            status = '✓' if log.extraction_successful else '✗'
            subject = log.subject[:50] + "..." if len(log.subject) > 50 else log.subject
            print(f'{status} {log.email_type:<8} | {log.extracted_count:>2} items | {subject}')
            if not log.extraction_successful and log.error_message:
                error_msg = log.error_message[:100] + "..." if len(log.error_message) > 100 else log.error_message
                print(f'    Error: {error_msg}')

if __name__ == "__main__":
    asyncio.run(show_extractions())