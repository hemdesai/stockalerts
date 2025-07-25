"""Test IDEAS price extraction fix."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.email_processor import EmailProcessor
from app.core.database import AsyncSessionLocal


async def test_ideas_fix():
    print('=' * 60)
    print('TESTING IDEAS PRICE EXTRACTION FIX')
    print('=' * 60)
    
    async with AsyncSessionLocal() as db:
        processor = EmailProcessor()
        
        # Process IDEAS emails
        results = await processor.process_recent_emails(
            db=db,
            email_types=['ideas'],
            hours=168  # 7 days
        )
        
        print(f"\nProcessed {len(results)} IDEAS emails")
        
        # Check the extracted stocks
        from app.services.database.stock_service import StockService
        stock_service = StockService()
        
        ideas_stocks = await stock_service.get_stocks_by_category(db, 'ideas')
        
        print(f"\nTotal IDEAS stocks in database: {len(ideas_stocks)}")
        
        # Check specific stocks that should have correct prices
        expected_prices = {
            'COP': (211.00, 223.00),
            'DKNG': (41.42, 45.65),
            'CELH': (43.03, 46.56),
            'XYL': (128.00, 136.00),
            'COIN': (355.00, 431.00),
            'PLNT': (106.00, 116.00),
            'ULTA': (465.00, 498.00),
            'IVT': (26.40, 27.44),
            'GAP': (19.04, 23.01),
            'AMN': (18.09, 22.01)
        }
        
        print("\nValidation of key stocks:")
        print("-" * 70)
        print(f"{'Ticker':<8} {'Expected Buy':<12} {'Expected Sell':<12} {'Actual Buy':<12} {'Actual Sell':<12} {'Status'}")
        print("-" * 70)
        
        success_count = 0
        for stock in ideas_stocks:
            ticker = stock.ticker
            if ticker in expected_prices:
                exp_buy, exp_sell = expected_prices[ticker]
                actual_buy = stock.buy_trade
                actual_sell = stock.sell_trade
                
                # Check if prices match (within $1 tolerance)
                buy_match = abs(actual_buy - exp_buy) < 1.0 if actual_buy else False
                sell_match = abs(actual_sell - exp_sell) < 1.0 if actual_sell else False
                match = buy_match and sell_match
                
                if match:
                    success_count += 1
                
                status = "✅" if match else "❌"
                print(f"{ticker:<8} ${exp_buy:<11.2f} ${exp_sell:<11.2f} ${actual_buy:<11.2f} ${actual_sell:<11.2f} {status}")
        
        print("-" * 70)
        print(f"Correctly extracted: {success_count}/{len(expected_prices)}")
        
        # Check for generic $200/$250 prices
        generic_count = 0
        for stock in ideas_stocks:
            if stock.buy_trade == 200.0 and stock.sell_trade == 250.0:
                generic_count += 1
                print(f"⚠️  {stock.ticker} still has generic $200/$250 prices")
        
        if generic_count > 0:
            print(f"\n❌ Found {generic_count} stocks with generic prices - fix not fully working")
        else:
            print(f"\n✅ No stocks with generic $200/$250 prices found!")


if __name__ == "__main__":
    asyncio.run(test_ideas_fix())