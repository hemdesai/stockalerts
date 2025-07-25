"""
Production-ready alert workflow runner.
This script is designed to be run by a scheduler (cron, Windows Task Scheduler, etc.)
"""
import asyncio
import sys
import argparse
from datetime import datetime
import pytz
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from alert_workflow import AlertWorkflow
from app.core.logging import get_logger

logger = get_logger(__name__)


async def run_production_workflow(force_session: str = None, dry_run: bool = False):
    """
    Run the complete production workflow.
    
    Args:
        force_session: Force a specific session (AM/PM) instead of auto-detect
        dry_run: If True, test mode without sending emails
    """
    eastern = pytz.timezone('America/New_York')
    now = datetime.now(eastern)
    
    # Auto-detect session if not forced
    if force_session:
        session = force_session
    else:
        hour = now.hour
        if 9 <= hour < 12:
            session = 'AM'
        elif 13 <= hour < 16:
            session = 'PM'
        else:
            logger.info(f"Current time {now.strftime('%H:%M')} ET is outside trading hours. No alerts to generate.")
            return
    
    logger.info(f"{'='*80}")
    logger.info(f"Starting HE Alerts Workflow - {session} Session")
    logger.info(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')} ET")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'PRODUCTION'}")
    logger.info(f"{'='*80}")
    
    workflow = AlertWorkflow()
    
    try:
        # Run complete workflow
        results = await workflow.run_complete_workflow(
            session=session,
            skip_price_fetch=False,  # Always fetch fresh prices
            send_email=not dry_run,  # Send email unless in dry run mode
            test_mode=False          # Production mode - save to DB
        )
        
        # Log results
        if results.get('success'):
            logger.info("Workflow completed successfully")
            
            # Price fetch summary
            if results.get('price_fetch', {}).get('success'):
                pf = results['price_fetch']
                logger.info(f"Prices: {pf.get('stocks_checked', 0)} checked, {pf.get('prices_updated', 0)} updated")
            
            # Alert summary
            if results.get('alerts', {}).get('success'):
                ar = results['alerts']
                alert_count = ar.get('alert_count', 0)
                logger.info(f"Alerts: {alert_count} generated")
                
                if alert_count > 0:
                    # Log alert breakdown
                    if ar.get('summary'):
                        for action, tickers in ar['summary'].items():
                            logger.info(f"  {action}: {', '.join(tickers)}")
                    
                    # Email status
                    if results.get('email_sent'):
                        logger.info("Alert email sent successfully")
                    elif dry_run:
                        logger.info("Email sending skipped (dry run mode)")
                    else:
                        logger.warning("Failed to send alert email")
                else:
                    logger.info("No alerts triggered - all positions within thresholds")
            
            # Display full summary
            await workflow.display_workflow_summary(results)
            
        else:
            logger.error(f"Workflow failed: {results.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Critical error in workflow: {e}")
        raise


def main():
    """Main entry point with CLI arguments."""
    parser = argparse.ArgumentParser(
        description='HE Alerts Production Workflow Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run for current session (auto-detect AM/PM)
  python run_alert_workflow.py
  
  # Force AM session
  python run_alert_workflow.py --session AM
  
  # Dry run (no emails sent)
  python run_alert_workflow.py --dry-run
  
  # Force PM session in dry run mode
  python run_alert_workflow.py --session PM --dry-run

Scheduling:
  # Windows Task Scheduler (runs at 10:45 AM and 2:30 PM ET)
  schtasks /create /tn "HE_Alerts_AM" /tr "python C:\\code\\stockalert\\he_alerts\\run_alert_workflow.py" /sc daily /st 10:45
  schtasks /create /tn "HE_Alerts_PM" /tr "python C:\\code\\stockalert\\he_alerts\\run_alert_workflow.py" /sc daily /st 14:30
  
  # Linux/Mac cron (runs at 10:45 AM and 2:30 PM ET)
  45 10 * * * cd /path/to/he_alerts && python run_alert_workflow.py
  30 14 * * * cd /path/to/he_alerts && python run_alert_workflow.py
"""
    )
    
    parser.add_argument(
        '--session',
        choices=['AM', 'PM'],
        help='Force specific session instead of auto-detect'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test mode - generate alerts but do not send emails'
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run_production_workflow(
            force_session=args.session,
            dry_run=args.dry_run
        ))
    except KeyboardInterrupt:
        logger.info("Workflow interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()