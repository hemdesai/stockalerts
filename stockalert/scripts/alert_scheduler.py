import os
import time
import logging
import schedule
import threading
import pytz
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from alert_system import AlertSystem
from stockalert.utils.env_loader import get_env, load_environment

# Remove redundant environment loading since we're using the centralized loader
# load_environment()

class AlertScheduler:
    """Scheduler for running stock alerts at specific times"""
    
    def __init__(self):
        """Initialize the alert scheduler"""
        self.alert_system = AlertSystem()
        self.running = False
        self.thread = None
        self.buffer_pct = 2.0  # Default 2% buffer for price alerts
        
        # Schedule times for sending alerts (Eastern Time)
        self.schedule_times = [
            datetime.strptime('11:05', '%H:%M').time(),   # 11:05 AM EST
            datetime.strptime('14:35', '%H:%M').time(),  # 2:35 PM EST
        ]
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
        logging.info(f"Schedule times: {[t.strftime('%H:%M') for t in self.schedule_times]} EST")

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

    def run_alerts(self):
        """Generate and send alerts"""
        try:
            current_time = datetime.now(self.ny_tz).strftime("%H:%M")
            logging.info(f"Starting scheduled alert run at {current_time} EST")
            
            if not self.is_market_open():
                logging.info("Market is closed. Skipping alert generation.")
                return
            
            # Get and generate alerts
            df = self.alert_system.get_latest_signals()
            if df is None or df.empty:
                logging.warning("No signals data available")
                return
                
            alerts = self.alert_system.generate_alerts(df=df, buffer_pct=self.buffer_pct)
            
            if alerts:
                logging.info(f"Generated {len(alerts)} alerts")
                # Determine if it's AM or PM based on current time
                current_hour = datetime.now(self.ny_tz).hour
                alert_time = "AM" if current_hour < 12 else "PM"
                logging.info(f"Sending {alert_time} alerts")
                
                # Send email alerts
                self.alert_system.send_email_alert(alerts)
                logging.info(f"{alert_time} Alerts sent successfully")
            else:
                logging.info("No alerts generated for current criteria")
                
        except Exception as e:
            logging.error(f"Error in alert run: {str(e)}")

    def schedule_jobs(self):
        """Schedule alert jobs for specific times"""
        for schedule_time in self.schedule_times:
            schedule.every().day.at(schedule_time.strftime("%H:%M")).do(self.run_alerts)
            logging.info(f"Scheduled alert job for {schedule_time.strftime('%H:%M')} EST")

    def run(self):
        """Main function to run the scheduler"""
        logging.info("Starting Alert Scheduler...")
        
        self.schedule_jobs()
        
        # Run initial check
        self.run_alerts()
        
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