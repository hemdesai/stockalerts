"""
Main entry point for the automated scheduler with market holiday awareness.
"""
import asyncio
import signal
import sys
from app.services.scheduler.automated_scheduler import AutomatedScheduler
from app.core.logging import get_logger

logger = get_logger(__name__)


async def main():
    """Run the automated scheduler."""
    scheduler = AutomatedScheduler()
    
    # Handle shutdown gracefully
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received, stopping scheduler...")
        scheduler.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start the scheduler
        scheduler.start()
        
        # Show market calendar info
        logger.info("\n" + "="*60)
        logger.info("Market Holiday Awareness Active")
        logger.info("="*60)
        
        # Show upcoming holidays
        from datetime import date
        current_year = date.today().year
        holidays = scheduler.market_calendar.get_market_holidays(current_year)
        
        logger.info(f"\nMarket holidays for {current_year}:")
        for holiday_date, holiday_name in holidays[:10]:  # Show next 10
            if holiday_date >= date.today():
                logger.info(f"  {holiday_date}: {holiday_name}")
        
        # Show schedule info
        logger.info("\n" + "="*60)
        logger.info("Scheduled Tasks")
        logger.info("="*60)
        for job_info in scheduler.get_schedule_info():
            logger.info(f"\n{job_info['name']}:")
            logger.info(f"  Next run: {job_info['next_run']}")
            logger.info(f"  Schedule: {job_info['trigger']}")
        
        logger.info("\n" + "="*60)
        logger.info("Scheduler is running. Press Ctrl+C to stop.")
        logger.info("="*60)
        
        # Keep the scheduler running
        while True:
            await asyncio.sleep(60)  # Check every minute
            
            # Optionally log heartbeat
            if asyncio.get_event_loop().time() % 3600 < 60:  # Every hour
                logger.debug("Scheduler heartbeat - running normally")
                
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Scheduler error: {e}", exc_info=True)
    finally:
        scheduler.stop()
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    asyncio.run(main())