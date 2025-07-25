"""Check what data has been extracted and stored in the database."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import AsyncSessionLocal
from app.services.database import StockService, EmailService


async def check_database_contents():
    print('=' * 80)
    print('DATABASE CONTENTS VERIFICATION')
    print('=' * 80)
    
    async with AsyncSessionLocal() as db:
        # Check stocks by category directly
        categories = ['daily', 'digitalassets', 'ideas', 'etfs']
        
        print('\nEXTRACTED STOCKS BY CATEGORY:')
        print('=' * 80)
        
        total_stocks = 0
        for category in categories:
            print(f'\n{category.upper()} STOCKS:')
            print('-' * 60)
            
            stocks = await StockService.get_stocks_by_category(db, category, limit=50)
            
            if stocks:
                print(f"{'Ticker':<8} | {'Sentiment':<10} | {'Buy Price':<12} | {'Sell Price':<12} | {'Created'}")
                print('-' * 70)
                
                for stock in stocks:
                    sentiment = stock.sentiment or "neutral"
                    buy_price = f"${stock.buy_trade:.2f}" if stock.buy_trade else "N/A"
                    sell_price = f"${stock.sell_trade:.2f}" if stock.sell_trade else "N/A"
                    created = stock.created_at.strftime('%m/%d %H:%M') if stock.created_at else "N/A"
                    
                    print(f"{stock.ticker:<8} | {sentiment:<10} | {buy_price:<12} | {sell_price:<12} | {created}")
                
                print(f"\n{category.upper()} Total: {len(stocks)} stocks")
                total_stocks += len(stocks)
            else:
                print("No stocks found for this category")
        
        print(f'\nGRAND TOTAL: {total_stocks} stocks across all categories')
        
        # Simple validation
        print('\nVALIDATION:')
        print('-' * 50)
        
        # Check daily stocks
        daily_stocks = await StockService.get_stocks_by_category(db, 'daily', limit=50)
        has_major_stocks = any(stock.ticker in ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'GOOGL'] for stock in daily_stocks)
        print(f"  • Daily: {len(daily_stocks)} stocks, Major stocks present: {has_major_stocks}")
        
        # Check crypto stocks  
        crypto_stocks = await StockService.get_stocks_by_category(db, 'digitalassets', limit=50)
        has_crypto = any('BTC' in stock.ticker or 'ETH' in stock.ticker for stock in crypto_stocks)
        print(f"  • Crypto: {len(crypto_stocks)} stocks, Crypto assets present: {has_crypto}")
        
        # Check ideas stocks
        ideas_stocks = await StockService.get_stocks_by_category(db, 'ideas', limit=50)
        has_sentiments = any(stock.sentiment in ['bullish', 'bearish'] for stock in ideas_stocks)
        print(f"  • Ideas: {len(ideas_stocks)} stocks, Sentiments present: {has_sentiments}")
        
        # Check ETF stocks
        etf_stocks = await StockService.get_stocks_by_category(db, 'etfs', limit=50)
        has_etfs = any(len(stock.ticker) >= 3 for stock in etf_stocks)
        print(f"  • ETFs: {len(etf_stocks)} stocks, Valid tickers: {has_etfs}")
        
        # Final summary
        print(f'\n{"="*80}')
        working_categories = sum(1 for stocks in [daily_stocks, crypto_stocks, ideas_stocks, etf_stocks] if len(stocks) > 0)
        print(f'SUMMARY: {working_categories}/4 email types have extracted data, {total_stocks} total stocks')
        print(f'{"="*80}')


if __name__ == "__main__":
    asyncio.run(check_database_contents())