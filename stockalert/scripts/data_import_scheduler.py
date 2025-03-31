import schedule
import time
from datetime import datetime, timedelta
import pytz
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import pandas as pd
import os
import sys

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import extractors
from stockalert.scripts.extractors.daily_extractor import DailyExtractor
from stockalert.scripts.extractors.crypto_extractor import CryptoEmailExtractor
from stockalert.scripts.extractors.etf_extractor import ETFEmailExtractor
from stockalert.scripts.extractors.ideas_extractor import IdeasEmailExtractor
from stockalert.scripts.csv_notification_service import CSVNotificationService
from stockalert.scripts.db_manager import StockAlertDBManager

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
                    success = extractor.extract_from_local_images()
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
                    data = extractor.extract()
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
        logging.info("Starting database import...")
        
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

    def check_market_prices(self):
        """Check current market prices at scheduled times"""
        current_time = datetime.now(self.ny_tz).strftime("%H:%M")
        logging.info(f"Checking market prices at {current_time}...")
        
        if not self.is_market_open():
            logging.info("Market is closed. Skipping market price check.")
            return
            
        try:
            # Check market prices for all assets in the database
            logging.info("Checking current market prices...")
            # Update market prices for all assets in the database
            self.db_manager.update_stock_names()
            logging.info("Market price check completed")
            
        except Exception as e:
            logging.error(f"Error checking market prices: {str(e)}")
            import traceback
            traceback.print_exc()

    def schedule_jobs(self):
        """Schedule data import jobs for specific times"""
        logging.info("Scheduling data import jobs...")
        
        # Schedule daily data refresh between 8:30 and 8:50 AM ET
        # Generate a random time within this window to avoid all extractors running at once
        import_start = datetime.strptime('08:30', '%H:%M').time()
        import_end = datetime.strptime('08:50', '%H:%M').time()
        
        # Calculate random minutes between start and end times
        start_minutes = import_start.hour * 60 + import_start.minute
        end_minutes = import_end.hour * 60 + import_end.minute
        
        # Generate random time within the window
        import random
        random_minutes = random.randint(start_minutes, end_minutes)
        scheduled_hour = random_minutes // 60
        scheduled_minute = random_minutes % 60
        scheduled_time = datetime.strptime(f'{scheduled_hour:02d}:{scheduled_minute:02d}', '%H:%M')
        
        # Schedule daily data refresh (daily and digitalassets) to run every day
        schedule.every().day.at(scheduled_time.strftime("%H:%M")).do(self.refresh_daily_data)
        logging.info(f"Scheduled daily data refresh for {scheduled_time.strftime('%H:%M')} ET (runs every trading day)")
        
        # Schedule weekly data refresh (ideas and etfs) at the same time
        # The refresh_weekly_data method has internal logic to only run on the first trading day of the week
        schedule.every().day.at(scheduled_time.strftime("%H:%M")).do(self.refresh_weekly_data)
        logging.info(f"Scheduled weekly data refresh for {scheduled_time.strftime('%H:%M')} ET (runs only on first trading day of week)")
        
        # Schedule database import at 9:25 AM ET
        schedule.every().day.at("09:45").do(self.import_to_database)
        logging.info("Scheduled database import for 9:45 AM ET")
        
        # Schedule market price checks
        schedule.every().day.at("11:11").do(self.check_market_prices)
        logging.info("Scheduled market price check for 11:11 AM ET")
        
        schedule.every().day.at("14:22").do(self.check_market_prices)
        logging.info("Scheduled market price check for 2:22 PM ET")

    def run(self):
        """Main function to run the scheduler"""
        logging.info("Starting Data Import Scheduler...")
        
        self.schedule_jobs()
        
        # Run initial refresh based on current time
        current_time = datetime.now(self.ny_tz).strftime("%H:%M")
        logging.info(f"Current time is {current_time} ET")
        
        # Check if we're near one of our scheduled times
        now = datetime.now(self.ny_tz)
        morning_check_time = now.replace(hour=11, minute=11, second=0)
        afternoon_check_time = now.replace(hour=14, minute=22, second=0)
        db_import_time = now.replace(hour=9, minute=45, second=0)
        
        # If we're within 5 minutes of morning check time
        if abs((now - morning_check_time).total_seconds()) < 300:  # Within 5 minutes
            logging.info("Current time is within 5 minutes of morning market check time (11:11 AM ET).")
            if now >= morning_check_time:
                logging.info("Running immediate market price check.")
                self.check_market_prices()
            else:
                logging.info("Waiting for scheduled market price check.")
        # If we're within 5 minutes of afternoon check time
        elif abs((now - afternoon_check_time).total_seconds()) < 300:  # Within 5 minutes
            logging.info("Current time is within 5 minutes of afternoon market check time (2:22 PM ET).")
            if now >= afternoon_check_time:
                logging.info("Running immediate market price check.")
                self.check_market_prices()
            else:
                logging.info("Waiting for scheduled market price check.")
        # If we're within 5 minutes of database import time
        elif abs((now - db_import_time).total_seconds()) < 300:  # Within 5 minutes
            logging.info("Current time is within 5 minutes of database import time (9:45 AM ET).")
            if now >= db_import_time:
                logging.info("Running immediate database import.")
                self.import_to_database()
            else:
                logging.info("Waiting for scheduled database import.")
        # If it's early in the day, run initial data refresh only
        elif now.hour < 9:
            logging.info("It's early in the day. Running initial data refresh.")
            self.refresh_daily_data()
            self.refresh_weekly_data()
        # Otherwise, just follow the schedule
        else:
            logging.info("Outside of scheduled windows. Will run according to schedule.")
        
        # Add a manual refresh option
        def manual_refresh():
            logging.info("Manual refresh triggered")
            # Force refresh regardless of market status for manual triggers
            logging.info("Forcing data refresh regardless of market status")
            
            # Always refresh daily categories
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
                        success = extractor.extract_from_local_images()
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
            
            # Only refresh weekly categories if it's the first trading day of the week
            if self.is_first_trading_day_of_week():
                logging.info("Today is the first trading day of the week - refreshing weekly categories")
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
                            data = extractor.extract()
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
            else:
                logging.info("Today is NOT the first trading day of the week - skipping weekly categories (ideas and etfs)")
        
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
    
    # Force immediate refresh of data
    print("Forcing immediate refresh of data categories...")
    
    # Always refresh daily categories
    print("Refreshing daily categories...")
    for category in scheduler.daily_categories:
        try:
            print(f"Refreshing {category} data...")
            extractor = scheduler.extractors[category]
            
            if category == 'daily':
                data = extractor.extract()
            elif category == 'digitalassets':
                data = extractor.extract_from_local_images()
                
            print(f"Successfully refreshed {category} data")
        except Exception as e:
            print(f"Error refreshing {category} data: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Only refresh weekly categories if it's the first trading day of the week
    if scheduler.is_first_trading_day_of_week():
        print("Today is the first trading day of the week - refreshing weekly categories...")
        for category in scheduler.weekly_categories:
            try:
                print(f"Refreshing {category} data...")
                extractor = scheduler.extractors[category]
                
                if category == 'etfs':
                    data = extractor.extract()
                elif category == 'ideas':
                    data = extractor.extract()
                    
                print(f"Successfully refreshed {category} data")
            except Exception as e:
                print(f"Error refreshing {category} data: {str(e)}")
                import traceback
                traceback.print_exc()
    else:
        print("Today is NOT the first trading day of the week - skipping weekly categories (ideas and etfs)")
    
    # Only start the scheduler if requested
    if "--run-scheduler" in sys.argv:
        scheduler.run()
    else:
        print("Data refresh complete. To start the scheduler, use the --run-scheduler flag.")

if __name__ == "__main__":
    main()
