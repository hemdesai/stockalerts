"""
Test script for price cache functionality
"""
import sys
import time
import logging
from pathlib import Path

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the PriceCache class
from stockalert.scripts.price_cache import PriceCache

def test_price_cache():
    """Test the price cache functionality"""
    # Initialize the price cache
    cache = PriceCache()
    
    # Define some test tickers
    test_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
    
    print(f"Testing price cache with {len(test_tickers)} tickers: {', '.join(test_tickers)}")
    
    # First run - should fetch from API and cache
    print("\n--- First Run (API Calls) ---")
    start_time = time.time()
    prices = cache.cache_ticker_prices(test_tickers)
    elapsed = time.time() - start_time
    
    print(f"First run completed in {elapsed:.2f} seconds")
    print(f"Retrieved {len(prices)} prices:")
    for ticker, price in prices.items():
        print(f"  {ticker}: ${price:.2f}")
    
    # Second run - should use cached data
    print("\n--- Second Run (Cached) ---")
    start_time = time.time()
    cached_prices = cache.get_ticker_prices_batch(test_tickers)
    elapsed = time.time() - start_time
    
    print(f"Second run completed in {elapsed:.2f} seconds")
    print(f"Retrieved {len(cached_prices)} prices from cache:")
    for ticker, price in cached_prices.items():
        print(f"  {ticker}: ${price:.2f}")
    
    # Compare performance
    if len(prices) > 0 and len(cached_prices) > 0:
        print("\n--- Cache Performance ---")
        print(f"Cache efficiency metrics:")
        print(f"  API calls: {cache.api_calls}")
        print(f"  Cache hits: {cache.cache_hits}")
        print(f"  Cache misses: {cache.cache_misses}")
        
        # Verify prices match
        mismatches = 0
        for ticker in test_tickers:
            if ticker in prices and ticker in cached_prices:
                if abs(prices[ticker] - cached_prices[ticker]) > 0.01:
                    print(f"  Price mismatch for {ticker}: ${prices[ticker]:.2f} vs ${cached_prices[ticker]:.2f}")
                    mismatches += 1
        
        if mismatches == 0:
            print("  All cached prices match original prices ")

if __name__ == "__main__":
    test_price_cache()