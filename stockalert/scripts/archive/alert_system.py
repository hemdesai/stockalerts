import os
import time
import json
import sqlite3
import pandas as pd
import requests
import logging
import yfinance as yf
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from stockalert.scripts.price_cache import PriceCache

# Google API imports for service account
from google.oauth2 import service_account
from googleapiclient.discovery import build
import base64

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("alert_system.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AlertSystem")

class AlertSystem:
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.db_path = self.root_dir / 'data' / 'stocks.db'
        self.cache_file = self.root_dir / 'data' / 'price_cache.json'
        self.price_cache = self._load_cache()
        
        # Initialize enhanced cache
        self.enhanced_cache = PriceCache()
        
        # Service account file path
        self.service_account_file = self.root_dir / 'credentials' / 'service_account.json'
        
        # Default recipient email
        self.recipient_email = os.environ.get('EMAIL_RECIPIENT', 'hemdesai@gmail.com')
        
        # Cache expiry times in seconds
        self.cache_expiry = {
            'ideas': 3600,  # 1 hour for stocks
            'etfs': 3600,  # 1 hour for ETFs
            'digitalassets': 3600,  # 1 hour for crypto
            'daily': 3600  # 1 hour for daily signals
        }
        
        # API keys
        self.alpha_vantage_key = os.environ.get('ALPHA_VANTAGE_API_KEY', '')
        self.finnhub_key = os.environ.get('FINNHUB_API_KEY', 'cv9d5thr01qkfpsj57kgcv9d5thr01qkfpsj57l0')
        self.fmp_api_key = os.environ.get('FMP_API_KEY', 'fljUxZDDcQuA4NGkWTQ4AmKFDOjrJQkl')
        
        # Rate limiting
        self.last_finnhub_call = 0
        self.finnhub_min_delay = 1.1  # Minimum delay between Finnhub API calls (60 calls/min)
        
        self.last_yahoo_call = 0
        self.yahoo_min_delay = 5.0  # Increased minimum delay between Yahoo Finance API calls
        
        self.last_alpha_vantage_call = 0
        self.alpha_vantage_min_delay = 15.0  # Minimum delay between Alpha Vantage API calls (5 calls/min)
        
        logger.info("AlertSystem initialized")
    
    def _load_cache(self):
        """Load price cache from file"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                logger.info(f"Loaded price cache with {len(cache_data)} entries")
                return cache_data
            else:
                logger.info("No cache file found, creating new cache")
                return {}
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return {}
    
    def _save_cache(self):
        """Save price cache to file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.price_cache, f)
            logger.info(f"Saved price cache with {len(self.price_cache)} entries")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
    
    def _get_price_from_finnhub(self, ticker, category, attempt=1):
        """Get price from Finnhub API"""
        # Enforce rate limit
        current_time = time.time()
        time_since_last_call = current_time - self.last_finnhub_call
        
        if time_since_last_call < self.finnhub_min_delay:
            sleep_time = self.finnhub_min_delay - time_since_last_call
            logger.debug(f"Finnhub rate limiting: waiting {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)
        
        self.last_finnhub_call = time.time()
        
        try:
            # Format ticker for special cases
            formatted_ticker = ticker
            if ticker.startswith('^'):
                # For indices, remove the ^ symbol
                formatted_ticker = ticker[1:]
            elif '=' in ticker:
                # For futures, use a different format
                formatted_ticker = ticker.split('=')[0]
            
            # For crypto assets, use a different endpoint
            if category == 'digitalassets':
                if '-USD' in ticker:
                    symbol = ticker.replace('-USD', '')
                    finnhub_ticker = f"BINANCE:{symbol}USDT"
                else:
                    finnhub_ticker = ticker
                
                url = f'https://finnhub.io/api/v1/crypto/candle?symbol={finnhub_ticker}&resolution=D&from={int(time.time())-86400}&to={int(time.time())}&token={self.finnhub_key}'
                response = requests.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    if 's' in data and data['s'] == 'ok' and 'c' in data and len(data['c']) > 0:
                        price = data['c'][-1]
                        logger.info(f"Got price for {ticker} from Finnhub crypto endpoint: ${price:.2f}")
                        return price
                    else:
                        logger.warning(f"Failed to get price for {ticker} from Finnhub crypto endpoint: {data}")
                        return None
                else:
                    logger.warning(f"Finnhub API error for {ticker}: {response.status_code}")
                    return None
            else:
                # Use quote endpoint for stocks, ETFs, and daily signals
                url = f'https://finnhub.io/api/v1/quote?symbol={formatted_ticker}&token={self.finnhub_key}'
                response = requests.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'c' in data and data['c'] > 0:
                        price = data['c']
                        logger.info(f"Got price for {ticker} from Finnhub: ${price:.2f}")
                        return price
                    else:
                        logger.warning(f"Failed to get price for {ticker} from Finnhub: {data}")
                        return None
                else:
                    logger.warning(f"Finnhub API error for {ticker}: {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Error getting price from Finnhub for {ticker} (attempt {attempt}): {e}")
            return None
    
    def _get_price_from_yahoo(self, ticker, attempt=1):
        """Get price from Yahoo Finance API with individual ticker request"""
        # Try enhanced cache first
        price = self.enhanced_cache.get_ticker_price(ticker)
        if price is not None:
            logger.info(f"Got price for {ticker} from enhanced cache: ${price:.2f}")
            return price
            
        # Enforce rate limit
        current_time = time.time()
        time_since_last_call = current_time - self.last_yahoo_call
        
        if time_since_last_call < self.yahoo_min_delay:
            sleep_time = self.yahoo_min_delay - time_since_last_call
            logger.debug(f"Yahoo rate limiting: waiting {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)
        
        self.last_yahoo_call = time.time()
        
        try:
            ticker_obj = yf.Ticker(ticker)
            ticker_info = ticker_obj.info
            
            if 'currentPrice' in ticker_info and ticker_info['currentPrice'] is not None:
                price = ticker_info['currentPrice']
                logger.info(f"Got price for {ticker} from Yahoo Finance: ${price:.2f}")
                return price
            else:
                logger.warning(f"Failed to get price for {ticker} from Yahoo Finance (attempt {attempt})")
                return None
        except Exception as e:
            logger.error(f"Error getting price from Yahoo Finance for {ticker} (attempt {attempt}): {e}")
            return None
            
    def _get_prices_from_yahoo_batch(self, tickers):
        """Get prices for multiple tickers using yf.download() batch request"""
        if not tickers:
            return {}
            
        # Try enhanced cache first
        results = self.enhanced_cache.get_ticker_prices_batch(tickers)
        if results and len(results) == len(tickers):
            logger.info(f"Got all {len(tickers)} prices from enhanced cache")
            return results
        elif results:
            logger.info(f"Got {len(results)}/{len(tickers)} prices from enhanced cache")
            # Continue with remaining tickers
            tickers = [t for t in tickers if t not in results]
            
        # Enforce rate limit
        current_time = time.time()
        time_since_last_call = current_time - self.last_yahoo_call
        
        if time_since_last_call < self.yahoo_min_delay:
            sleep_time = self.yahoo_min_delay - time_since_last_call
            logger.debug(f"Yahoo rate limiting: waiting {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)
        
        self.last_yahoo_call = time.time()
        
        try:
            # Use yf.download() for batch processing - more efficient than individual Ticker calls
            data = yf.download(tickers, period="1d", group_by="ticker", progress=False)
            
            batch_results = {}
            # Handle single ticker case
            if len(tickers) == 1:
                ticker = tickers[0]
                if 'Close' in data and not pd.isna(data['Close'][-1]):
                    batch_results[ticker] = data['Close'][-1]
                    logger.info(f"Got price for {ticker} from Yahoo Finance batch: ${batch_results[ticker]:.2f}")
            # Handle multiple tickers
            else:
                for ticker in tickers:
                    if (ticker in data.columns and 'Close' in data[ticker] and 
                        len(data[ticker]['Close']) > 0 and not pd.isna(data[ticker]['Close'][-1])):
                        batch_results[ticker] = data[ticker]['Close'][-1]
                        logger.info(f"Got price for {ticker} from Yahoo Finance batch: ${batch_results[ticker]:.2f}")
            
            # Combine with cached results
            if results:
                results.update(batch_results)
                return results
            else:
                return batch_results
            
        except Exception as e:
            logger.error(f"Error getting prices from Yahoo Finance batch for {len(tickers)} tickers: {e}")
            return results if results else {}
    
    def _get_price_from_alpha_vantage(self, ticker, attempt=1):
        """Get price from Alpha Vantage API"""
        if not self.alpha_vantage_key:
            logger.warning("Alpha Vantage API key not set")
            return None
        
        # Enforce rate limit
        current_time = time.time()
        time_since_last_call = current_time - self.last_alpha_vantage_call
        
        if time_since_last_call < self.alpha_vantage_min_delay:
            sleep_time = self.alpha_vantage_min_delay - time_since_last_call
            logger.debug(f"Alpha Vantage rate limiting: waiting {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)
        
        self.last_alpha_vantage_call = time.time()
        
        try:
            url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={self.alpha_vantage_key}'
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if 'Global Quote' in data and '05. price' in data['Global Quote']:
                    price = float(data['Global Quote']['05. price'])
                    logger.info(f"Got price for {ticker} from Alpha Vantage: ${price:.2f}")
                    return price
                else:
                    logger.warning(f"Failed to get price for {ticker} from Alpha Vantage (attempt {attempt}): {data}")
                    return None
            else:
                logger.warning(f"Alpha Vantage API error for {ticker}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting price from Alpha Vantage for {ticker} (attempt {attempt}): {e}")
            return None
    
    def get_current_price(self, ticker, category=None):
        """Get current price for a ticker with caching and multiple data sources"""
        # Check enhanced cache first
        price = self.enhanced_cache.get_ticker_price(ticker)
        if price is not None:
            logger.debug(f"Using enhanced cache for {ticker}: ${price:.2f}")
            # Update local cache too
            self.price_cache[ticker] = (time.time(), price)
            self._save_cache()
            return price
            
        # Check local cache
        current_time = time.time()
        
        if ticker in self.price_cache:
            cache_time, price = self.price_cache[ticker]
            cache_age = current_time - cache_time
            
            # Use cached price if it's still fresh
            if category and category in self.cache_expiry and cache_age < self.cache_expiry[category]:
                logger.debug(f"Using cached price for {ticker}: ${price:.2f} (age: {cache_age:.1f}s)")
                return price
        
        # Try Yahoo Finance first with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            price = self._get_price_from_yahoo(ticker, attempt + 1)
            
            if price is not None:
                self.price_cache[ticker] = (current_time, price)
                self._save_cache()
                return price
            
            if attempt < max_retries - 1:
                # Exponential backoff: 2^attempt * base_delay
                retry_delay = 2 ** attempt * 2
                logger.info(f"Retrying Yahoo Finance for {ticker} in {retry_delay} seconds...")
                time.sleep(retry_delay)
        
        # If Yahoo Finance fails, try Finnhub
        for attempt in range(max_retries):
            price = self._get_price_from_finnhub(ticker, category, attempt + 1)
            if price is not None:
                self.price_cache[ticker] = (current_time, price)
                self._save_cache()
                return price
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying Finnhub for {ticker} in {self.finnhub_min_delay} seconds...")
                time.sleep(self.finnhub_min_delay)
        
        # If Finnhub fails, try Alpha Vantage
        if self.alpha_vantage_key:
            for attempt in range(max_retries):
                price = self._get_price_from_alpha_vantage(ticker, attempt + 1)
                if price is not None:
                    self.price_cache[ticker] = (current_time, price)
                    self._save_cache()
                    return price
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying Alpha Vantage for {ticker} in {self.alpha_vantage_min_delay} seconds...")
                    time.sleep(self.alpha_vantage_min_delay)
        
        # If all APIs fail, check if we have an expired cache entry we can use as a last resort
        if ticker in self.price_cache:
            cache_time, price = self.price_cache[ticker]
            logger.warning(f"Using expired cached price for {ticker}: ${price:.2f}")
            return price
        
        # If everything fails, return None
        logger.error(f"Failed to get price for {ticker} from all sources")
        return None
    
    def get_current_prices_batch(self, tickers, category, batch_size=10, batch_delay=10):
        """
        Get current prices for multiple tickers in batches to avoid rate limits
        
        Args:
            tickers (list): List of ticker symbols
            category (str): Asset category
            batch_size (int): Number of tickers to process in each batch
            batch_delay (int): Delay in seconds between batches
            
        Returns:
            dict: Dictionary mapping tickers to their current prices
        """
        logger.info(f"Getting prices for {len(tickers)} tickers in batches of {batch_size}")
        
        # Try enhanced cache first for all tickers
        results = self.enhanced_cache.get_ticker_prices_batch(tickers)
        if results and len(results) == len(tickers):
            logger.info(f"Got all {len(tickers)} prices from enhanced cache")
            return results
        
        # For any missing tickers, continue with original implementation
        if results:
            logger.info(f"Got {len(results)}/{len(tickers)} prices from enhanced cache")
            # Filter out tickers we already have
            remaining_tickers = [t for t in tickers if t not in results]
        else:
            remaining_tickers = tickers
            results = {}
        
        # Check local cache for remaining tickers
        current_time = time.time()
        cached_tickers = []
        uncached_tickers = []
        
        for ticker in remaining_tickers:
            if ticker in self.price_cache:
                cache_time, price = self.price_cache[ticker]
                cache_age = current_time - cache_time
                
                # Use cached price if it's still fresh
                if category in self.cache_expiry and cache_age < self.cache_expiry[category]:
                    logger.debug(f"Using cached price for {ticker}: ${price:.2f} (age: {cache_age:.1f}s)")
                    results[ticker] = price
                    cached_tickers.append(ticker)
                else:
                    uncached_tickers.append(ticker)
            else:
                uncached_tickers.append(ticker)
                
        logger.info(f"Using cached prices for {len(cached_tickers)} tickers, fetching {len(uncached_tickers)} tickers")
        
        # Process remaining tickers in batches
        for i in range(0, len(uncached_tickers), batch_size):
            batch = uncached_tickers[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(uncached_tickers) + batch_size - 1)//batch_size}: {batch}")
            
            # Try to get prices in batch first using yf.download()
            batch_results = self._get_prices_from_yahoo_batch(batch)
            
            # For any tickers that failed in batch, try individual requests
            failed_tickers = [t for t in batch if t not in batch_results]
            if failed_tickers:
                logger.info(f"{len(failed_tickers)} tickers failed in batch, trying individual requests")
                for ticker in failed_tickers:
                    price = self.get_current_price(ticker, category)
                    if price is not None:
                        batch_results[ticker] = price
            
            # Update results and cache
            for ticker, price in batch_results.items():
                results[ticker] = price
                self.price_cache[ticker] = (current_time, price)
            
            # Save cache after each batch
            self._save_cache()
            
            # Add delay between batches (but not after the last batch)
            if i + batch_size < len(uncached_tickers):
                logger.debug(f"Sleeping for {batch_delay} seconds between batches")
                time.sleep(batch_delay)
        
        return results

    def get_company_name(self, ticker):
        """Get company name from Finnhub API"""
        # Enforce rate limit
        current_time = time.time()
        time_since_last_call = current_time - self.last_finnhub_call
        
        if time_since_last_call < self.finnhub_min_delay:
            sleep_time = self.finnhub_min_delay - time_since_last_call
            logger.debug(f"Finnhub rate limiting: waiting {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)
        
        self.last_finnhub_call = time.time()
        
        try:
            # Try company profile endpoint first
            url = f'https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={self.finnhub_key}'
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if 'name' in data and data['name']:
                    name = data['name']
                    logger.info(f"Got name for {ticker} from Finnhub profile: {name}")
                    return name
            
            # If profile fails, try symbol lookup
            url = f'https://finnhub.io/api/v1/search?q={ticker}&token={self.finnhub_key}'
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and len(data['result']) > 0:
                    # Find exact match
                    exact_matches = [r for r in data['result'] if r['symbol'] == ticker]
                    if exact_matches:
                        name = exact_matches[0]['description']
                        logger.info(f"Got name for {ticker} from Finnhub lookup: {name}")
                        return name
                    else:
                        # Return first result
                        name = data['result'][0]['description']
                        logger.info(f"Got name for {ticker} from Finnhub lookup (first result): {name}")
                        return name
            
            logger.warning(f"Failed to get name for {ticker} from Finnhub")
            return None
        except Exception as e:
            logger.error(f"Error getting name from Finnhub for {ticker}: {e}")
            return None
    
    def generate_alerts(self, df=None):
        """Generate alerts based on current prices and thresholds"""
        try:
            # Connect to database if df not provided
            if df is None:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Get all stocks including sentiment
                cursor.execute("SELECT Ticker, Name, Category, \"Buy Trade\" as Buy_Trade, \"Sell Trade\" as Sell_Trade, Sentiment FROM stocks")
                columns = [description[0] for description in cursor.description]
                stocks = cursor.fetchall()
                
                # Convert to DataFrame
                df = pd.DataFrame(stocks, columns=columns)
                conn.close()
            
            if df.empty:
                logger.warning("No stocks data available")
                return []
            
            # Group tickers by category for batch processing
            category_tickers = {}
            for _, row in df.iterrows():
                category = row.get('Category', 'unknown')
                ticker = row.get('Ticker')
                if ticker and pd.notna(ticker):
                    if category not in category_tickers:
                        category_tickers[category] = []
                    category_tickers[category].append(ticker)
            
            # Get prices in batches by category
            price_data = {}
            for category, tickers in category_tickers.items():
                category_prices = self.get_current_prices_batch(tickers, category)
                price_data.update(category_prices)
            
            alerts = []
            for _, row in df.iterrows():
                ticker = row.get('Ticker')
                name = row.get('Name', ticker)
                category = row.get('Category', 'unknown')
                buy_trade = row.get('Buy_Trade')
                sell_trade = row.get('Sell_Trade')
                sentiment = row.get('Sentiment', '').upper()  # Get sentiment from database
                
                # Skip if required fields are missing or sentiment is NEUTRAL
                if not ticker or pd.isna(buy_trade) or pd.isna(sell_trade) or sentiment == "NEUTRAL":
                    continue
                
                # Get current price from our batch results
                current_price = price_data.get(ticker)
                if current_price is None:
                    logger.warning(f"Skipping alert for {ticker} - could not get current price")
                    continue
                
                # Determine alert type based on price position and sentiment
                alert_type = None
                threshold = None
                
                # For BULLISH assets:
                # - BUY when price is below buy trade
                # - SELL when price is above sell trade
                # For BEARISH assets:
                # - SHORT when price is above sell trade
                # - COVER when price is below buy trade
                
                if sentiment == "BULLISH":
                    if current_price <= buy_trade:
                        alert_type = "BUY"
                        threshold = buy_trade
                    elif current_price >= sell_trade:
                        alert_type = "SELL"
                        threshold = sell_trade
                elif sentiment == "BEARISH":
                    if current_price <= buy_trade:
                        alert_type = "COVER"
                        threshold = buy_trade
                    elif current_price >= sell_trade:
                        alert_type = "SHORT"
                        threshold = sell_trade
                
                # Only create an alert if we have a valid alert type
                if alert_type:
                    alerts.append({
                        'ticker': ticker,
                        'name': name,
                        'current_price': current_price,
                        'threshold': threshold,
                        'type': alert_type,
                        'buy_trade': buy_trade,
                        'sell_trade': sell_trade,
                        'sentiment': sentiment,
                        'category': category
                    })
            
            return alerts
        except Exception as e:
            logger.error(f"Error generating alerts: {e}")
            return []
            
    def get_latest_signals(self):
        """Get the latest signals from the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Query all stocks
            df = pd.read_sql_query("SELECT Ticker, Name, Category, \"Buy Trade\" as Buy_Trade, \"Sell Trade\" as Sell_Trade FROM stocks", conn)
            
            conn.close()
            return df
        except Exception as e:
            logger.error(f"Error getting latest signals: {e}")
            return None
    
    def send_email_alerts(self, alerts, recipient_email=None):
        """Send email alerts using Google API service account"""
        if not alerts:
            logger.info("No alerts to send")
            return False
        
        recipient = recipient_email or self.recipient_email
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        subject = f"Stock Alerts: {len(alerts)} opportunities found"
        
        # Group alerts by category
        alerts_by_category = {}
        for alert in alerts:
            category = alert.get('category', 'unknown')
            if category not in alerts_by_category:
                alerts_by_category[category] = []
            alerts_by_category[category].append(alert)
        
        # Create email body with HTML formatting
        body = f"<h2>Stock Alerts ({timestamp})</h2>"
        
        # Counter for numbering the alerts
        counter = 1
        
        # Process each category
        for category, category_alerts in alerts_by_category.items():
            # Ensure category name is properly formatted
            category_display = category.lower()
            if category_display == "digitalassets":
                category_display = "Digital Assets"
            elif category_display == "etfs":
                category_display = "ETFs"
            elif category_display == "ideas":
                category_display = "Ideas"
            elif category_display == "daily":
                category_display = "Daily Signals"
            
            body += f"<h3>{category_display}</h3>"
            
            for alert in category_alerts:
                ticker = alert['ticker']
                name = alert['name']
                current_price = alert['current_price']
                threshold = alert['threshold']
                alert_type = alert['type']
                
                # Use the sentiment directly from the database (stored in the alert)
                sentiment = alert.get('sentiment', '').lower()
                
                # Determine trade ranges
                buy_trade = alert.get('buy_trade', threshold * 0.95)
                sell_trade = alert.get('sell_trade', threshold * 1.05)
                
                # Ensure buy is lower than sell for display
                if buy_trade > sell_trade:
                    buy_trade, sell_trade = sell_trade, buy_trade
                
                # Calculate potential gain/profit
                profit_pct = 0
                if alert_type == "BUY":
                    # For BUY alerts, calculate potential gain to sell price
                    profit_pct = ((sell_trade - current_price) / current_price) * 100
                elif alert_type == "SELL":
                    # For SELL alerts, calculate potential profit from current price to buy price
                    profit_pct = ((current_price - buy_trade) / buy_trade) * 100
                elif alert_type == "COVER":
                    # For COVER alerts, calculate potential profit from short entry to current price
                    profit_pct = ((sell_trade - current_price) / current_price) * 100
                elif alert_type == "SHORT":
                    # For SHORT alerts, calculate potential profit from current price to buy price
                    profit_pct = ((current_price - buy_trade) / current_price) * 100
                
                # Format the action based on alert type
                action = alert_type
                if action == "BUY" or action == "SHORT":
                    action = action.title()
                elif action == "SELL":
                    action = "Sell"
                elif action == "COVER":
                    action = "Cover"
                
                # Check if ticker is an index, interest rate, currency or other special asset type
                is_index_or_rate = (ticker.startswith('^') or 
                                   '=' in ticker or 
                                   ticker in ['TYX', '2YY', '5YY', '10Y', '30Y', 'DXY', 'EUR', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'NZD'] or
                                   ticker.endswith('USD') or ticker.endswith('EUR') or ticker.endswith('GBP') or ticker.endswith('JPY') or
                                   ticker.endswith('CHF') or ticker.endswith('CAD') or ticker.endswith('AUD') or ticker.endswith('NZD') or
                                   category.lower() == 'digitalassets')
                
                # Format the price display based on the ticker type
                if is_index_or_rate:
                    price_format = f"{current_price:.2f}"
                    buy_price_format = f"{buy_trade:.2f}"
                    sell_price_format = f"{sell_trade:.2f}"
                else:
                    price_format = f"${current_price:.2f}"
                    buy_price_format = f"${buy_trade:.2f}"
                    sell_price_format = f"${sell_trade:.2f}"
                
                # Format the line in the style shown in the example
                body += f"{counter}. {ticker} ({name}) at {price_format} -> {action} "
                body += f"({buy_price_format}-{sell_price_format} {sentiment}) "
                body += f"for {'+' if profit_pct > 0 else ''}{profit_pct:.1f}% {'gain' if profit_pct > 0 else 'profit'}<br><br>\n"
                
                counter += 1
            
            body += "<br>"
        
        body += "<p>This email was sent automatically by the StockAlert system.</p>"
        
        # Check if service account file exists
        if not os.path.exists(self.service_account_file):
            logger.error(f"Service account file not found: {self.service_account_file}")
            logger.error("Email sending failed. To enable email alerts, please create a Google service account and save the credentials to this path.")
            
            # Save email content to a file as fallback
            fallback_file = self.root_dir / 'data' / f'email_alerts_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
            with open(fallback_file, 'w') as f:
                f.write(f"Subject: {subject}\n")
                f.write(f"To: {recipient}\n\n")
                f.write(body)
            logger.info(f"Email content saved to {fallback_file}")
            return False
        
        # Proceed with sending via Gmail API
        try:
            # Load service account credentials
            logger.debug(f"Loading service account from {self.service_account_file}")
            
            # Check if file exists and log its content type
            if os.path.exists(self.service_account_file):
                with open(self.service_account_file, 'r') as f:
                    try:
                        import json
                        service_account_data = json.load(f)
                        logger.debug(f"Service account file loaded successfully. Contains keys: {', '.join(service_account_data.keys())}")
                    except json.JSONDecodeError:
                        logger.error(f"Service account file is not valid JSON")
                        with open(self.service_account_file, 'r') as f2:
                            logger.error(f"First 100 chars of file: {f2.read(100)}")
            
            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_file,
                scopes=['https://www.googleapis.com/auth/gmail.send']
            )
            
            # Create email
            msg = MIMEMultipart()
            msg['From'] = 'stockalertsystem@gmail.com'
            msg['To'] = recipient
            msg['Subject'] = subject
            
            logger.debug(f"Creating email to {msg['To']} with {len(alerts)} alerts")
            msg.attach(MIMEText(body, 'html'))
            
            # Send email using Google API
            logger.debug("Building Gmail service")
            service = build('gmail', 'v1', credentials=credentials)
            raw_message = base64.urlsafe_b64encode(msg.as_bytes())
            raw_message = raw_message.decode()
            message_body = {'raw': raw_message}
            
            logger.debug("Sending email via Gmail API")
            service.users().messages().send(userId='me', body=message_body).execute()
            logger.info(f"Successfully sent email with {len(alerts)} alerts to {recipient}")
            return True
        except Exception as api_error:
            logger.error(f"Gmail API error: {api_error}")
            if hasattr(api_error, 'content'):
                logger.error(f"API error content: {api_error.content}")
            
            # Save email content to a file as fallback
            fallback_file = self.root_dir / 'data' / f'email_alerts_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
            with open(fallback_file, 'w') as f:
                f.write(f"Subject: {subject}\n")
                f.write(f"To: {recipient}\n\n")
                f.write(body)
            logger.info(f"Email content saved to {fallback_file}")
            return False
                
    def run(self, recipient_email=None):
        """Run the alert system"""
        try:
            # Generate alerts
            alerts = self.generate_alerts()
            
            if alerts:
                logger.info(f"Generated {len(alerts)} alerts")
                
                # Send email alerts
                self.send_email_alerts(alerts, recipient_email)
                return alerts
            else:
                logger.info("No alerts generated")
                return []
        except Exception as e:
            logger.error(f"Error running alert system: {e}")
            return []

if __name__ == "__main__":
    alert_system = AlertSystem()
    alerts = alert_system.run()
    
    # Print alerts
    for alert in alerts:
        print(f"{alert['type']} Alert: {alert['ticker']} ({alert['name']}) - Current: ${alert['current_price']:.2f}, Threshold: ${alert['threshold']:.2f}")
