import schedule
import time
from datetime import datetime
import pytz
from alert_system import AlertSystem

def is_market_open():
    ny_tz = pytz.timezone('America/New_York')
    now = datetime.now(ny_tz)
    
    # Check if it's a weekday
    if now.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        return False
    
    # Check if time is between 9:30 AM and 4:00 PM
    market_start = now.replace(hour=9, minute=30, second=0)
    market_end = now.replace(hour=16, minute=0, second=0)
    
    return market_start <= now <= market_end

def run_alerts():
    if is_market_open():
        alert_system = AlertSystem()
        alerts = alert_system.generate_alerts()
        if alerts:
            alert_system.send_email_alert(alerts)

def schedule_alerts():
    # Run every 2 hours during market hours
    schedule.every(2).hours.do(run_alerts)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    schedule_alerts() 