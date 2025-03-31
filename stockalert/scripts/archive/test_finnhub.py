import os
import pandas as pd
import sqlite3
import requests
import time
from pathlib import Path
import json
import random

# Finnhub API key
API_KEY = "cv9d5thr01qkfpsj57kgcv9d5thr01qkfpsj57l0"

# Categories to test
CATEGORIES = ['ideas', 'etfs', 'digitalassets', 'daily']

class FinnhubTest:
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.db_path = self.root_dir / 'data' / 'stocks.db'
        self.api_key = API_KEY
        self.last_call_time = 0
        self.min_delay = 1.1  # Minimum delay between API calls in seconds (to stay under 60 calls/min)
        
    def get_tickers_by_category(self, sample_size=3):
        """Get sample tickers from each category"""
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
            SELECT Ticker, Name, Category
            FROM stocks
            """
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                print("No data found in database")
                return None
                
            # Group by category
            tickers_by_category = {}
            for category in CATEGORIES:
                category_df = df[df['Category'] == category]
                if not category_df.empty:
                    # Take a random sample
                    sample = category_df.sample(min(sample_size, len(category_df)))
                    tickers_by_category[category] = sample.to_dict('records')
                    
            return tickers_by_category
        except Exception as e:
            print(f"Error getting tickers: {e}")
            return None
    
    def check_name_issues(self):
        """Check for records where Name equals Ticker"""
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
            SELECT Ticker, Name, Category
            FROM stocks
            """
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                print("No data found in database")
                return
                
            # Count records where Name equals Ticker
            name_issues = df[df['Ticker'] == df['Name']]
            issue_count = len(name_issues)
            total_count = len(df)
            
            print("\n=== NAME ISSUES ===")
            print(f"Total records: {total_count}")
            print(f"Records where Name equals Ticker: {issue_count} ({issue_count/total_count*100:.1f}%)\n")
            
            # Group by category
            for category in CATEGORIES:
                category_df = df[df['Category'] == category]
                category_issues = name_issues[name_issues['Category'] == category]
                
                if not category_df.empty:
                    issue_pct = len(category_issues) / len(category_df) * 100
                    print(f"Category: {category}")
                    print(f"  Issues: {len(category_issues)}/{len(category_df)} records ({issue_pct:.1f}%)")
                    
                    # Show examples
                    if not category_issues.empty:
                        examples = category_issues['Ticker'].tolist()[:3]
                        print(f"  Examples: {examples}")
                    print()
        except Exception as e:
            print(f"Error checking name issues: {e}")
    
    def enforce_rate_limit(self):
        """Enforce rate limit for Finnhub API"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        
        # Enforce minimum delay between API calls
        if time_since_last_call < self.min_delay:
            sleep_time = self.min_delay - time_since_last_call
            print(f"  Rate limiting: waiting {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)
        
        # Update last call time
        self.last_call_time = time.time()
    
    def get_quote_finnhub(self, ticker):
        """Get quote from Finnhub API"""
        self.enforce_rate_limit()
        
        try:
            # Format ticker for special cases
            formatted_ticker = ticker
            if ticker.startswith('^'):
                # For indices, remove the ^ symbol
                formatted_ticker = ticker[1:]
            elif '=' in ticker:
                # For futures, use a different format
                formatted_ticker = ticker.split('=')[0]
            
            # Make API request
            url = f'https://finnhub.io/api/v1/quote?symbol={formatted_ticker}&token={self.api_key}'
            response = requests.get(url)
            
            # Check for HTTP errors
            response.raise_for_status()
            
            data = response.json()
            
            if 'c' in data and data['c'] > 0:
                price = data['c']
                return price, data
            else:
                return None, data
        except requests.exceptions.HTTPError as e:
            print(f"  HTTP Error: {e}")
            return None, {'error': str(e)}
        except requests.exceptions.ConnectionError as e:
            print(f"  Connection Error: {e}")
            return None, {'error': str(e)}
        except requests.exceptions.Timeout as e:
            print(f"  Timeout Error: {e}")
            return None, {'error': str(e)}
        except requests.exceptions.RequestException as e:
            print(f"  Request Error: {e}")
            return None, {'error': str(e)}
        except Exception as e:
            print(f"  Error getting quote from Finnhub: {e}")
            return None, {'error': str(e)}
    
    def get_company_profile(self, ticker):
        """Get company profile from Finnhub API"""
        self.enforce_rate_limit()
        
        try:
            # Make API request
            url = f'https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={self.api_key}'
            response = requests.get(url)
            
            # Check for HTTP errors
            response.raise_for_status()
            
            data = response.json()
            
            if 'name' in data and data['name']:
                name = data['name']
                return name, data
            else:
                return None, data
        except requests.exceptions.HTTPError as e:
            print(f"  HTTP Error: {e}")
            return None, {'error': str(e)}
        except requests.exceptions.ConnectionError as e:
            print(f"  Connection Error: {e}")
            return None, {'error': str(e)}
        except requests.exceptions.Timeout as e:
            print(f"  Timeout Error: {e}")
            return None, {'error': str(e)}
        except requests.exceptions.RequestException as e:
            print(f"  Request Error: {e}")
            return None, {'error': str(e)}
        except Exception as e:
            print(f"  Error getting company profile from Finnhub: {e}")
            return None, {'error': str(e)}
    
    def get_crypto_info(self, ticker):
        """Get crypto info from Finnhub API"""
        self.enforce_rate_limit()
        
        try:
            # Convert ticker format if needed (BTC-USD -> BINANCE:BTCUSDT)
            if '-USD' in ticker:
                symbol = ticker.replace('-USD', '')
                finnhub_ticker = f"BINANCE:{symbol}USDT"
            else:
                finnhub_ticker = ticker
            
            # Make API request
            url = f'https://finnhub.io/api/v1/crypto/candle?symbol={finnhub_ticker}&resolution=D&from={int(time.time())-86400}&to={int(time.time())}&token={self.api_key}'
            response = requests.get(url)
            
            # Check for HTTP errors
            response.raise_for_status()
            
            data = response.json()
            
            if 's' in data and data['s'] == 'ok' and 'c' in data and len(data['c']) > 0:
                price = data['c'][-1]
                return price, data
            else:
                return None, data
        except requests.exceptions.HTTPError as e:
            print(f"  HTTP Error: {e}")
            return None, {'error': str(e)}
        except requests.exceptions.ConnectionError as e:
            print(f"  Connection Error: {e}")
            return None, {'error': str(e)}
        except requests.exceptions.Timeout as e:
            print(f"  Timeout Error: {e}")
            return None, {'error': str(e)}
        except requests.exceptions.RequestException as e:
            print(f"  Request Error: {e}")
            return None, {'error': str(e)}
        except Exception as e:
            print(f"  Error getting crypto info from Finnhub: {e}")
            return None, {'error': str(e)}
    
    def get_symbol_lookup(self, ticker):
        """Look up symbol information from Finnhub API"""
        self.enforce_rate_limit()
        
        try:
            # Make API request
            url = f'https://finnhub.io/api/v1/search?q={ticker}&token={self.api_key}'
            response = requests.get(url)
            
            # Check for HTTP errors
            response.raise_for_status()
            
            data = response.json()
            
            if 'result' in data and len(data['result']) > 0:
                # Find exact match
                exact_matches = [r for r in data['result'] if r['symbol'] == ticker]
                if exact_matches:
                    return exact_matches[0]['description'], data
                else:
                    # Return first result
                    return data['result'][0]['description'], data
            else:
                return None, data
        except requests.exceptions.HTTPError as e:
            print(f"  HTTP Error: {e}")
            return None, {'error': str(e)}
        except requests.exceptions.ConnectionError as e:
            print(f"  Connection Error: {e}")
            return None, {'error': str(e)}
        except requests.exceptions.Timeout as e:
            print(f"  Timeout Error: {e}")
            return None, {'error': str(e)}
        except requests.exceptions.RequestException as e:
            print(f"  Request Error: {e}")
            return None, {'error': str(e)}
        except Exception as e:
            print(f"  Error getting symbol lookup from Finnhub: {e}")
            return None, {'error': str(e)}
    
    def test_ticker(self, ticker, category):
        """Test a single ticker with Finnhub API"""
        print(f"\nTesting ticker: {ticker}")
        
        results = {
            'ticker': ticker,
            'category': category,
            'quote_success': False,
            'profile_success': False,
            'lookup_success': False,
            'crypto_success': False
        }
        
        # Test quote endpoint
        price, quote_data = self.get_quote_finnhub(ticker)
        if price is not None:
            print(f"  ✓ QUOTE: Success! Price: ${price:.2f}")
            results['quote_success'] = True
        else:
            print(f"  ✗ QUOTE: Failed.")
        
        # Test company profile endpoint for stocks and ETFs
        if category in ['ideas', 'etfs']:
            name, profile_data = self.get_company_profile(ticker)
            if name is not None:
                print(f"  ✓ PROFILE: Success! Name: {name}")
                results['profile_success'] = True
            else:
                print(f"  ✗ PROFILE: Failed.")
        
        # Test symbol lookup for all categories
        lookup_name, lookup_data = self.get_symbol_lookup(ticker)
        if lookup_name is not None:
            print(f"  ✓ LOOKUP: Success! Name: {lookup_name}")
            results['lookup_success'] = True
        else:
            print(f"  ✗ LOOKUP: Failed.")
        
        # Test crypto endpoint for digital assets
        if category == 'digitalassets':
            crypto_price, crypto_data = self.get_crypto_info(ticker)
            if crypto_price is not None:
                print(f"  ✓ CRYPTO: Success! Price: ${crypto_price:.2f}")
                results['crypto_success'] = True
            else:
                print(f"  ✗ CRYPTO: Failed.")
        
        return results
    
    def run(self, sample_size=3):
        """Run the Finnhub API test"""
        print("Testing Finnhub API and checking database...\n")
        
        # Check for name issues in database
        self.check_name_issues()
        
        # Get tickers by category
        tickers_by_category = self.get_tickers_by_category(sample_size)
        if tickers_by_category is None:
            return
        
        print("\n=== FINNHUB API TEST ===")
        
        results = {}
        for category, tickers in tickers_by_category.items():
            print(f"\nTesting category: {category}")
            ticker_list = [t['Ticker'] for t in tickers]
            print(f"Test tickers: {ticker_list}")
            
            category_results = []
            for ticker_info in tickers:
                ticker = ticker_info['Ticker']
                result = self.test_ticker(ticker, category)
                category_results.append(result)
                
                # Add a small random delay between tickers
                time.sleep(random.uniform(1.5, 2.5))
            
            results[category] = category_results
        
        # Print summary
        print("\n=== SUMMARY ===\n")
        for category, category_results in results.items():
            quote_success = sum(1 for r in category_results if r['quote_success'])
            lookup_success = sum(1 for r in category_results if r['lookup_success'])
            total = len(category_results)
            
            print(f"Category: {category}")
            print(f"  QUOTE: {quote_success}/{total} successful")
            print(f"  LOOKUP: {lookup_success}/{total} successful")
            
            if category in ['ideas', 'etfs']:
                profile_success = sum(1 for r in category_results if r['profile_success'])
                print(f"  PROFILE: {profile_success}/{total} successful")
            
            if category == 'digitalassets':
                crypto_success = sum(1 for r in category_results if r['crypto_success'])
                print(f"  CRYPTO: {crypto_success}/{total} successful")
            
            print()
        
        # Print recommendation
        print("=== RECOMMENDATION ===")
        print("Based on the test results, here's the recommended approach:")
        print("1. Use Finnhub API for stock and ETF quotes")
        print("2. Use Finnhub API for company profiles to update names")
        print("3. For crypto assets, use Finnhub's crypto endpoints with proper symbol conversion")
        print("4. Implement robust caching to minimize API calls")
        print("5. Set appropriate rate limiting to stay under 60 calls/minute")

if __name__ == "__main__":
    tester = FinnhubTest()
    tester.run(sample_size=2)
