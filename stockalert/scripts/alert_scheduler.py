import os
import time
import logging
import schedule
import threading
import pytz
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from stockalert.scripts.alert_system import AlertSystemImproved
from stockalert.utils.env_loader import get_env, load_environment
from stockalert.scripts.price_cache import PriceCache
from stockalert.scripts.generate_and_store_alerts import generate_and_store_alerts
from stockalert.scripts.db_manager import StockAlertDBManager

# Remove redundant environment loading since we're using the centralized loader
# load_environment()

class AlertScheduler:
    """Scheduler for running stock alerts at specific times"""
    
    def __init__(self):
        """Initialize the alert scheduler"""
        self.alert_system = AlertSystemImproved()
        self.running = False
        self.thread = None
        self.buffer_pct = 0.0  # No buffer for price alerts - exact price crossing
        self.price_cache = PriceCache()
        self.db_manager = StockAlertDBManager()
        self.price_caching_in_progress = False
        self.price_caching_complete = False
        self.last_caching_start_time = None
        
        # Schedule times (Eastern Time)
        self.morning_data_import_start = datetime.strptime('08:50', '%H:%M').time()
        self.morning_data_import_end = datetime.strptime('09:15', '%H:%M').time()
        self.morning_alert_time = datetime.strptime('11:11', '%H:%M').time()
        self.afternoon_alert_time = datetime.strptime('14:22', '%H:%M').time()
        
        self.ny_tz = pytz.timezone('America/New_York')
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(Path(__file__).parent.parent / 'data' / 'scheduler.log'),
                logging.StreamHandler()
            ]
        )
        
        # Log environment variables for debugging
        logging.info(f"Email sender: {get_env('EMAIL_SENDER', 'hemdesai@gmail.com')}")
        logging.info(f"Email recipient: {get_env('EMAIL_RECIPIENT', 'hemdesai@gmail.com')}")
        logging.info(f"Alert buffer set to {self.buffer_pct}%")
        logging.info(f"Morning data import window: {self.morning_data_import_start.strftime('%H:%M')} - {self.morning_data_import_end.strftime('%H:%M')} ET")
        logging.info(f"Morning alert time (with ticker refresh): {self.morning_alert_time.strftime('%H:%M')} ET")
        logging.info(f"Afternoon alert time (price refresh only): {self.afternoon_alert_time.strftime('%H:%M')} ET")
        
        # Check MCP connection
        self.using_mcp = self.alert_system.check_mcp_connection()
        if self.using_mcp:
            logging.info("MCP client connected and will be used for sending emails")
        else:
            logging.warning("MCP client not connected, will use direct Gmail API for sending emails")

    def is_market_open(self):
        """Check if US market is open"""
        now = datetime.now(self.ny_tz)
        
        # Check if it's a weekday
        if now.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            logging.info("Market closed - Weekend")
            return False
        
        # Check if time is between 9:30 AM and 4:00 PM
        market_start = now.replace(hour=9, minute=30, second=0)
        market_end = now.replace(hour=16, minute=0, second=0)
        
        is_open = market_start <= now <= market_end
        if not is_open:
            logging.info("Market closed - Outside trading hours")
        return is_open

    def get_all_tickers(self):
        """Get all tickers from the database that need price updates"""
        tickers = set()
        try:
            conn = sqlite3.connect(self.alert_system.db_path)
            cursor = conn.cursor()
            
            # Get tickers from all relevant tables
            for category in ['ideas', 'etfs', 'digitalassets', 'daily']:
                cursor.execute(f"SELECT ticker FROM {category}")
                category_tickers = [row[0] for row in cursor.fetchall()]
                tickers.update(category_tickers)
                
            conn.close()
            logging.info(f"Found {len(tickers)} unique tickers in database")
            return list(tickers)
        except Exception as e:
            logging.error(f"Error getting tickers: {e}")
            return []

    def cache_prices(self):
        """Cache prices for all tickers"""
        if self.price_caching_in_progress:
            logging.info("Price caching already in progress, skipping")
            return
            
        self.price_caching_in_progress = True
        self.price_caching_complete = False
        self.last_caching_start_time = datetime.now(self.ny_tz)
        
        logging.info("Starting price caching job")
        
        if not self.is_market_open():
            logging.info("Market is closed. Skipping price caching.")
            self.price_caching_in_progress = False
            return
            
        # Start price caching in a separate thread
        threading.Thread(target=self._cache_prices_thread).start()
    
    def _cache_prices_thread(self):
        """Thread function to cache prices for all tickers"""
        try:
            tickers = self.get_all_tickers()
            if tickers:
                # This will take some time depending on the number of tickers
                self.price_cache.cache_ticker_prices(tickers)
                logging.info(f"Completed caching prices for {len(tickers)} tickers")
                
                # Calculate how long it took
                elapsed_time = datetime.now(self.ny_tz) - self.last_caching_start_time
                logging.info(f"Price caching took {elapsed_time.total_seconds()/60:.2f} minutes")
                
                # Mark caching as complete
                self.price_caching_complete = True
            else:
                logging.warning("No tickers found to cache")
        except Exception as e:
            logging.error(f"Error in price caching thread: {e}")
            import traceback
            logging.error(traceback.format_exc())
        finally:
            self.price_caching_in_progress = False

    def update_ticker_names(self):
        """Update ticker names in the database"""
        logging.info("Starting ticker name update")
        
        try:
            # Update ticker names for all categories
            for category in ['ideas', 'etfs', 'digitalassets', 'daily']:
                logging.info(f"Updating ticker names for {category}")
                self.db_manager.update_stock_names(category)
                
            logging.info("Ticker name update completed")
        except Exception as e:
            logging.error(f"Error updating ticker names: {e}")
            import traceback
            logging.error(traceback.format_exc())

    def run_morning_alerts(self):
        """Run morning alerts with ticker name refresh and price caching"""
        try:
            current_time = datetime.now(self.ny_tz).strftime("%H:%M")
            logging.info(f"Starting morning alert run at {current_time} ET")
            
            if not self.is_market_open():
                logging.info("Market is closed. Skipping morning alert generation.")
                return
            
            # 1. Update ticker names first
            logging.info("Refreshing ticker names before price caching")
            self.update_ticker_names()
            
            # 2. Cache prices
            logging.info("Starting price caching for morning alerts")
            self.cache_prices()
            
            # 3. Wait for price caching to complete
            if self.price_caching_in_progress:
                logging.info("Price caching is still in progress. Waiting for completion...")
                
                # Wait for up to 10 minutes for price caching to complete
                wait_start = datetime.now(self.ny_tz)
                max_wait = timedelta(minutes=10)
                
                while self.price_caching_in_progress:
                    time.sleep(10)  # Check every 10 seconds
                    if datetime.now(self.ny_tz) - wait_start > max_wait:
                        logging.warning("Timed out waiting for price caching to complete")
                        break
                
                if self.price_caching_complete:
                    logging.info("Price caching completed. Proceeding with alert generation.")
                else:
                    logging.warning("Price caching did not complete successfully. Proceeding with alert generation anyway.")
            elif not self.price_caching_complete:
                logging.warning("Price caching was not run or did not complete. Proceeding with alert generation anyway.")
            
            # 4. Generate and send alerts
            self._generate_and_send_alerts("Morning")
                
        except Exception as e:
            logging.error(f"Error in morning alert run: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())

    def run_afternoon_alerts(self):
        """Run afternoon alerts with just price caching (no ticker refresh)"""
        try:
            current_time = datetime.now(self.ny_tz).strftime("%H:%M")
            logging.info(f"Starting afternoon alert run at {current_time} ET")
            
            if not self.is_market_open():
                logging.info("Market is closed. Skipping afternoon alert generation.")
                return
            
            # 1. Cache prices only (no ticker name refresh)
            logging.info("Starting price caching for afternoon alerts")
            self.cache_prices()
            
            # 2. Wait for price caching to complete
            if self.price_caching_in_progress:
                logging.info("Price caching is still in progress. Waiting for completion...")
                
                # Wait for up to 10 minutes for price caching to complete
                wait_start = datetime.now(self.ny_tz)
                max_wait = timedelta(minutes=10)
                
                while self.price_caching_in_progress:
                    time.sleep(10)  # Check every 10 seconds
                    if datetime.now(self.ny_tz) - wait_start > max_wait:
                        logging.warning("Timed out waiting for price caching to complete")
                        break
                
                if self.price_caching_complete:
                    logging.info("Price caching completed. Proceeding with alert generation.")
                else:
                    logging.warning("Price caching did not complete successfully. Proceeding with alert generation anyway.")
            elif not self.price_caching_complete:
                logging.warning("Price caching was not run or did not complete. Proceeding with alert generation anyway.")
            
            # 3. Generate and send alerts
            self._generate_and_send_alerts("Afternoon")
                
        except Exception as e:
            logging.error(f"Error in afternoon alert run: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())

    def _generate_and_send_alerts(self, session_name):
        """Generate and send alerts"""
        # Check MCP connection before sending emails
        self.using_mcp = self.alert_system.check_mcp_connection()
        if self.using_mcp:
            logging.info("MCP client connected and will be used for sending emails")
        else:
            logging.warning("MCP client not connected, will use direct Gmail API for sending emails")
        
        # Generate and store alerts, then send email
        result = generate_and_store_alerts(buffer_pct=self.buffer_pct, send_email=True)
        
        if result['generated'] > 0:
            # Determine if it's AM or PM based on current time
            current_hour = datetime.now(self.ny_tz).hour
            alert_time = "AM" if current_hour < 12 else "PM"
            logging.info(f"Generated {result['generated']} {alert_time} alerts, stored {result['stored']} in database")
            logging.info(f"{session_name} alerts sent successfully via {'MCP' if self.using_mcp else 'direct Gmail API'}")
        else:
            logging.info(f"No {session_name.lower()} alerts generated for current criteria")
            
        # Reset price caching status for next run
        self.price_caching_complete = False

    def schedule_jobs(self):
        """Schedule jobs for different times of the day"""
        # Morning alert at 11:11 AM ET (with ticker name refresh)
        schedule.every().day.at(self.morning_alert_time.strftime("%H:%M")).do(self.run_morning_alerts)
        logging.info(f"Scheduled morning alert job (with ticker refresh) for {self.morning_alert_time.strftime('%H:%M')} ET")
        
        # Afternoon alert at 2:22 PM ET (price refresh only)
        schedule.every().day.at(self.afternoon_alert_time.strftime("%H:%M")).do(self.run_afternoon_alerts)
        logging.info(f"Scheduled afternoon alert job (price refresh only) for {self.afternoon_alert_time.strftime('%H:%M')} ET")

    def run(self):
        """Main function to run the scheduler"""
        logging.info("Starting Alert Scheduler...")
        
        self.schedule_jobs()
        
        # Check if we should run initial alerts based on current time
        now = datetime.now(self.ny_tz)
        current_time = now.time()
        
        # If it's between morning alert time and afternoon alert time
        if self.morning_alert_time <= current_time < self.afternoon_alert_time:
            # If within 5 minutes after morning alert time
            morning_dt = datetime.combine(now.date(), self.morning_alert_time)
            morning_dt = self.ny_tz.localize(morning_dt)
            
            time_diff = abs((now - morning_dt).total_seconds() / 60)
            if time_diff <= 5:
                logging.info(f"Current time is within 5 minutes of morning alert time {self.morning_alert_time.strftime('%H:%M')}. Running initial morning alert.")
                self.run_morning_alerts()
        
        # If it's after afternoon alert time
        elif current_time >= self.afternoon_alert_time:
            # If within 5 minutes after afternoon alert time
            afternoon_dt = datetime.combine(now.date(), self.afternoon_alert_time)
            afternoon_dt = self.ny_tz.localize(afternoon_dt)
            
            time_diff = abs((now - afternoon_dt).total_seconds() / 60)
            if time_diff <= 5:
                logging.info(f"Current time is within 5 minutes of afternoon alert time {self.afternoon_alert_time.strftime('%H:%M')}. Running initial afternoon alert.")
                self.run_afternoon_alerts()
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logging.error(f"Error in scheduler loop: {str(e)}")
                time.sleep(300)  # Wait 5 minutes on error before retrying

def main():
    scheduler = AlertScheduler()
    scheduler.run()

if __name__ == "__main__":
    main()