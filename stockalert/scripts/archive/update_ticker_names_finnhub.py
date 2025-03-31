import os
import time
import sqlite3
import pandas as pd
import requests
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("update_names.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("NameUpdater")

class TickerNameUpdater:
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.db_path = self.root_dir / 'data' / 'stocks.db'
        self.finnhub_key = os.environ.get('FINNHUB_API_KEY', 'cv9d5thr01qkfpsj57kgcv9d5thr01qkfpsj57l0')
        
        # Rate limiting
        self.last_finnhub_call = 0
        self.finnhub_min_delay = 1.1  # Minimum delay between Finnhub API calls (60 calls/min)
        
        logger.info("TickerNameUpdater initialized")
    
    def enforce_rate_limit(self):
        """Enforce rate limit for Finnhub API"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_finnhub_call
        
        if time_since_last_call < self.finnhub_min_delay:
            sleep_time = self.finnhub_min_delay - time_since_last_call
            logger.debug(f"Rate limiting: waiting {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)
        
        self.last_finnhub_call = time.time()
    
    def get_company_name(self, ticker, category):
        """Get company name from Finnhub API"""
        self.enforce_rate_limit()
        
        try:
            # For crypto assets, use a different approach
            if category == 'digitalassets':
                if '-USD' in ticker:
                    # Extract the coin name from the ticker
                    coin = ticker.replace('-USD', '')
                    # Map common crypto tickers to full names
                    crypto_names = {
                        'BTC': 'Bitcoin',
                        'ETH': 'Ethereum',
                        'SOL': 'Solana',
                        'XRP': 'Ripple',
                        'ADA': 'Cardano',
                        'DOGE': 'Dogecoin',
                        'DOT': 'Polkadot',
                        'AVAX': 'Avalanche',
                        'LINK': 'Chainlink',
                        'MATIC': 'Polygon',
                        'UNI': 'Uniswap',
                        'ATOM': 'Cosmos',
                        'LTC': 'Litecoin'
                    }
                    if coin in crypto_names:
                        return crypto_names[coin]
                    else:
                        return f"{coin} Coin"
                return ticker  # Return the ticker as is if not in standard format
            
            # For indices, use a different approach
            if category == 'daily' and ticker.startswith('^'):
                # Map common indices to full names
                index_names = {
                    '^TNX': 'US 10-Year Treasury Yield',
                    '^VIX': 'CBOE Volatility Index',
                    '^GSPC': 'S&P 500 Index',
                    '^DJI': 'Dow Jones Industrial Average',
                    '^IXIC': 'NASDAQ Composite Index',
                    '^RUT': 'Russell 2000 Index'
                }
                if ticker in index_names:
                    return index_names[ticker]
                else:
                    return ticker.replace('^', '') + ' Index'
            
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
    
    def get_tickers_needing_update(self):
        """Get tickers that need name updates"""
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
            SELECT Ticker, Name, Category
            FROM stocks
            """
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                logger.warning("No data found in database")
                return None
            
            # Find tickers where Name equals Ticker
            name_issues = df[df['Ticker'] == df['Name']]
            
            logger.info(f"Found {len(name_issues)} tickers needing name updates")
            return name_issues
        except Exception as e:
            logger.error(f"Error getting tickers needing update: {e}")
            return None
    
    def update_ticker_names(self, batch_size=10, max_updates=None):
        """Update ticker names in the database"""
        # Get tickers needing update
        df = self.get_tickers_needing_update()
        if df is None or df.empty:
            logger.info("No tickers need name updates")
            return 0
        
        # Limit the number of updates if specified
        if max_updates is not None and max_updates > 0:
            df = df.head(max_updates)
        
        total_updates = len(df)
        successful_updates = 0
        
        logger.info(f"Starting to update {total_updates} ticker names")
        
        # Process in batches to avoid API rate limits
        for i in range(0, total_updates, batch_size):
            batch_df = df.iloc[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(total_updates + batch_size - 1)//batch_size}: {len(batch_df)} tickers")
            
            # Add a delay between batches
            if i > 0:
                time.sleep(5)
            
            # Connect to database for this batch
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for _, row in batch_df.iterrows():
                ticker = row['Ticker']
                category = row['Category']
                
                # Get company name from Finnhub
                name = self.get_company_name(ticker, category)
                
                if name and name != ticker:
                    try:
                        # Update name in database
                        cursor.execute(
                            "UPDATE stocks SET Name = ? WHERE Ticker = ?",
                            (name, ticker)
                        )
                        logger.info(f"Updated {ticker} with name: {name}")
                        successful_updates += 1
                    except Exception as e:
                        logger.error(f"Error updating {ticker} in database: {e}")
                else:
                    logger.warning(f"Skipping {ticker} - could not get valid name")
            
            # Commit changes and close connection
            conn.commit()
            conn.close()
        
        logger.info(f"Completed {successful_updates}/{total_updates} name updates")
        return successful_updates
    
    def run(self, batch_size=10, max_updates=None):
        """Run the ticker name updater"""
        logger.info("Running ticker name updater")
        
        # Update ticker names
        updates = self.update_ticker_names(batch_size, max_updates)
        
        logger.info(f"Ticker name updater completed with {updates} updates")
        return updates

if __name__ == "__main__":
    updater = TickerNameUpdater()
    updater.run(batch_size=5)  # Process in small batches to avoid rate limits
