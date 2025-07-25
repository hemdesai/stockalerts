"""Test price update for a single stock."""
import asyncio
from app.services.ibkr.price_fetcher import PriceFetcher


async def test_single_stock():
    price_fetcher = PriceFetcher()
    
    # Test a few common stocks
    tickers = ["AAPL", "MSFT", "GOOGL"]
    
    for ticker in tickers:
        print(f"\nTesting {ticker}...")
        try:
            price = await price_fetcher.get_single_price(ticker)
            if price:
                print(f"{ticker}: ${price:.2f}")
            else:
                print(f"{ticker}: No price available")
        except Exception as e:
            print(f"{ticker}: Error - {e}")


if __name__ == "__main__":
    asyncio.run(test_single_stock())