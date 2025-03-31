"""
View the contents of the requests_cache SQLite database
"""
import sqlite3
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def view_cache_contents():
    """View the contents of the cache file"""
    # Path to the cache file
    cache_file = Path(project_root) / 'data' / 'stockalert_yfinance.cache'
    
    if not cache_file.exists():
        print(f"Cache file not found: {cache_file}")
        return
    
    # Connect to the SQLite database
    conn = sqlite3.connect(cache_file)
    
    # Get list of tables
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print(f"Cache file: {cache_file}")
    print(f"Tables in cache: {[table[0] for table in tables]}")
    print("-" * 50)
    
    # Query the responses table
    try:
        # Get count of cached responses
        cursor.execute("SELECT COUNT(*) FROM responses")
        count = cursor.fetchone()[0]
        print(f"Total cached responses: {count}")
        
        # Get the most recent entries
        df = pd.read_sql_query(
            "SELECT url, created, expires, _id FROM responses ORDER BY created DESC LIMIT 10", 
            conn
        )
        
        # Format timestamps
        df['created'] = df['created'].apply(
            lambda x: datetime.fromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S')
        )
        df['expires'] = df['expires'].apply(
            lambda x: datetime.fromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S')
        )
        
        print("\nMost recent cache entries:")
        print(df.to_string())
        
        # Extract ticker symbols from URLs
        tickers = []
        for url in df['url']:
            if 'chart/' in url:
                ticker = url.split('chart/')[1].split('?')[0]
                tickers.append(ticker)
            else:
                tickers.append('N/A')
        
        print("\nCached tickers:")
        for ticker in tickers:
            print(f"  - {ticker}")
            
    except Exception as e:
        print(f"Error querying cache: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    view_cache_contents()