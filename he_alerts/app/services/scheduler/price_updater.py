"""
Scheduled price update service.
Runs twice daily to fetch prices from IBKR.
"""
import asyncio
from datetime import datetime, time
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import structlog

from app.core.database import AsyncSessionLocal
from app.services.ibkr.price_fetcher import PriceFetcher
from app.services.database.alert_service import AlertService
from app.core.config import settings

logger = structlog.get_logger(__name__)


class PriceUpdateScheduler:
    """Manages scheduled price updates."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)
        self.price_fetcher = PriceFetcher()
        self.alert_service = AlertService()
        
    async def run_price_update(self, session_type: str):
        """
        Run a price update for AM or PM session.
        
        Args:
            session_type: "AM" or "PM"
        """
        logger.info(f"Starting {session_type} price update")
        
        try:
            async with AsyncSessionLocal() as db:
                # Fetch and update prices
                result = await self.price_fetcher.update_stock_prices(db, session_type)
                
                logger.info(
                    f"{session_type} price update completed: "
                    f"{result['updated_count']}/{result['total_stocks']} stocks updated, "
                    f"{len(result['alerts'])} alerts triggered"
                )
                
                # Process alerts
                if result['alerts']:
                    await self.alert_service.process_price_alerts(db, result['alerts'])
                
        except Exception as e:
            logger.error(f"Error in {session_type} price update: {e}", exc_info=True)
    
    def start(self):
        """Start the price update scheduler."""
        # Parse schedule times
        am_hour, am_minute = map(int, settings.MORNING_PRICE_TIME.split(':'))
        pm_hour, pm_minute = map(int, settings.AFTERNOON_PRICE_TIME.split(':'))
        
        # Schedule AM price update
        self.scheduler.add_job(
            self.run_price_update,
            CronTrigger(
                hour=am_hour,
                minute=am_minute,
                timezone=settings.TIMEZONE
            ),
            args=['AM'],
            id='am_price_update',
            name='AM Price Update',
            replace_existing=True
        )
        
        # Schedule PM price update
        self.scheduler.add_job(
            self.run_price_update,
            CronTrigger(
                hour=pm_hour,
                minute=pm_minute,
                timezone=settings.TIMEZONE
            ),
            args=['PM'],
            id='pm_price_update',
            name='PM Price Update',
            replace_existing=True
        )
        
        self.scheduler.start()
        
        logger.info(
            f"Price update scheduler started. "
            f"AM updates at {settings.MORNING_PRICE_TIME} ET, "
            f"PM updates at {settings.AFTERNOON_PRICE_TIME} ET"
        )
    
    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Price update scheduler stopped")


# Manual price update functions for testing
async def run_manual_price_update(session_type: str = "AM"):
    """
    Manually run a price update (for testing).
    
    Args:
        session_type: "AM" or "PM"
    """
    updater = PriceUpdateScheduler()
    await updater.run_price_update(session_type)


if __name__ == "__main__":
    import sys
    
    # Check command line argument
    session = sys.argv[1] if len(sys.argv) > 1 else "AM"
    if session not in ["AM", "PM"]:
        print("Usage: python price_updater.py [AM|PM]")
        sys.exit(1)
    
    # Run manual update
    asyncio.run(run_manual_price_update(session))