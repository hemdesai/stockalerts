"""Test crypto extraction with derivative exposures fix."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.email_processor import EmailProcessor
from app.core.database import AsyncSessionLocal


async def test_crypto_derivative_fix():
    print('=' * 60)
    print('TESTING CRYPTO + DERIVATIVE EXPOSURES EXTRACTION')
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
        
        print(f"\nTotal crypto/derivative stocks in database: {len(crypto_stocks)}")
        
        if crypto_stocks:
            # Separate pure crypto from derivative exposures
            pure_crypto = ['BTC', 'ETH', 'SOL', 'AVAX', 'AAVE', 'XRP', 'ADA', 'MATIC', 'DOT', 'LINK']
            derivative_stocks = ['IBIT', 'MSTR', 'MARA', 'RIOT', 'COIN', 'ETHA', 'BLOK', 'BITO']
            
            pure_crypto_found = [s for s in crypto_stocks if s.ticker in pure_crypto]
            derivative_found = [s for s in crypto_stocks if s.ticker in derivative_stocks]
            other_found = [s for s in crypto_stocks if s.ticker not in pure_crypto + derivative_stocks]
            
            print(f"\nPure Crypto Assets: {len(pure_crypto_found)}")
            if pure_crypto_found:
                print("-" * 60)
                print(f"{'Ticker':<8} {'Sentiment':<10} {'Buy Price':<12} {'Sell Price':<12}")
                print("-" * 60)
                for stock in sorted(pure_crypto_found, key=lambda x: x.ticker):
                    print(f"{stock.ticker:<8} {stock.sentiment:<10} ${stock.buy_trade:<11.2f} ${stock.sell_trade:<11.2f}")
            
            print(f"\nDerivative Exposures (Crypto Stocks): {len(derivative_found)}")
            if derivative_found:
                print("-" * 60)
                print(f"{'Ticker':<8} {'Sentiment':<10} {'Buy Price':<12} {'Sell Price':<12}")
                print("-" * 60)
                for stock in sorted(derivative_found, key=lambda x: x.ticker):
                    print(f"{stock.ticker:<8} {stock.sentiment:<10} ${stock.buy_trade:<11.2f} ${stock.sell_trade:<11.2f}")
            
            if other_found:
                print(f"\nOther Crypto-Related Assets: {len(other_found)}")
                print("-" * 60)
                for stock in sorted(other_found, key=lambda x: x.ticker):
                    print(f"{stock.ticker:<8} {stock.sentiment:<10} ${stock.buy_trade:<11.2f} ${stock.sell_trade:<11.2f}")
            
            # Check for expected tickers
            expected_crypto = ['BTC', 'ETH', 'SOL']
            expected_derivatives = ['IBIT', 'MSTR', 'MARA']
            
            found_tickers = {stock.ticker for stock in crypto_stocks}
            
            missing_crypto = set(expected_crypto) - found_tickers
            missing_derivatives = set(expected_derivatives) - found_tickers
            
            print(f"\nValidation:")
            print(f"Expected crypto found: {len(set(expected_crypto) & found_tickers)}/{len(expected_crypto)}")
            if missing_crypto:
                print(f"  Missing crypto: {missing_crypto}")
            
            print(f"Expected derivatives found: {len(set(expected_derivatives) & found_tickers)}/{len(expected_derivatives)}")
            if missing_derivatives:
                print(f"  Missing derivatives: {missing_derivatives}")
            
            total_expected = len(expected_crypto) + len(expected_derivatives)
            total_found = len(set(expected_crypto + expected_derivatives) & found_tickers)
            success = total_found >= total_expected * 0.8  # 80% success threshold
            
            print(f"\nExtraction {'SUCCESSFUL' if success else 'NEEDS IMPROVEMENT'}")
            print(f"Found {total_found}/{total_expected} expected assets")
        else:
            print("\nNo crypto stocks extracted - fix not working yet")


if __name__ == "__main__":
    asyncio.run(test_crypto_derivative_fix())