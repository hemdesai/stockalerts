import schedule
import time
from datetime import datetime, timedelta
import pytz
import logging
from pathlib import Path
import pandas as pd
import os
import sys

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import extractors
from scripts.email_extractors.daily_extractor import DailyExtractor
from scripts.email_extractors.crypto_extractor import CryptoEmailExtractor
from scripts.email_extractors.etf_extractor import ETFEmailExtractor
from scripts.email_extractors.ideas_extractor import IdeasEmailExtractor
from scripts.csv_notification_service import CSVNotificationService
from scripts.db_manager import StockAlertDBManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / 'data' / 'data_import.log'),
        logging.StreamHandler()
    ]
)

class DataImportScheduler:
    def __init__(self):
        self.ny_tz = pytz.timezone('America/New_York')
        self.daily_categories = ['daily', 'digitalassets']
        self.weekly_categories = ['ideas', 'etfs']
        
        # Initialize extractors
        self.extractors = {
            'daily': DailyExtractor(),
            'digitalassets': CryptoEmailExtractor(),
            'etfs': ETFEmailExtractor(),
            'ideas': IdeasEmailExtractor()
        }
        
        # Initialize notification service
        self.notification_service = CSVNotificationService()
        
        # Initialize DB manager
        self.db_manager = StockAlertDBManager()
        
        # US market holidays for 2025 (update annually)
        self.market_holidays_2025 = [
            datetime(2025, 1, 1),   # New Year's Day
            datetime(2025, 1, 20),  # Martin Luther King Jr. Day
            datetime(2025, 2, 17),  # Presidents' Day
            datetime(2025, 4, 18),  # Good Friday
            datetime(2025, 5, 26),  # Memorial Day
            datetime(2025, 6, 19),  # Juneteenth
            datetime(2025, 7, 4),   # Independence Day
            datetime(2025, 9, 1),   # Labor Day
            datetime(2025, 11, 27), # Thanksgiving Day
            datetime(2025, 12, 25)  # Christmas Day
        ]

    def is_market_open(self):
        """Check if US market is open today"""
        now = datetime.now(self.ny_tz)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Check if it's a weekday
        if now.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            logging.info("Market closed - Weekend")
            return False
        
        # Check if it's a holiday
        for holiday in self.market_holidays_2025:
            if today.date() == holiday.date():
                logging.info(f"Market closed - Holiday: {holiday.strftime('%Y-%m-%d')}")
                return False
        
        # Check if time is between 9:30 AM and 4:00 PM
        market_start = now.replace(hour=9, minute=30, second=0)
        market_end = now.replace(hour=16, minute=0, second=0)
        
        is_open = market_start <= now <= market_end
        if not is_open:
            logging.info("Market closed - Outside trading hours")
            return False
            
        return True

    def is_first_trading_day_of_week(self):
        """Check if today is the first trading day of the week"""
        now = datetime.now(self.ny_tz)
        
        # If it's Monday and market is open, it's the first trading day
        if now.weekday() == 0 and self.is_market_open():
            return True
            
        # If Monday was a holiday, check if today is Tuesday and Monday was a holiday
        if now.weekday() == 1:
            yesterday = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            for holiday in self.market_holidays_2025:
                if yesterday.date() == holiday.date():
                    return True
                    
        # Special case: after a long weekend
        if now.weekday() == 1:  # Tuesday
            # Check if Monday was a holiday or weekend
            monday = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            for holiday in self.market_holidays_2025:
                if monday.date() == holiday.date():
                    return True
        
        return False

    def refresh_daily_data(self):
        """Refresh data for daily categories (daily and digitalassets)"""
        if not self.is_market_open():
            logging.info("Skipping daily data refresh - Market closed")
            return
            
        logging.info("Starting daily data refresh...")
        
        for category in self.daily_categories:
            try:
                logging.info(f"Refreshing {category} data...")
                extractor = self.extractors[category]
                
                if category == 'daily':
                    data = extractor.extract()
                    if data:
                        # Verify the data was saved correctly
                        csv_path = Path(__file__).parent.parent / 'data' / 'daily.csv'
                        if csv_path.exists():
                            df = pd.read_csv(csv_path)
                            logging.info(f"Daily data saved with {len(df)} records")
                            # Log some sample data
                            if not df.empty:
                                sample = df.head(3)
                                logging.info(f"Sample daily data: {sample[['ticker', 'sentiment']].to_dict('records')}")
                elif category == 'digitalassets':
                    success = extractor.extract_crypto_data()
                    if success:
                        # Verify the data was saved correctly
                        csv_path = Path(__file__).parent.parent / 'data' / 'digitalassets.csv'
                        if csv_path.exists():
                            df = pd.read_csv(csv_path)
                            logging.info(f"Digital assets data saved with {len(df)} records")
                            # Log some sample data
                            if not df.empty:
                                sample = df.head(3)
                                logging.info(f"Sample digital assets data: {sample[['ticker', 'sentiment']].to_dict('records')}")
                
                logging.info(f"Successfully refreshed {category} data")
                    
            except Exception as e:
                logging.error(f"Error refreshing {category} data: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Send notification after all CSVs are updated
        try:
            logging.info("Sending CSV notification email...")
            self.notification_service.send_csv_notification()
        except Exception as e:
            logging.error(f"Error sending CSV notification: {str(e)}")

    def refresh_weekly_data(self):
        """Refresh data for weekly categories (ideas and etfs)"""
        if not self.is_market_open():
            logging.info("Skipping weekly data refresh - Market closed")
            return
            
        if not self.is_first_trading_day_of_week():
            logging.info("Skipping weekly data refresh - Not first trading day of week")
            return
            
        logging.info("Starting weekly data refresh...")
        
        for category in self.weekly_categories:
            try:
                logging.info(f"Refreshing {category} data...")
                extractor = self.extractors[category]
                
                if category == 'etfs':
                    data = extractor.extract()
                    if data:
                        # Verify the data was saved correctly
                        csv_path = Path(__file__).parent.parent / 'data' / 'etfs.csv'
                        if csv_path.exists():
                            df = pd.read_csv(csv_path)
                            logging.info(f"ETF data saved with {len(df)} records")
                            # Log some sample data
                            if not df.empty:
                                sample = df.head(3)
                                logging.info(f"Sample ETF data: {sample[['ticker', 'sentiment']].to_dict('records')}")
                elif category == 'ideas':
                    data = extractor.extract_ideas_data()
                    if data:
                        # Verify the data was saved correctly
                        csv_path = Path(__file__).parent.parent / 'data' / 'ideas.csv'
                        if csv_path.exists():
                            df = pd.read_csv(csv_path)
                            logging.info(f"Ideas data saved with {len(df)} records")
                            # Log some sample data
                            if not df.empty:
                                sample = df.head(3)
                                logging.info(f"Sample ideas data: {sample[['ticker', 'sentiment']].to_dict('records')}")
                
                logging.info(f"Successfully refreshed {category} data")
                    
            except Exception as e:
                logging.error(f"Error refreshing {category} data: {str(e)}")
                import traceback
                traceback.print_exc()

    def import_to_database(self):
        """Import CSV data to database"""
        logging.info("Starting database import at 10:55 AM...")
        
        try:
            # Import each CSV file to the database
            data_dir = Path(__file__).parent.parent / 'data'
            
            for category in self.daily_categories + self.weekly_categories:
                csv_path = data_dir / f"{category}.csv"
                if csv_path.exists():
                    logging.info(f"Importing {category} data from {csv_path}...")
                    result = self.db_manager.import_csv_data(str(csv_path), category)
                    
                    if result.get('success', False):
                        logging.info(f"Successfully imported {result.get('imported_count', 0)} records for {category}")
                        if result.get('error_count', 0) > 0:
                            logging.warning(f"Had {result.get('error_count', 0)} errors during import")
                            for error in result.get('validation_errors', []):
                                logging.warning(f"Validation error: {error}")
                    else:
                        logging.error(f"Failed to import {category} data: {result.get('error', 'Unknown error')}")
                else:
                    logging.warning(f"CSV file for {category} not found at {csv_path}")
            
            logging.info("Database import completed")
        except Exception as e:
            logging.error(f"Error during database import: {str(e)}")
            import traceback
            traceback.print_exc()

    def schedule_jobs(self):
        """Schedule data import jobs"""
        # Schedule daily data refresh between 8:45 AM and 9:10 AM ET
        start_time = datetime.now(self.ny_tz).replace(hour=8, minute=45, second=0).time()
        end_time = datetime.now(self.ny_tz).replace(hour=9, minute=10, second=0).time()
        
        # Calculate a random time within the window
        total_minutes = (datetime.combine(datetime.today(), end_time) - datetime.combine(datetime.today(), start_time)).total_seconds() / 60
        random_minute = int(pd.np.random.randint(0, total_minutes))
        scheduled_time = (datetime.combine(datetime.today(), start_time) + timedelta(minutes=random_minute)).time()
        
        schedule.every().day.at(scheduled_time.strftime("%H:%M")).do(self.refresh_daily_data)
        logging.info(f"Scheduled daily data refresh for {scheduled_time.strftime('%H:%M')} ET (between 8:45 AM and 9:10 AM)")

        # Schedule database import at 10:55 AM ET
        schedule.every().day.at("10:55").do(self.import_to_database)
        logging.info("Scheduled database import for 10:55 AM ET")
        
        # Schedule weekly data refresh at 10:00 AM ET on the first trading day
        # schedule.every().day.at("10:00").do(self.refresh_weekly_data)
        # logging.info("Scheduled weekly data refresh for 10:00 ET (will only run on first trading day of week)")

    def run(self):
        """Main function to run the scheduler"""
        logging.info("Starting Data Import Scheduler...")
        
        self.schedule_jobs()
        
        # Run initial refresh
        current_time = datetime.now(self.ny_tz).strftime("%H:%M")
        logging.info(f"Running initial data refresh at {current_time} ET")
        
        # Check if market is open or will be open today
        now = datetime.now(self.ny_tz)
        market_open = now.replace(hour=8, minute=45, second=0)
        market_close = now.replace(hour=9, minute=10, second=0)
        
        # If we're before market open but market will open today
        if now < market_open and self.is_market_open():
            logging.info("Market will open today. Scheduling initial refresh for 8:45 AM ET")
        # If we're during market hours
        elif market_open <= now <= market_close and self.is_market_open():
            logging.info("Market is currently open. Running immediate refresh.")
            self.refresh_daily_data()
            self.refresh_weekly_data()
        # If market is already closed for today
        else:
            logging.info("Market is closed for today. Will check again tomorrow.")
        
        # Add a manual refresh option
        def manual_refresh():
            logging.info("Manual refresh triggered")
            # Force refresh regardless of market status for manual triggers
            logging.info("Forcing data refresh regardless of market status")
            
            for category in self.daily_categories:
                try:
                    logging.info(f"Manually refreshing {category} data...")
                    extractor = self.extractors[category]
                    
                    if category == 'daily':
                        data = extractor.extract()
                        if data:
                            # Verify the data was saved correctly
                            csv_path = Path(__file__).parent.parent / 'data' / 'daily.csv'
                            if csv_path.exists():
                                df = pd.read_csv(csv_path)
                                logging.info(f"Daily data saved with {len(df)} records")
                                if not df.empty:
                                    sample = df.head(3)
                                    logging.info(f"Sample daily data: {sample[['ticker', 'sentiment']].to_dict('records')}")
                    elif category == 'digitalassets':
                        success = extractor.extract_crypto_data()
                        if success:
                            # Verify the data was saved correctly
                            csv_path = Path(__file__).parent.parent / 'data' / 'digitalassets.csv'
                            if csv_path.exists():
                                df = pd.read_csv(csv_path)
                                logging.info(f"Digital assets data saved with {len(df)} records")
                                if not df.empty:
                                    sample = df.head(3)
                                    logging.info(f"Sample digital assets data: {sample[['ticker', 'sentiment']].to_dict('records')}")
                    
                    logging.info(f"Successfully refreshed {category} data")
                        
                except Exception as e:
                    logging.error(f"Error refreshing {category} data: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            for category in self.weekly_categories:
                try:
                    logging.info(f"Manually refreshing {category} data...")
                    extractor = self.extractors[category]
                    
                    if category == 'etfs':
                        data = extractor.extract()
                        if data:
                            # Verify the data was saved correctly
                            csv_path = Path(__file__).parent.parent / 'data' / 'etfs.csv'
                            if csv_path.exists():
                                df = pd.read_csv(csv_path)
                                logging.info(f"ETF data saved with {len(df)} records")
                                if not df.empty:
                                    sample = df.head(3)
                                    logging.info(f"Sample ETF data: {sample[['ticker', 'sentiment']].to_dict('records')}")
                    elif category == 'ideas':
                        data = extractor.extract_ideas_data()
                        if data:
                            # Verify the data was saved correctly
                            csv_path = Path(__file__).parent.parent / 'data' / 'ideas.csv'
                            if csv_path.exists():
                                df = pd.read_csv(csv_path)
                                logging.info(f"Ideas data saved with {len(df)} records")
                                if not df.empty:
                                    sample = df.head(3)
                                    logging.info(f"Sample ideas data: {sample[['ticker', 'sentiment']].to_dict('records')}")
                    
                    logging.info(f"Successfully refreshed {category} data")
                        
                except Exception as e:
                    logging.error(f"Error refreshing {category} data: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
        # Schedule a manual refresh option that can be triggered by creating a file
        trigger_file = Path(__file__).parent.parent / 'data' / 'trigger_refresh'
        
        while True:
            try:
                # Check for manual trigger file
                if trigger_file.exists():
                    logging.info(f"Found trigger file: {trigger_file}")
                    manual_refresh()
                    # Remove the trigger file
                    trigger_file.unlink()
                    logging.info("Removed trigger file after refresh")
                
                schedule.run_pending()
                time.sleep(10)  # Check every 10 seconds for manual triggers, 60 seconds was too long
            except Exception as e:
                logging.error(f"Error in scheduler loop: {str(e)}")
                time.sleep(300)  # Wait 5 minutes on error before retrying

def force_refresh():
    """Force an immediate data refresh by creating a trigger file"""
    trigger_file = Path(__file__).parent.parent / 'data' / 'trigger_refresh'
    with open(trigger_file, 'w') as f:
        f.write(f"Trigger refresh at {datetime.now()}")
    print(f"Created trigger file at {trigger_file}. The scheduler will detect this and run a refresh.")

def main():
    scheduler = DataImportScheduler()
    
    # Force immediate refresh of all data
    print("Forcing immediate refresh of all data categories...")
    for category in scheduler.daily_categories + scheduler.weekly_categories:
        try:
            print(f"Refreshing {category} data...")
            extractor = scheduler.extractors[category]
            
            if category == 'daily':
                data = extractor.extract()
            elif category == 'digitalassets':
                data = extractor.extract_crypto_data()
            elif category == 'etfs':
                data = extractor.extract()
            elif category == 'ideas':
                data = extractor.extract_ideas_data()
                
            print(f"Successfully refreshed {category} data")
        except Exception as e:
            print(f"Error refreshing {category} data: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Only start the scheduler if requested
    if "--run-scheduler" in sys.argv:
        scheduler.run()
    else:
        print("Data refresh complete. To start the scheduler, use the --run-scheduler flag.")

if __name__ == "__main__":
    main()
