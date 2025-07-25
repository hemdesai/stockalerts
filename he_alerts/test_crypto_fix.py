"""Test crypto extraction fix."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.email_processor import EmailProcessor
from app.core.database import AsyncSessionLocal


async def test_crypto_fix():
    print('=' * 60)
    print('TESTING CRYPTO EXTRACTION FIX')
    print('=' * 60)
    
    async with AsyncSessionLocal() as db:
        processor = EmailProcessor()
        
        # Process crypto emails
        results = await processor.process_recent_emails(
            db=db,
            email_types=['crypto'],
            hours=168  # 7 days
        )
        
        print(f"\nProcessed {len(results)} crypto emails")
        
        # Check the extracted stocks
        from app.services.database.stock_service import StockService
        stock_service = StockService()
        
        crypto_stocks = await stock_service.get_stocks_by_category(db, 'digitalassets')
        
        print(f"\nTotal crypto stocks in database: {len(crypto_stocks)}")
        
        if crypto_stocks:
            print("\nExtracted Crypto Assets:")
            print("-" * 60)
            print(f"{'Ticker':<8} {'Sentiment':<10} {'Buy Price':<12} {'Sell Price':<12}")
            print("-" * 60)
            
            for stock in sorted(crypto_stocks, key=lambda x: x.ticker):
                print(f"{stock.ticker:<8} {stock.sentiment:<10} ${stock.buy_trade:<11.2f} ${stock.sell_trade:<11.2f}")
            
            # Check for expected crypto assets
            expected_tickers = ['BTC', 'ETH', 'SOL', 'AVAX', 'AAVE']
            found_tickers = {stock.ticker for stock in crypto_stocks}
            
            print(f"\nExpected tickers found: {len(expected_tickers.intersection(found_tickers))}/{len(expected_tickers)}")
            missing = expected_tickers - found_tickers
            if missing:
                print(f"Missing tickers: {missing}")
            
            # Validate price ranges
            print("\nPrice validation:")
            for stock in crypto_stocks:
                if stock.ticker == 'BTC':
                    # BTC should have prices in thousands
                    if stock.buy_trade > 10000 and stock.sell_trade > 10000:
                        print(f"  BTC: OK (Buy=${stock.buy_trade:.0f}, Sell=${stock.sell_trade:.0f})")
                    else:
                        print(f"  BTC: FAIL - prices too low")
                elif stock.ticker == 'ETH':
                    # ETH should have prices in hundreds/thousands
                    if stock.buy_trade > 100 and stock.sell_trade > 100:
                        print(f"  ETH: OK (Buy=${stock.buy_trade:.0f}, Sell=${stock.sell_trade:.0f})")
                    else:
                        print(f"  ETH: FAIL - prices too low")
            
            success = len(crypto_stocks) >= 3
            print(f"\nExtraction {'SUCCESSFUL' if success else 'FAILED'}")
        else:
            print("\nNo crypto stocks extracted - fix not working yet")


if __name__ == "__main__":
    asyncio.run(test_crypto_fix())