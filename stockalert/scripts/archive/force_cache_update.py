"""
Force update of price cache for all tickers in the database
Stores prices directly in the stocks.db database
"""
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from stockalert.scripts.price_cache import PriceCache
from stockalert.scripts.db_manager import StockAlertDBManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(project_root) / "data" / "price_cache.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("force_cache_update")

def get_current_session():
    """Determine if current time is AM or PM session"""
    now = datetime.now()
    if now.hour < 12:
        return "AM"
    return "PM"

def force_cache_update():
    """Force update of price cache for all tickers"""
    start_time = time.time()
    session = get_current_session()
    logger.info(f"Starting forced price cache update for {session} session")
    
    # Get all tickers from the database
    db_manager = StockAlertDBManager()
    db_manager.connect()
    db_manager.cursor.execute("SELECT DISTINCT ticker FROM stocks")
    tickers = [row[0] for row in db_manager.cursor.fetchall()]
    db_manager.close()
    
    if not tickers:
        logger.error("No tickers found in database")
        return
    
    logger.info(f"Retrieved {len(tickers)} unique tickers from database")
    
    # Initialize the price cache
    cache = PriceCache()
    
    # Cache prices for all tickers
    logger.info(f"Caching prices for {len(tickers)} tickers")
    prices = cache.cache_ticker_prices(tickers)
    
    # Log results
    elapsed = time.time() - start_time
    success_count = len(prices)
    success_rate = success_count / len(tickers) * 100 if tickers else 0
    
    logger.info(f"Cached {success_count}/{len(tickers)} prices ({success_rate:.1f}%) in {elapsed:.2f} seconds")
    logger.info(f"API calls: {cache.api_calls}")
    
    # Print summary
    print(f"\nPrice Cache Update Summary ({session} Session):")
    print(f"---------------------------")
    print(f"Total tickers: {len(tickers)}")
    print(f"Successfully cached: {success_count} ({success_rate:.1f}%)")
    print(f"Time taken: {elapsed:.2f} seconds")
    print(f"API calls: {cache.api_calls}")
    print(f"Prices stored directly in stocks.db database")

if __name__ == "__main__":
    force_cache_update()