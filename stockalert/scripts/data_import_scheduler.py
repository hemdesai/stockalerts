import os
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime, timedelta
import pytz
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
    when='D',  # Daily rotation
    interval=1,
    backupCount=7  # Keep logs for 7 days
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        file_handler,
        logging.StreamHandler()
    ]
)

class DataImportScheduler:
    """Scheduler for importing CSV data"""
    
    def __init__(self):
        """Initialize the scheduler"""
        self.daily_categories = ['daily']
        self.weekly_categories = ['ideas', 'etfs', 'digitalassets']
        
    def import_to_database(self):
        """Import CSV data to database"""
        logging.info("Starting database import...")
        
        try:
            # Import each CSV file to the database
            data_dir = Path(__file__).parent.parent / 'data'
            
            for category in self.daily_categories + self.weekly_categories:
                csv_path = data_dir / f"{category}.csv"
                if csv_path.exists():
                    logging.info(f"Importing {category} data from {csv_path}...")
                    try:
                        df = pd.read_csv(csv_path)
                        logging.info(f"Successfully imported {len(df)} records for {category}")
                    except Exception as e:
                        logging.error(f"Error importing {category} data: {str(e)}")
                else:
                    logging.warning(f"CSV file for {category} not found at {csv_path}")
            
            logging.info("Database import completed")
        except Exception as e:
            logging.error(f"Error during database import: {str(e)}")
            import traceback
            traceback.print_exc()

    def run_manual_import(self):
        """Run manual import from existing CSV files"""
        self.import_to_database()

if __name__ == "__main__":
    scheduler = DataImportScheduler()
    scheduler.run_manual_import()
