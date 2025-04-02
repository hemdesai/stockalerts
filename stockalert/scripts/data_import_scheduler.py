import os
import pandas as pd
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
import sys
from logging.handlers import TimedRotatingFileHandler

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Setup logging with rotation
log_file = Path(__file__).parent.parent / 'data' / 'data_import.log'
file_handler = TimedRotatingFileHandler(
    filename=log_file,
    when='D',
    interval=1,
    backupCount=7
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[file_handler, logging.StreamHandler()]
)

class DataImportScheduler:
    """Scheduler for importing CSV data into stocks.db"""

    def __init__(self):
        self.daily_categories = ['daily']
        self.weekly_categories = ['ideas', 'etfs', 'digitalassets']

    def import_to_database(self):
        """Import CSV data into stocks.db"""
        logging.info("Starting database import...")

        try:
            db_path = Path(__file__).parent.parent / 'data' / 'stocks.db'
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Clear existing records
            cursor.execute("DELETE FROM stocks")
            conn.commit()
            logging.info("Deleted all existing records from stocks table")

            data_dir = Path(__file__).parent.parent / 'data'

            for category in self.daily_categories + self.weekly_categories:
                csv_path = data_dir / f"{category}.csv"
                if csv_path.exists():
                    logging.info(f"Importing {category} data from {csv_path}...")
                    try:
                        df = pd.read_csv(csv_path)
                        df['category'] = category
                        df['Last_Price_Update'] = datetime.now().isoformat()

                        for _, row in df.iterrows():
                            cursor.execute("""
                                INSERT OR REPLACE INTO stocks 
                                (ticker, sentiment, name, buy_trade, sell_trade, category, AM_Price, PM_Price, Last_Price_Update)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                row.get('ticker'),
                                row.get('sentiment'),
                                row.get('name'),
                                row.get('buy_trade'),
                                row.get('sell_trade'),
                                row.get('category'),
                                row.get('AM_Price'),
                                row.get('PM_Price'),
                                row.get('Last_Price_Update')
                            ))

                        conn.commit()
                        logging.info(f"Inserted {len(df)} records into stocks table for {category}")
                    except Exception as e:
                        logging.error(f"Error processing {category}: {str(e)}")
                else:
                    logging.warning(f"CSV file for {category} not found at {csv_path}")

            conn.close()
            logging.info("Database import completed")
        except Exception as e:
            logging.error(f"Database connection error: {str(e)}")
            if 'conn' in locals():
               conn.close()

    def run_manual_import(self):
        """Run manual import from existing CSV files"""
        self.import_to_database()

if __name__ == "__main__":
    scheduler = DataImportScheduler()
    scheduler.run_manual_import()