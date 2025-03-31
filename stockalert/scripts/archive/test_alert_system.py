import os
import pandas as pd
import sqlite3
import time
import random
from pathlib import Path
import argparse
from alert_system import AlertSystem

class AlertSystemTester:
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.db_path = self.root_dir / 'data' / 'stocks.db'
        self.alert_system = AlertSystem()
        
    def get_sample_tickers(self, category=None, sample_size=3):
        """Get a sample of tickers from the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            if category:
                query = f"""
                SELECT Ticker, Name, Category
                FROM stocks
                WHERE Category = '{category}'
                ORDER BY RANDOM()
                LIMIT {sample_size}
                """
            else:
                query = f"""
                SELECT Ticker, Name, Category
                FROM stocks
                ORDER BY RANDOM()
                LIMIT {sample_size}
                """
                
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                print(f"No tickers found for category: {category}")
                return []
                
            print(f"Found {len(df)} sample tickers")
            return df.to_dict('records')
        except Exception as e:
            print(f"Error getting sample tickers: {e}")
            return []
    
    def test_price_fetching(self, tickers, delay_between_tickers=60):
        """Test fetching prices for a list of tickers"""
        results = {
            'success': [],
            'failure': []
        }
        
        print(f"\n=== TESTING PRICE FETCHING FOR {len(tickers)} TICKERS ===\n")
        
        for i, ticker_info in enumerate(tickers):
            ticker = ticker_info['Ticker']
            category = ticker_info['Category']
            name = ticker_info['Name']
            
            print(f"\nTesting {i+1}/{len(tickers)}: {ticker} ({name}) - Category: {category}")
            
            # Add a delay between tickers to avoid rate limiting
            if i > 0:
                wait_time = delay_between_tickers + random.uniform(5, 15)
                print(f"Waiting {wait_time:.1f} seconds before next ticker...")
                time.sleep(wait_time)
            
            try:
                price = self.alert_system.get_current_price(ticker, category)
                
                if price is not None:
                    print(f"✓ Success! Price for {ticker}: ${price:.2f}")
                    results['success'].append({
                        'ticker': ticker,
                        'category': category,
                        'name': name,
                        'price': price
                    })
                else:
                    print(f"✗ Failed to get price for {ticker}")
                    results['failure'].append({
                        'ticker': ticker,
                        'category': category,
                        'name': name
                    })
            except Exception as e:
                print(f"✗ Error getting price for {ticker}: {e}")
                results['failure'].append({
                    'ticker': ticker,
                    'category': category,
                    'name': name,
                    'error': str(e)
                })
        
        return results
    
    def test_alert_generation(self, sample_size=3):
        """Test generating alerts for a sample of tickers"""
        print("\n=== TESTING ALERT GENERATION ===\n")
        
        # Get latest signals from database
        df = self.alert_system.get_latest_signals()
        if df is None or df.empty:
            print("No signals found in database")
            return None
        
        # Take a random sample
        sample_df = df.sample(min(sample_size, len(df)))
        print(f"Testing alert generation with {len(sample_df)} tickers")
        
        # Generate alerts with a small batch size
        alerts = self.alert_system.generate_alerts(sample_df, batch_size=1)
        
        print(f"\nGenerated {len(alerts)} alerts")
        for alert in alerts:
            print(f"Alert: {alert['ticker']} ({alert['name']}) - {alert['action']} at ${alert['current_price']:.2f}")
        
        return alerts
    
    def run_category_test(self, category, sample_size=3, delay=60):
        """Test a specific category of tickers"""
        print(f"\n=== TESTING CATEGORY: {category.upper()} ===\n")
        
        # Get sample tickers for the category
        tickers = self.get_sample_tickers(category, sample_size)
        
        if not tickers:
            print(f"No tickers found for category: {category}")
            return
        
        # Test price fetching
        results = self.test_price_fetching(tickers, delay)
        
        # Print summary
        print(f"\n=== SUMMARY FOR {category.upper()} ===")
        print(f"Success: {len(results['success'])}/{len(tickers)}")
        print(f"Failure: {len(results['failure'])}/{len(tickers)}")
        
        return results
    
    def run_full_test(self, sample_size=2, delay=60):
        """Run a full test of all categories"""
        categories = ['ideas', 'etfs', 'digitalassets', 'daily']
        all_results = {}
        
        print("\n=== RUNNING FULL SYSTEM TEST ===\n")
        
        for category in categories:
            all_results[category] = self.run_category_test(category, sample_size, delay)
            
            # Add a longer delay between categories
            wait_time = 120 + random.uniform(10, 30)
            print(f"\nWaiting {wait_time:.1f} seconds before next category...")
            time.sleep(wait_time)
        
        # Test alert generation with a small sample
        alerts = self.test_alert_generation(sample_size=sample_size)
        
        # Print overall summary
        print("\n=== OVERALL SUMMARY ===")
        total_success = sum(len(results['success']) for results in all_results.values() if results)
        total_failure = sum(len(results['failure']) for results in all_results.values() if results)
        total_tickers = total_success + total_failure
        
        print(f"Total tickers tested: {total_tickers}")
        print(f"Success: {total_success}/{total_tickers} ({total_success/total_tickers*100:.1f}%)")
        print(f"Failure: {total_failure}/{total_tickers} ({total_failure/total_tickers*100:.1f}%)")
        print(f"Alerts generated: {len(alerts) if alerts else 0}")
        
        return all_results, alerts

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test the stock alert system')
    parser.add_argument('--category', type=str, choices=['ideas', 'etfs', 'digitalassets', 'daily'], 
                        help='Test a specific category')
    parser.add_argument('--sample', type=int, default=2, help='Number of tickers to sample per category')
    parser.add_argument('--delay', type=int, default=60, help='Delay between ticker tests in seconds')
    parser.add_argument('--alerts', action='store_true', help='Test alert generation only')
    
    args = parser.parse_args()
    
    tester = AlertSystemTester()
    
    if args.alerts:
        # Test alert generation only
        tester.test_alert_generation(args.sample)
    elif args.category:
        # Test a specific category
        tester.run_category_test(args.category, args.sample, args.delay)
    else:
        # Run full test
        tester.run_full_test(args.sample, args.delay)
