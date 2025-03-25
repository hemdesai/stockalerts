"""
Generate and store alerts in the database
Uses cached prices from the database for AM and PM sessions
"""
import sys
import logging
import sqlite3
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from stockalert.scripts.alert_system import AlertSystemImproved
from stockalert.scripts.db_manager import StockAlertDBManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(project_root) / "data" / "alerts.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("generate_and_store_alerts")

def create_alerts_table():
    """Create alerts table in the database if it doesn't exist"""
    try:
        db_manager = StockAlertDBManager()
        db_manager.connect()
        
        # Create alerts table
        db_manager.cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            name TEXT,
            current_price FLOAT,
            threshold FLOAT,
            type TEXT,
            buy_trade FLOAT,
            sell_trade FLOAT,
            sentiment TEXT,
            category TEXT,
            price_pct FLOAT,
            session TEXT,
            timestamp TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
        ''')
        
        db_manager.conn.commit()
        logger.info("Alerts table created or already exists")
        db_manager.close()
        return True
    except Exception as e:
        logger.error(f"Error creating alerts table: {e}")
        return False

def store_alerts(alerts):
    """Store alerts in the database"""
    if not alerts:
        logger.info("No alerts to store")
        return 0
    
    try:
        db_manager = StockAlertDBManager()
        db_manager.connect()
        
        # Get current session
        session = alerts[0]['session']
        
        # Deactivate old alerts for this session
        db_manager.cursor.execute(
            "UPDATE alerts SET is_active = 0 WHERE session = ? AND is_active = 1",
            (session,)
        )
        
        # Insert new alerts
        count = 0
        for alert in alerts:
            db_manager.cursor.execute('''
            INSERT INTO alerts (
                ticker, name, current_price, threshold, type, 
                buy_trade, sell_trade, sentiment, category, 
                price_pct, session, timestamp, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''', (
                alert['ticker'], alert['name'], alert['current_price'], 
                alert['threshold'], alert['type'], alert['buy_trade'], 
                alert['sell_trade'], alert['sentiment'], alert['category'], 
                alert['price_pct'], alert['session'], alert['timestamp']
            ))
            count += 1
        
        db_manager.conn.commit()
        logger.info(f"Stored {count} alerts for {session} session")
        db_manager.close()
        return count
    except Exception as e:
        logger.error(f"Error storing alerts: {e}")
        return 0

def generate_and_store_alerts(buffer_pct=2.0, send_email=True):
    """Generate alerts and store them in the database"""
    try:
        # Create alerts table if it doesn't exist
        create_alerts_table()
        
        # Initialize alert system
        alert_system = AlertSystemImproved()
        
        # Generate alerts
        alerts = alert_system.generate_alerts(buffer_pct=buffer_pct)
        
        # Store alerts in database
        stored_count = store_alerts(alerts)
        
        # Send email if requested
        if alerts and send_email:
            alert_system.send_email(alerts)
        
        return {
            'generated': len(alerts),
            'stored': stored_count,
            'session': alert_system.get_current_session()
        }
    except Exception as e:
        logger.error(f"Error generating and storing alerts: {e}")
        return {
            'generated': 0,
            'stored': 0,
            'session': None,
            'error': str(e)
        }

if __name__ == "__main__":
    result = generate_and_store_alerts()
    
    print(f"\nAlert Generation Summary:")
    print(f"------------------------------------------")
    print(f"Session: {result.get('session', 'Unknown')}")
    print(f"Alerts generated: {result.get('generated', 0)}")
    print(f"Alerts stored in database: {result.get('stored', 0)}")
    if 'error' in result:
        print(f"Error: {result['error']}")
    print(f"------------------------------------------")
