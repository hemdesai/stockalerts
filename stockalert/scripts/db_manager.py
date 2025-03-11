import os
import sqlite3
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
import time

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
    
    def initialize_database(self):
        """Create database tables if they don't exist"""
        self.connect()
        
        # Create assets table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            name TEXT,
            category TEXT NOT NULL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, category)
        )
        ''')
        
        # Create price_data table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            date DATE NOT NULL,
            sentiment TEXT,
            buy_trade REAL,
            sell_trade REAL,
            current_price REAL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES assets(id),
            UNIQUE(asset_id, date)
        )
        ''')
        
        # Create alerts table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            alert_type TEXT NOT NULL,
            threshold REAL,
            active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
        ''')
        
        # Create alert_history table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER NOT NULL,
            triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            price_at_trigger REAL,
            notification_sent BOOLEAN DEFAULT 0,
            FOREIGN KEY (alert_id) REFERENCES alerts(id)
        )
        ''')
        
        # Create corrections table for manual adjustments
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            original_value TEXT,
            corrected_value TEXT,
            corrected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
        ''')
        
        self.conn.commit()
        self.close()
    
    def validate_ticker(self, ticker, category):
        """Validate ticker symbol using Yahoo Finance"""
        try:
            # Check if we have a manual mapping for this ticker
            if ticker in self.ticker_mappings:
                ticker = self.ticker_mappings[ticker]
            
            # Adjust ticker format based on category
            if category == 'digitalassets' and not ticker.endswith('-USD'):
                yf_ticker = f"{ticker}-USD"
            else:
                yf_ticker = ticker
            
            # Try to get info from Yahoo Finance
            ticker_obj = yf.Ticker(yf_ticker)
            info = ticker_obj.info
            
            # Add a small delay to avoid rate limiting
            time.sleep(0.05)  # 50ms delay between requests
            
            # Check if we got valid data
            if 'regularMarketPrice' in info and info['regularMarketPrice'] is not None:
                return {
                    'valid': True,
                    'ticker': yf_ticker,
                    'name': info.get('shortName', ''),
                    'current_price': info.get('regularMarketPrice', 0)
                }
            else:
                # Try alternative ticker formats
                if category == 'digitalassets':
                    alternatives = [f"{ticker}USD", f"{ticker}USDT", ticker]
                else:
                    alternatives = [f"{ticker}.NS", f"{ticker}.L", f"{ticker}.TO"]
                
                for alt_ticker in alternatives:
                    try:
                        ticker_obj = yf.Ticker(alt_ticker)
                        info = ticker_obj.info
                        # Add a small delay to avoid rate limiting
                        time.sleep(0.05)  # 50ms delay between requests
                        
                        if 'regularMarketPrice' in info and info['regularMarketPrice'] is not None:
                            return {
                                'valid': True,
                                'ticker': alt_ticker,
                                'name': info.get('shortName', ''),
                                'current_price': info.get('regularMarketPrice', 0)
                            }
                    except:
                        continue
                
                # If all attempts failed, check if we should force accept this ticker
                # This is useful for tickers that we know exist but Yahoo Finance doesn't have
                if self.should_force_accept_ticker(ticker, category):
                    return {
                        'valid': True,
                        'ticker': ticker,
                        'name': f"{ticker} (Manual)",
                        'current_price': 0  # We don't have price data
                    }
                
                return {
                    'valid': False,
                    'ticker': ticker,
                    'name': '',
                    'current_price': 0,
                    'error': 'Could not validate ticker with Yahoo Finance'
                }
        except Exception as e:
            return {
                'valid': False,
                'ticker': ticker,
                'name': '',
                'current_price': 0,
                'error': str(e)
            }
    
    def should_force_accept_ticker(self, ticker, category):
        """Determine if we should force accept a ticker that Yahoo Finance doesn't recognize"""
        # Check if this ticker exists in our corrections table
        self.connect()
        
        try:
            # Check if we have a manual correction for this ticker
            self.cursor.execute(
                """
                SELECT a.id
                FROM assets a
                JOIN corrections c ON a.id = c.asset_id
                WHERE a.ticker = ? AND a.category = ? AND c.field_name = 'ticker'
                """,
                (ticker, category)
            )
            
            result = self.cursor.fetchone()
            return result is not None
        except:
            return False
        finally:
            self.close()
    
    def validate_price_data(self, buy_trade, sell_trade):
        """Validate price data for reasonableness"""
        errors = []
        
        # Check for non-negative values
        if buy_trade < 0:
            errors.append("Buy trade price cannot be negative")
        
        if sell_trade < 0:
            errors.append("Sell trade price cannot be negative")
        
        # Check for reasonable range between buy and sell
        if buy_trade > 0 and sell_trade > 0:
            price_diff_pct = abs(sell_trade - buy_trade) / min(buy_trade, sell_trade) * 100
            if price_diff_pct > 50:  # More than 50% difference might be suspicious
                errors.append(f"Large difference between buy and sell prices: {price_diff_pct:.2f}%")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def import_csv_data(self, csv_path, category):
        """Import data from CSV file into database"""
        try:
            # Check if file exists
            if not os.path.exists(csv_path):
                return {
                    'success': False,
                    'error': f"File not found: {csv_path}"
                }
            
            # Read CSV file
            df = pd.read_csv(csv_path)
            
            # Normalize column names (convert to lowercase)
            df.columns = [col.lower().replace(' ', '_') for col in df.columns]
            
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
            
            # Connect to database
            self.connect()
            
            # Delete existing price data for this category for today
            today = datetime.now().strftime('%Y-%m-%d')
            self.cursor.execute(
                """
                DELETE FROM price_data 
                WHERE asset_id IN (
                    SELECT id FROM assets WHERE category = ?
                ) AND date = ?
                """,
                (category, today)
            )
            
            # Process each row
            imported_count = 0
            error_count = 0
            validation_errors = []
            
            for _, row in df.iterrows():
                ticker = row['ticker']
                sentiment = row.get('sentiment', 'NEUTRAL')  # Default to NEUTRAL if not provided
                buy_trade = float(row['buy_trade'])
                sell_trade = float(row['sell_trade'])
                
                # Check if we have a manual mapping for this ticker
                if ticker in self.ticker_mappings:
                    ticker = self.ticker_mappings[ticker]
                
                # Validate ticker
                ticker_validation = self.validate_ticker(ticker, category)
                
                # Validate price data
                price_validation = self.validate_price_data(buy_trade, sell_trade)
                
                if not ticker_validation['valid']:
                    # Store the error for manual correction later
                    validation_errors.append({
                        'ticker': ticker,
                        'error': ticker_validation['error']
                    })
                    
                    # Add the ticker to the database anyway, but mark it as needing correction
                    self.cursor.execute(
                        "INSERT OR IGNORE INTO assets (ticker, name, category) VALUES (?, ?, ?)",
                        (ticker, f"{ticker} (Needs Validation)", category)
                    )
                    
                    asset_id = self.cursor.lastrowid
                    if not asset_id:  # If the ticker already exists, get its ID
                        self.cursor.execute(
                            "SELECT id FROM assets WHERE ticker = ? AND category = ?",
                            (ticker, category)
                        )
                        asset_result = self.cursor.fetchone()
                        if asset_result:
                            asset_id = asset_result[0]
                    
                    # Add a note in the corrections table
                    if asset_id:
                        self.cursor.execute(
                            """
                            INSERT INTO corrections 
                            (asset_id, field_name, original_value, corrected_value)
                            VALUES (?, ?, ?, ?)
                            """,
                            (asset_id, 'validation', 'failed', 'needs_correction')
                        )
                    
                    error_count += 1
                    continue
                
                if not price_validation['valid']:
                    validation_errors.append({
                        'ticker': ticker,
                        'error': ', '.join(price_validation['errors'])
                    })
                    error_count += 1
                    continue
                
                # Get or create asset record
                self.cursor.execute(
                    "SELECT id FROM assets WHERE ticker = ? AND category = ?",
                    (ticker_validation['ticker'], category)
                )
                asset_result = self.cursor.fetchone()
                
                if asset_result:
                    asset_id = asset_result[0]
                    # Update asset name if needed
                    self.cursor.execute(
                        "UPDATE assets SET name = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                        (ticker_validation['name'], asset_id)
                    )
                else:
                    # Insert new asset
                    self.cursor.execute(
                        "INSERT INTO assets (ticker, name, category) VALUES (?, ?, ?)",
                        (ticker_validation['ticker'], ticker_validation['name'], category)
                    )
                    asset_id = self.cursor.lastrowid
                
                # Insert or update price data
                today = datetime.now().strftime('%Y-%m-%d')
                
                self.cursor.execute(
                    "SELECT id FROM price_data WHERE asset_id = ? AND date = ?",
                    (asset_id, today)
                )
                price_result = self.cursor.fetchone()
                
                if price_result:
                    # Update existing price data
                    self.cursor.execute(
                        """
                        UPDATE price_data 
                        SET sentiment = ?, buy_trade = ?, sell_trade = ?, 
                            current_price = ?, last_updated = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (sentiment, buy_trade, sell_trade, 
                         ticker_validation['current_price'], price_result[0])
                    )
                else:
                    # Insert new price data
                    self.cursor.execute(
                        """
                        INSERT INTO price_data 
                        (asset_id, date, sentiment, buy_trade, sell_trade, current_price)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (asset_id, today, sentiment, buy_trade, sell_trade, 
                         ticker_validation['current_price'])
                    )
                
                imported_count += 1
            
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
                'error': str(e)
            }
        finally:
            self.close()
    
    def purge_old_data(self, retention_days=30):
        """Purge data older than the specified retention period"""
        try:
            self.connect()
            
            # Calculate cutoff date
            cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime('%Y-%m-%d')
            
            # Delete old price data
            self.cursor.execute(
                "DELETE FROM price_data WHERE date < ?",
                (cutoff_date,)
            )
            
            deleted_count = self.cursor.rowcount
            
            # Commit changes
            self.conn.commit()
            
            return {
                'success': True,
                'deleted_count': deleted_count
            }
        
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            self.close()
    
    def get_asset_data(self, category=None, sentiment=None):
        """Get asset data with optional filtering"""
        try:
            self.connect()
            
            query = """
            SELECT a.ticker, a.name, a.category, p.sentiment, 
                   p.buy_trade, p.sell_trade, p.current_price, p.date
            FROM assets a
            JOIN price_data p ON a.id = p.asset_id
            WHERE 1=1
            """
            
            params = []
            
            if category:
                query += " AND a.category = ?"
                params.append(category)
            
            if sentiment:
                query += " AND p.sentiment = ?"
                params.append(sentiment)
            
            # Order by category and ticker
            query += " ORDER BY a.category, a.ticker"
            
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            
            # Convert to list of dictionaries
            columns = ['ticker', 'name', 'category', 'sentiment', 
                       'buy_trade', 'sell_trade', 'current_price', 'date']
            result = []
            
            for row in rows:
                result.append(dict(zip(columns, row)))
            
            return result
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            self.close()
    
    def get_validation_errors(self):
        """Get a list of assets that need validation"""
        try:
            self.connect()
            
            self.cursor.execute(
                """
                SELECT a.ticker, a.category, c.original_value, c.corrected_value
                FROM assets a
                JOIN corrections c ON a.id = c.asset_id
                WHERE c.field_name = 'validation' AND c.corrected_value = 'needs_correction'
                """
            )
            
            rows = self.cursor.fetchall()
            
            # Convert to list of dictionaries
            result = []
            for row in rows:
                result.append({
                    'ticker': row[0],
                    'category': row[1],
                    'original_value': row[2],
                    'corrected_value': row[3]
                })
            
            return result
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            self.close()
    
    def update_ticker_mapping(self, original_ticker, corrected_ticker, category):
        """Update the ticker mapping in the database and in memory"""
        try:
            self.connect()
            
            # Find the asset
            self.cursor.execute(
                "SELECT id FROM assets WHERE ticker = ? AND category = ?",
                (original_ticker, category)
            )
            asset_result = self.cursor.fetchone()
            
            if not asset_result:
                return {
                    'success': False,
                    'error': f"Asset not found: {original_ticker} ({category})"
                }
            
            asset_id = asset_result[0]
            
            # Update the ticker in the assets table
            self.cursor.execute(
                "UPDATE assets SET ticker = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                (corrected_ticker, asset_id)
            )
            
            # Update or add a correction record
            self.cursor.execute(
                """
                INSERT OR REPLACE INTO corrections 
                (asset_id, field_name, original_value, corrected_value)
                VALUES (?, ?, ?, ?)
                """,
                (asset_id, 'ticker', original_ticker, corrected_ticker)
            )
            
            # Remove the validation error if it exists
            self.cursor.execute(
                """
                DELETE FROM corrections
                WHERE asset_id = ? AND field_name = 'validation' AND corrected_value = 'needs_correction'
                """,
                (asset_id,)
            )
            
            # Add to in-memory mapping
            self.ticker_mappings[original_ticker] = corrected_ticker
            
            # Commit changes
            self.conn.commit()
            
            return {
                'success': True,
                'original_ticker': original_ticker,
                'corrected_ticker': corrected_ticker
            }
        
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            self.close()
    
    def add_correction(self, ticker, category, field_name, corrected_value):
        """Add a manual correction for an asset"""
        try:
            self.connect()
            
            # Find the asset
            self.cursor.execute(
                "SELECT id FROM assets WHERE ticker = ? AND category = ?",
                (ticker, category)
            )
            asset_result = self.cursor.fetchone()
            
            if not asset_result:
                return {
                    'success': False,
                    'error': f"Asset not found: {ticker} ({category})"
                }
            
            asset_id = asset_result[0]
            
            # Get original value
            if field_name in ['name', 'ticker', 'category']:
                self.cursor.execute(
                    f"SELECT {field_name} FROM assets WHERE id = ?",
                    (asset_id,)
                )
            else:  # Assume it's a price_data field
                self.cursor.execute(
                    f"SELECT {field_name} FROM price_data WHERE asset_id = ? ORDER BY date DESC LIMIT 1",
                    (asset_id,)
                )
            
            value_result = self.cursor.fetchone()
            original_value = value_result[0] if value_result else None
            
            # Add correction record
            self.cursor.execute(
                """
                INSERT INTO corrections 
                (asset_id, field_name, original_value, corrected_value)
                VALUES (?, ?, ?, ?)
                """,
                (asset_id, field_name, str(original_value), str(corrected_value))
            )
            
            # Apply correction
            if field_name in ['name', 'ticker', 'category']:
                self.cursor.execute(
                    f"UPDATE assets SET {field_name} = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                    (corrected_value, asset_id)
                )
            else:  # Assume it's a price_data field
                self.cursor.execute(
                    f"""
                    UPDATE price_data 
                    SET {field_name} = ?, last_updated = CURRENT_TIMESTAMP 
                    WHERE asset_id = ? AND date = (SELECT MAX(date) FROM price_data WHERE asset_id = ?)
                    """,
                    (corrected_value, asset_id, asset_id)
                )
            
            # Commit changes
            self.conn.commit()
            
            return {
                'success': True,
                'original_value': original_value,
                'corrected_value': corrected_value
            }
        
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            self.close()
