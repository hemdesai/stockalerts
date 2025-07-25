"""
Automated scheduler for HE Alerts with market holiday awareness.
"""
import asyncio
from datetime import datetime, time, date
from typing import Optional, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.core.config import settings
from app.core.logging import get_logger
from app.services.scheduler.market_calendar import MarketCalendar
import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from fetch_latest_emails import fetch_and_process_latest_emails
from alert_workflow import AlertWorkflow

logger = get_logger(__name__)


class AutomatedScheduler:
    """Handles all scheduled tasks with market awareness."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="America/New_York")
        self.market_calendar = MarketCalendar()
        self.alert_workflow = AlertWorkflow()
        
    async def check_and_run_email_extraction(self):
        """Run email extraction based on market day logic."""
        today = date.today()
        
        if not self.market_calendar.is_market_open(today):
            logger.info(f"Market closed on {today}, skipping email extraction")
            return
        
        try:
            if self.market_calendar.is_first_market_day_of_week(today):
                # First market day of week - run all 4 email types
                logger.info("First market day of week - extracting all 4 email types")
                email_types = ['daily', 'crypto', 'etfs', 'ideas']
            else:
                # Other market days - run only daily and crypto
                logger.info("Regular market day - extracting daily and crypto emails")
                email_types = ['daily', 'crypto']
            
            # Run extraction
            await fetch_and_process_latest_emails(email_types=email_types)
            logger.info(f"Successfully processed {len(email_types)} email types")
            
        except Exception as e:
            logger.error(f"Email extraction failed: {e}", exc_info=True)
    
    async def run_morning_alerts(self):
        """Run morning alert generation at 10:45 AM."""
        today = date.today()
        
        if not self.market_calendar.is_market_open(today):
            logger.info(f"Market closed on {today}, skipping morning alerts")
            return
        
        try:
            logger.info("Running morning alert workflow")
            await self.alert_workflow.run_complete_workflow(
                session="AM",
                skip_price_fetch=False,
                send_email=True,
                test_mode=False
            )
            logger.info("Morning alerts completed successfully")
            
        except Exception as e:
            logger.error(f"Morning alerts failed: {e}", exc_info=True)
    
    async def run_afternoon_alerts(self):
        """Run afternoon alert generation at 2:30 PM."""
        today = date.today()
        
        if not self.market_calendar.is_market_open(today):
            logger.info(f"Market closed on {today}, skipping afternoon alerts")
            return
        
        try:
            logger.info("Running afternoon alert workflow")
            await self.alert_workflow.run_complete_workflow(
                session="PM",
                skip_price_fetch=False,
                send_email=True,
                test_mode=False
            )
            logger.info("Afternoon alerts completed successfully")
            
        except Exception as e:
            logger.error(f"Afternoon alerts failed: {e}", exc_info=True)
    
    def setup_schedules(self):
        """Set up all scheduled tasks."""
        # Email extraction: 9:00 AM EST every market day
        self.scheduler.add_job(
            self.check_and_run_email_extraction,
            CronTrigger(
                day_of_week='mon-fri',
                hour=9,
                minute=0,
                timezone='America/New_York'
            ),
            id='email_extraction',
            name='Email Extraction (Market Days Only)',
            replace_existing=True
        )
        
        # Morning alerts: 10:45 AM EST every market day
        self.scheduler.add_job(
            self.run_morning_alerts,
            CronTrigger(
                day_of_week='mon-fri',
                hour=10,
                minute=45,
                timezone='America/New_York'
            ),
            id='morning_alerts',
            name='Morning Alerts (10:45 AM)',
            replace_existing=True
        )
        
        # Afternoon alerts: 2:30 PM EST every market day
        self.scheduler.add_job(
            self.run_afternoon_alerts,
            CronTrigger(
                day_of_week='mon-fri',
                hour=14,
                minute=30,
                timezone='America/New_York'
            ),
            id='afternoon_alerts',
            name='Afternoon Alerts (2:30 PM)',
            replace_existing=True
        )
        
        logger.info("Scheduled tasks configured:")
        logger.info("- Email extraction: 9:00 AM on market days")
        logger.info("- Morning alerts: 10:45 AM on market days")
        logger.info("- Afternoon alerts: 2:30 PM on market days")
    
    def start(self):
        """Start the scheduler."""
        self.setup_schedules()
        self.scheduler.start()
        logger.info("Automated scheduler started with market holiday awareness")
        
        # Log next scheduled runs
        for job in self.scheduler.get_jobs():
            logger.info(f"Next run for {job.name}: {job.next_run_time}")
    
    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Automated scheduler stopped")
    
    def get_schedule_info(self) -> List[dict]:
        """Get information about scheduled jobs."""
        jobs_info = []
        for job in self.scheduler.get_jobs():
            jobs_info.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time,
                'trigger': str(job.trigger)
            })
        return jobs_info