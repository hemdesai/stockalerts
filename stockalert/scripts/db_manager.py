import os
import sqlite3
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
import time
import json
import pytz

class StockAlertDBManager:
    """Database manager for StockAlert application"""
    
    def __init__(self, db_path=None):
        """Initialize the database manager"""
        if db_path is None:
            # Use default path
            project_root = Path(__file__).parent.parent
            db_path = project_root / 'data' / 'stocks.db'
        
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
        # Known ticker mappings for manual corrections
        self.ticker_mappings = {
            # Crypto mappings
            'BTC': 'BTC-USD',
            'ETH': 'ETH-USD',
            'SOL': 'SOL-USD',
            'AVAX': 'AVAX-USD',
            'XRP': 'XRP-USD'
        }
        
        # Update frequency in days for different categories
        self.update_frequency = {
            'ideas': 7,  # Weekly update
            'etfs': 7,   # Weekly update
            'digitalassets': 1,  # Daily update
            'daily': 1   # Daily update
        }
        
        # Path to store last update timestamps
        self.project_root = Path(__file__).parent.parent
        self.data_dir = self.project_root / 'data'
        self.update_log_path = self.data_dir / 'update_log.json'
        
        # Initialize update log if it doesn't exist
        self._initialize_update_log()
    
    def _initialize_update_log(self):
        """Initialize the update log file if it doesn't exist"""
        if not os.path.exists(self.update_log_path):
            update_log = {
                'ideas': {'last_update': None, 'last_file_mtime': None},
                'etfs': {'last_update': None, 'last_file_mtime': None},
                'digitalassets': {'last_update': None, 'last_file_mtime': None},
                'daily': {'last_update': None, 'last_file_mtime': None}
            }
            with open(self.update_log_path, 'w') as f:
                json.dump(update_log, f, indent=2)
    
    def _get_update_log(self):
        """Get the update log"""
        if os.path.exists(self.update_log_path):
            with open(self.update_log_path, 'r') as f:
                return json.load(f)
        else:
            self._initialize_update_log()
            return self._get_update_log()
    
    def _update_log(self, category, file_path=None):
        """Update the log for a category"""
        update_log = self._get_update_log()
        now = datetime.now().isoformat()
        
        update_log[category]['last_update'] = now
        
        if file_path and os.path.exists(file_path):
            mtime = os.path.getmtime(file_path)
            update_log[category]['last_file_mtime'] = mtime
        
        with open(self.update_log_path, 'w') as f:
            json.dump(update_log, f, indent=2)
    
    def should_update_category(self, category, file_path):
        """Check if a category should be updated based on frequency and file modification time"""
        if not os.path.exists(file_path):
            return False
            
        update_log = self._get_update_log()
        category_log = update_log.get(category, {})
        
        # Get current file modification time
        current_mtime = os.path.getmtime(file_path)
        last_mtime = category_log.get('last_file_mtime')
        
        # If we have no record of last update or file has been modified, update is needed
        if last_mtime is None or current_mtime > last_mtime:
            return True
            
        # Check if we should update based on frequency
        last_update_str = category_log.get('last_update')
        if last_update_str is None:
            return True
            
        last_update = datetime.fromisoformat(last_update_str)
        frequency_days = self.update_frequency.get(category, 1)
        
        # Check if enough days have passed since last update
        return (datetime.now() - last_update) >= timedelta(days=frequency_days)
    
    def connect(self):
        """Connect to the database"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        return self.conn
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
    
    def create_tables(self):
        """Create the necessary tables if they don't exist"""
        try:
            self.connect()
            
            # Create stocks table
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS stocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    name TEXT,
                    category TEXT,
                    sentiment TEXT,
                    target_price REAL,
                    stop_loss REAL,
                    AM_Price REAL,
                    PM_Price REAL,
                    Last_Price_Update TEXT,
                    UNIQUE(ticker, category)
                )
            ''')
            
            # Create alerts table
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    name TEXT,
                    price REAL,
                    target_price REAL,
                    stop_loss REAL,
                    alert_type TEXT,
                    session TEXT,
                    timestamp TEXT,
                    sent INTEGER DEFAULT 0
                )
            ''')
            
            # Create update log table
            self._initialize_update_log()
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error creating tables: {e}")
            return False
        finally:
            self.close()
    
    def validate_ticker(self, ticker, category):
        """Validate ticker symbol using Yahoo Finance"""
        try:
            # Check if we have a manual mapping for this ticker
            if ticker in self.ticker_mappings:
                ticker = self.ticker_mappings[ticker]
            
            # Use the ticker as is - no automatic -USD appending
            yf_ticker = ticker
            
            # Try to get basic info from Yahoo Finance with rate limiting
            try:
                ticker_obj = yf.Ticker(yf_ticker)
                # Sleep to avoid rate limiting (0.5 seconds per request)
                time.sleep(0.5)
                
                # Try to get the name from info
                info = ticker_obj.info
                name = info.get('shortName') or info.get('longName') or yf_ticker
                
                # Try to get current price
                current_price = info.get('regularMarketPrice') or info.get('currentPrice') or 0
                
                return {
                    'valid': True,
                    'ticker': yf_ticker,
                    'name': name,
                    'current_price': current_price
                }
            except Exception as e:
                print(f"Warning: Could not validate {yf_ticker} with Yahoo Finance: {e}")
                # Fallback to accepting the ticker without validation
                return {
                    'valid': True,
                    'ticker': yf_ticker,
                    'name': yf_ticker,  # Use ticker as name
                    'current_price': 0  # Default price
                }
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }
    
    def import_csv_data(self, csv_path, category):
        """Import data from CSV file into the database"""
        try:
            self.connect()
            
            # Check if file exists
            if not os.path.exists(csv_path):
                return {
                    'success': False,
                    'error': f"File not found: {csv_path}",
                    'imported_count': 0,
                    'error_count': 0,
                    'validation_errors': []
                }
            
            # Read CSV file
            df = pd.read_csv(csv_path)
            
            # Normalize column names (convert to lowercase)
            df.columns = [col.lower() for col in df.columns]
            
            # Map different column name formats to our standard format
            column_mapping = {
                'ticker': 'ticker',
                'sentiment': 'sentiment',
                'buy_trade': 'buy_trade',
                'buy trade': 'buy_trade',
                'sell_trade': 'sell_trade',
                'sell trade': 'sell_trade',
                'category': 'category'
            }
            
            # Rename columns based on mapping
            df = df.rename(columns={col: column_mapping[col] for col in df.columns if col in column_mapping})
            
            # Process each row
            imported_count = 0
            error_count = 0
            validation_errors = []
            
            for _, row in df.iterrows():
                try:
                    ticker = row['ticker']
                    
                    # Validate ticker
                    validation = self.validate_ticker(ticker, category)
                    
                    if validation['valid']:
                        # Insert into database
                        self.cursor.execute(
                            """
                            INSERT OR REPLACE INTO stocks 
                            (ticker, name, category, sentiment, target_price, stop_loss) 
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                validation['ticker'],
                                validation['name'],
                                category,
                                row['sentiment'],
                                row['buy_trade'],
                                row['sell_trade']
                            )
                        )
                        imported_count += 1
                    else:
                        error_count += 1
                        validation_errors.append({
                            'ticker': ticker,
                            'error': validation['error']
                        })
                except Exception as e:
                    error_count += 1
                    validation_errors.append({
                        'ticker': row.get('ticker', 'Unknown'),
                        'error': str(e)
                    })
            
            # Commit changes
            self.conn.commit()
            
            return {
                'success': True,
                'imported_count': imported_count,
                'error_count': error_count,
                'validation_errors': validation_errors
            }
            
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            return {
                'success': False,
                'error': str(e),
                'imported_count': 0,
                'error_count': 0,
                'validation_errors': []
            }
        finally:
            self.close()
    
    def delete_category_data(self, category):
        """Delete all data for a specific category"""
        try:
            self.connect()
            
            # Delete all records for this category
            self.cursor.execute(
                "DELETE FROM stocks WHERE category = ?",
                (category,)
            )
            deleted_count = self.cursor.rowcount
            print(f"Deleted {deleted_count} records for category {category}")
            
            # Commit changes
            self.conn.commit()
            
            return {
                'success': True,
                'deleted_count': deleted_count
            }
            
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            print(f"Error in delete_category_data: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            self.close()
    
    def get_all_stocks(self):
        """Get all stocks from the database"""
        try:
            self.connect()
            
            # Query all stocks
            self.cursor.execute("SELECT * FROM stocks")
            stocks = self.cursor.fetchall()
            
            # Get column names
            columns = [description[0] for description in self.cursor.description]
            
            # Convert to list of dictionaries
            result = []
            for stock in stocks:
                stock_dict = {}
                for i, column in enumerate(columns):
                    stock_dict[column] = stock[i]
                result.append(stock_dict)
            
            return result
            
        except Exception as e:
            print(f"Error in get_all_stocks: {e}")
            return []
        finally:
            self.close()
    
    def update_stock_names(self, category=None):
        """Update stock names by using ticker as name (no API calls)"""
        try:
            self.connect()
            
            # Get all stocks or stocks from a specific category
            if category:
                self.cursor.execute("SELECT ticker, category FROM stocks WHERE category = ?", (category,))
            else:
                self.cursor.execute("SELECT ticker, category FROM stocks")
            
            stocks = self.cursor.fetchall()
            
            for ticker, cat in stocks:
                try:
                    # Use ticker as name to avoid API calls
                    name = ticker
                    
                    # Update the name in the database
                    self.cursor.execute(
                        "UPDATE stocks SET name = ? WHERE ticker = ? AND category = ?",
                        (name, ticker, cat)
                    )
                except Exception as e:
                    print(f"Error updating name for {ticker}: {e}")
            
            self.conn.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self.close()
            
    def get_asset_data(self, category=None, sentiment=None):
        """Get asset data from the database with optional category and sentiment filters"""
        try:
            self.connect()
            
            # Build the query based on filters
            query = "SELECT * FROM stocks"
            params = []
            
            # Add WHERE clause if filters are provided
            where_clauses = []
            if category:
                where_clauses.append("category = ?")
                params.append(category)
            
            if sentiment:
                where_clauses.append("sentiment = ?")
                params.append(sentiment)
            
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            
            # Execute the query
            self.cursor.execute(query, params)
            
            # Fetch all rows
            rows = self.cursor.fetchall()
            
            # Get column names
            columns = [description[0] for description in self.cursor.description]
            
            # Convert to list of dictionaries
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))
            
            return result
        except Exception as e:
            return {"error": str(e)}
        finally:
            self.close()
    
    def get_validation_errors(self):
        """Get tickers with validation errors"""
        try:
            self.connect()
            
            # Query for tickers that failed validation
            query = """
            SELECT ticker, category, error_message 
            FROM validation_errors
            ORDER BY timestamp DESC
            """
            
            self.cursor.execute(query)
            rows = self.cursor.fetchall()
            
            # Get column names
            columns = [description[0] for description in self.cursor.description]
            
            # Convert to list of dictionaries
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))
            
            return result
        except Exception as e:
            return {"error": str(e)}
        finally:
            self.close()
    
    def update_ticker_mapping(self, original_ticker, corrected_ticker, category):
        """Update ticker mapping for validation errors"""
        try:
            self.connect()
            
            # Add to ticker mappings
            self.ticker_mappings[original_ticker] = corrected_ticker
            
            # Save to database
            mapping_json = json.dumps(self.ticker_mappings)
            
            # Check if mappings table exists
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticker_mappings (
                id INTEGER PRIMARY KEY,
                mappings TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Update or insert mappings
            self.cursor.execute("SELECT id FROM ticker_mappings LIMIT 1")
            if self.cursor.fetchone():
                self.cursor.execute(
                    "UPDATE ticker_mappings SET mappings = ?, updated_at = CURRENT_TIMESTAMP",
                    (mapping_json,)
                )
            else:
                self.cursor.execute(
                    "INSERT INTO ticker_mappings (mappings) VALUES (?)",
                    (mapping_json,)
                )
            
            # Remove from validation errors
            self.cursor.execute(
                "DELETE FROM validation_errors WHERE ticker = ? AND category = ?",
                (original_ticker, category)
            )
            
            # Update ticker in stocks table if it exists
            self.cursor.execute(
                "UPDATE stocks SET ticker = ? WHERE ticker = ? AND category = ?",
                (corrected_ticker, original_ticker, category)
            )
            
            self.conn.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self.close()
    
    def add_correction(self, ticker, category, field, value):
        """Add a correction to a specific field for a ticker"""
        try:
            self.connect()
            
            # Check if ticker exists
            self.cursor.execute(
                "SELECT * FROM stocks WHERE ticker = ? AND category = ?",
                (ticker, category)
            )
            
            row = self.cursor.fetchone()
            if not row:
                return {"success": False, "error": f"Ticker {ticker} not found in category {category}"}
            
            # Get column names
            columns = [description[0] for description in self.cursor.description]
            stock_data = dict(zip(columns, row))
            
            # Store original value
            original_value = stock_data.get(field)
            
            # Apply correction
            if field == "buy_trade" or field == "sell_trade":
                try:
                    value = float(value)
                except ValueError:
                    return {"success": False, "error": f"Value for {field} must be a number"}
            
            # Update the field
            self.cursor.execute(
                f"UPDATE stocks SET {field} = ? WHERE ticker = ? AND category = ?",
                (value, ticker, category)
            )
            
            # Log the correction
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS corrections (
                id INTEGER PRIMARY KEY,
                ticker TEXT,
                category TEXT,
                field TEXT,
                original_value TEXT,
                corrected_value TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            self.cursor.execute(
                "INSERT INTO corrections (ticker, category, field, original_value, corrected_value) VALUES (?, ?, ?, ?, ?)",
                (ticker, category, field, str(original_value), str(value))
            )
            
            self.conn.commit()
            return {
                "success": True, 
                "original_value": original_value,
                "corrected_value": value
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self.close()

    def cache_ticker_price(self, ticker, price, session=None):
        """
        Cache a ticker price in the database
        
        Args:
            ticker (str): Ticker symbol
            price (float): Current price
            session (str, optional): Trading session, either "AM" or "PM". If None, determines based on current time.
        
        Returns:
            bool: Success status
        """
        if session is None:
            # Determine session based on current Eastern Time
            ny_tz = pytz.timezone('America/New_York')
            now = datetime.now(ny_tz)
            session = "AM" if now.hour < 12 else "PM"
            
        try:
            self.connect()
            
            # Determine which column to update
            price_column = "AM_Price" if session == "AM" else "PM_Price"
            
            # Get current Eastern Time for timestamp
            ny_tz = pytz.timezone('America/New_York')
            eastern_time = datetime.now(ny_tz).strftime("%Y-%m-%d %H:%M:%S")
            
            # Update the price in the database with Eastern Time timestamp
            self.cursor.execute(
                f"UPDATE stocks SET {price_column} = ?, Last_Price_Update = ? WHERE ticker = ?",
                (price, eastern_time, ticker)
            )
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error caching price for {ticker}: {e}")
            return False
        finally:
            self.close()
            
    def get_ticker_price(self, ticker, session=None):
        """
        Get the cached price for a ticker
        
        Args:
            ticker (str): Ticker symbol
            session (str, optional): Trading session, either "AM" or "PM". If None, returns the most recent price.
        
        Returns:
            float: Cached price or None if not found
        """
        try:
            self.connect()
            
            if session:
                # Get price for specific session
                price_column = "AM_Price" if session == "AM" else "PM_Price"
                self.cursor.execute(
                    f"SELECT {price_column} FROM stocks WHERE ticker = ?",
                    (ticker,)
                )
                result = self.cursor.fetchone()
                return result[0] if result else None
            else:
                # Get most recent price (prefer PM if available, otherwise AM)
                self.cursor.execute(
                    "SELECT PM_Price, AM_Price FROM stocks WHERE ticker = ?",
                    (ticker,)
                )
                result = self.cursor.fetchone()
                if result:
                    return result[0] if result[0] is not None else result[1]
                return None
        except Exception as e:
            print(f"Error getting cached price for {ticker}: {e}")
            return None
        finally:
            self.close()
