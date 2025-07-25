"""
Scheduled alert runner for AM and PM sessions.
This script should be scheduled to run at specific times.
"""
import asyncio
import sys
from datetime import datetime
import pytz
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from alert_workflow import AlertWorkflow
from app.core.logging import get_logger

logger = get_logger(__name__)


async def run_scheduled_alerts():
    """Run the scheduled alert workflow."""
    eastern = pytz.timezone('America/New_York')
    now = datetime.now(eastern)
    
    # Determine session based on time
    hour = now.hour
    
    if 10 <= hour < 12:  # AM session window (10 AM - 12 PM ET)
        session = 'AM'
    elif 14 <= hour < 16:  # PM session window (2 PM - 4 PM ET)
        session = 'PM'
    else:
        logger.warning(f"Scheduled run at {now.strftime('%H:%M')} ET - outside trading windows")
        return
    
    logger.info(f"Starting scheduled alert run for {session} session at {now.strftime('%Y-%m-%d %H:%M:%S')} ET")
    
    workflow = AlertWorkflow()
    
    try:
        # Run complete workflow
        results = await workflow.run_complete_workflow(
            session=session,
            skip_price_fetch=False,  # Always fetch fresh prices
            send_email=True,         # Always send emails
            test_mode=False          # Production mode
        )
        
        # Log results
        if results.get('success'):
            logger.info(f"Scheduled alert run completed successfully")
            
            # Log details
            if results.get('price_fetch', {}).get('success'):
                pf = results['price_fetch']
                logger.info(f"Prices updated: {pf.get('prices_updated', 0)} stocks")
            
            if results.get('alerts', {}).get('success'):
                ar = results['alerts']
                logger.info(f"Alerts generated: {ar.get('alert_count', 0)}")
                
                if ar.get('alert_count', 0) > 0 and results.get('email_sent'):
                    logger.info("Alert email sent successfully")
        else:
            logger.error(f"Scheduled alert run failed: {results.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Critical error in scheduled alert run: {e}")
        raise


def main():
    """Main entry point."""
    try:
        asyncio.run(run_scheduled_alerts())
    except Exception as e:
        logger.error(f"Scheduled alert script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()