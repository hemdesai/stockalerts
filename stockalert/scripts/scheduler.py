import schedule
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime
import pytz

# Configure logging
project_root = Path(__file__).parent.parent
log_file = project_root / 'data' / 'scheduler.log'

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run_extraction():
    """Run the extraction scripts"""
    logging.info("Starting extraction process")
    
    try:
        # Run ideas extractor
        logging.info("Running ideas extractor")
        subprocess.run(
            ["python", "-m", "stockalert.scripts.email_extractors.ideas_extractor"],
            check=True
        )
        
        # Run crypto extractor
        logging.info("Running crypto extractor")
        subprocess.run(
            ["python", "-m", "stockalert.scripts.email_extractors.crypto_extractor"],
            check=True
        )
        
        # Import all data
        logging.info("Importing data into database")
        subprocess.run(
            ["python", "-m", "stockalert.scripts.import_all_data"],
            check=True
        )
        
        logging.info("Extraction process completed successfully")
        return True
    
    except Exception as e:
        logging.error(f"Error during extraction process: {e}")
        return False

def is_trading_day():
    """Check if today is a trading day (weekday)"""
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    
    # Check if it's a weekday (0 = Monday, 4 = Friday)
    return now.weekday() < 5

def main():
    """Main scheduler function"""
    logging.info("Starting scheduler")
    
    # Schedule daily extraction at 11:05 AM Eastern Time
    schedule.every().day.at("11:05").do(
        lambda: run_extraction() if is_trading_day() else logging.info("Not a trading day, skipping extraction")
    )
    
    # Schedule daily extraction at 2:35 PM Eastern Time
    schedule.every().day.at("14:35").do(
        lambda: run_extraction() if is_trading_day() else logging.info("Not a trading day, skipping extraction")
    )
    
    logging.info("Scheduler started, waiting for scheduled times")
    
    # Run the scheduler
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()
