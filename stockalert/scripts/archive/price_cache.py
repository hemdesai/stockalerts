"""
Enhanced price caching module for stock alert system
Uses direct database storage for efficient caching of ticker prices
"""
import time
import logging
import pandas as pd
import yfinance as yf
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# For API rate limiting
from requests import Session
from pyrate_limiter import Duration, RequestRate, Limiter

# Import database manager
from stockalert.scripts.db_manager import StockAlertDBManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("price_cache.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PriceCache")

class PriceCache:
    def __init__(self):
        """
        Initialize price cache with direct database storage
        """
        self.root_dir = Path(__file__).parent.parent
        self.db_manager = StockAlertDBManager()
        self.ticker_names = {}
        self.api_calls = 0
        self.batch_size = 10  # Reduced batch size
        self.batch_delay = 10  # Increased delay between batches (seconds)
        
        # Get ticker names from database
        self.get_ticker_names_from_db()
        
        # Configure YFinance session with custom user agent
        self.session = Session()
        self.session.headers['User-Agent'] = 'StockAlert/1.0'
        
        # Configure rate limiter (2 requests per 10 seconds)
        rate = RequestRate(2, Duration.SECOND * 10)
        self.limiter = Limiter(rate)
        
        logger.info(f"Initialized price cache")
    
    def get_ticker_names_from_db(self):
        """
        Get ticker symbols and their names from the stocks.db database
        
        Returns:
            dict: Dictionary of ticker names {ticker: name}
        """
        ticker_names = {}
        
        try:
            # Connect to the database
            conn = sqlite3.connect(self.db_manager.db_path)
            cursor = conn.cursor()
            
            # Query for all tickers and their names
            cursor.execute("SELECT ticker, name FROM stocks")
            results = cursor.fetchall()
            
            # Create a dictionary of ticker names
            for ticker, name in results:
                ticker_names[ticker] = name
            
            logger.info(f"Retrieved {len(ticker_names)} ticker names from database")
        except Exception as e:
            logger.error(f"Error retrieving ticker names from database: {e}")
        finally:
            if conn:
                conn.close()
        
        self.ticker_names = ticker_names
        
    def cache_ticker_prices(self, tickers, period="1d", interval="1m"):
        """
        Pre-cache ticker prices for a list of tickers
        
        Args:
            tickers: List of ticker symbols
            period: Time period to download (default: 1d)
            interval: Data interval (default: 1m)
        
        Returns:
            dict: Dictionary of cached prices {ticker: price}
        """
        if not tickers:
            return {}
            
        logger.info(f"Caching prices for {len(tickers)} tickers")
        
        # Split tickers into batches of 10 to avoid overloading
        all_tickers = list(tickers)
        results = {}
        
        for i in range(0, len(all_tickers), self.batch_size):
            batch = all_tickers[i:i+self.batch_size]
            batch_str = ", ".join(batch[:5]) + (f"... and {len(batch)-5} more" if len(batch) > 5 else "")
            logger.info(f"Processing batch {i//self.batch_size + 1}/{(len(all_tickers) + self.batch_size - 1)//self.batch_size}: {batch_str}")
            
            try:
                # Use our cached session
                data = yf.download(
                    batch,
                    period=period,
                    interval=interval,
                    group_by='ticker',
                    auto_adjust=True,
                    prepost=False,
                    threads=True,
                    proxy=None,
                    session=self.session,
                    timeout=10
                )
                
                self.api_calls += 1
                
                # Extract latest prices
                if len(batch) == 1:
                    ticker = batch[0]
                    if 'Close' in data and len(data) > 0:
                        results[ticker] = data['Close'].iloc[-1]
                        name = self.ticker_names.get(ticker, ticker)
                        logger.info(f"Cached price for {name} ({ticker}): ${results[ticker]:.2f}")
                else:
                    for ticker in batch:
                        if (ticker in data.columns and 'Close' in data[ticker] and 
                            len(data[ticker]['Close']) > 0 and not pd.isna(data[ticker]['Close'][-1])):
                            results[ticker] = data[ticker]['Close'][-1]
                            name = self.ticker_names.get(ticker, ticker)
                            logger.info(f"Cached price for {name} ({ticker}): ${results[ticker]:.2f}")
                
                # Add a small delay between batches
                if i + self.batch_size < len(all_tickers):
                    time.sleep(self.batch_delay)
                    
            except Exception as e:
                logger.error(f"Error caching batch {i//self.batch_size + 1}: {e}")
                # Try individual tickers in case batch failed
                for ticker in batch:
                    try:
                        price = self.get_ticker_price(ticker)
                        if price is not None:
                            results[ticker] = price
                    except Exception as ticker_e:
                        logger.error(f"Error caching individual ticker {ticker}: {ticker_e}")
        
        success_rate = len(results) / len(tickers) * 100 if tickers else 0
        logger.info(f"Successfully cached prices for {len(results)}/{len(tickers)} tickers ({success_rate:.1f}%)")
        return results
    
    def get_ticker_price(self, ticker):
        """
        Get the latest price for a ticker using cached data when available
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            float: Latest price or None if not available
        """
        try:
            # Check if cache contains this ticker
            price = self.db_manager.get_ticker_price(ticker)
            
            if price is not None:
                logger.debug(f"Got price for {ticker}: ${price:.2f} (cached)")
                return price
            
            # This will use fresh data
            ticker_obj = yf.Ticker(ticker, session=self.session)
            hist = ticker_obj.history(period="1d", timeout=10)
            
            if not hist.empty:
                price = hist['Close'].iloc[-1]
                logger.debug(f"Got price for {ticker}: ${price:.2f} (fresh)")
                self.db_manager.cache_ticker_price(ticker, price)
                return price
        except Exception as e:
            logger.error(f"Error getting price for {ticker}: {e}")
        
        return None
    
    def get_ticker_prices_batch(self, tickers):
        """
        Get latest prices for multiple tickers using cached data when available
        
        Args:
            tickers: List of ticker symbols
            
        Returns:
            dict: Dictionary of prices {ticker: price}
        """
        if not tickers:
            return {}
            
        try:
            # Get ticker names from database
            ticker_names = self.ticker_names
            
            # Check cache status before making request
            cache_status = [self.db_manager.get_ticker_price(t) is not None for t in tickers]
            cached_count = sum(cache_status)
            
            if cached_count == len(tickers):
                logger.info(f"All {len(tickers)} tickers found in cache")
            else:
                logger.info(f"Found {cached_count}/{len(tickers)} tickers in cache")
                
            # Use our cached session
            data = yf.download(
                tickers,
                period="1d",
                interval="1m",
                group_by='ticker',
                auto_adjust=True,
                prepost=False,
                threads=True,
                proxy=None,
                session=self.session,
                timeout=10
            )
            
            self.api_calls += 1
            
            # Extract latest prices
            results = {}
            
            if len(tickers) == 1:
                ticker = tickers[0]
                if 'Close' in data and len(data) > 0:
                    results[ticker] = data['Close'].iloc[-1]
                    name = ticker_names.get(ticker, ticker)
                    logger.info(f"Retrieved price for {name} ({ticker}): ${results[ticker]:.2f}")
            else:
                for ticker in tickers:
                    if (ticker in data.columns and 'Close' in data[ticker] and 
                        len(data[ticker]['Close']) > 0 and not pd.isna(data[ticker]['Close'][-1])):
                        results[ticker] = data[ticker]['Close'][-1]
                        name = ticker_names.get(ticker, ticker)
                        logger.info(f"Retrieved price for {name} ({ticker}): ${results[ticker]:.2f}")
            
            # Cache prices
            for ticker, price in results.items():
                self.db_manager.cache_ticker_price(ticker, price)
            
            return results
        except Exception as e:
            logger.error(f"Error retrieving batch prices: {e}")
            # Try individual tickers as fallback
            results = {}
            for ticker in tickers:
                try:
                    price = self.get_ticker_price(ticker)
                    if price is not None:
                        results[ticker] = price
                except Exception as ticker_e:
                    logger.error(f"Error retrieving individual ticker {ticker}: {ticker_e}")
            return results
