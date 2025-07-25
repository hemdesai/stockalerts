"""
Generate and send stock alerts based on current prices.
"""
import asyncio
import argparse
from datetime import datetime
from typing import Optional

from app.core.database import AsyncSessionLocal
from app.services.alert_generator import AlertGenerator
from app.services.email_sender import EmailSender
from app.core.logging import get_logger

logger = get_logger(__name__)


async def generate_and_send_alerts(
    session: Optional[str] = None,
    send_email: bool = True,
    dry_run: bool = False
):
    """
    Generate alerts and optionally send email.
    
    Args:
        session: Trading session (AM/PM) or None for auto-detect
        send_email: Whether to send email
        dry_run: If True, generate alerts but don't store or send
    """
    alert_generator = AlertGenerator()
    email_sender = EmailSender()
    
    async with AsyncSessionLocal() as db:
        # Generate alerts
        result = await alert_generator.generate_and_store_alerts(db, session)
        
        if not result['success']:
            logger.error(f"Failed to generate alerts: {result['message']}")
            return
        
        logger.info(f"Alert generation complete: {result['message']}")
        
        if result['alert_count'] == 0:
            logger.info("No alerts to send")
            return
        
        # Display alerts
        alerts = result.get('alerts', [])
        print(f"\n{'='*60}")
        print(f"ALERTS GENERATED - {result['session']} Session")
        print(f"{'='*60}")
        print(f"Total alerts: {result['alert_count']}")
        
        # Show summary by type
        summary = result.get('summary', {})
        print("\nSummary by action:")
        for action, tickers in summary.items():
            print(f"  {action}: {', '.join(tickers)}")
        
        # Show detailed alerts
        print("\nDetailed alerts:")
        for alert in alerts:
            print(f"  {alert['ticker']} ({alert['category']}) - {alert['type']} at ${alert['current_price']:.2f}")
            print(f"    Sentiment: {alert['sentiment']}, Buy: ${alert['buy_trade']:.2f}, Sell: ${alert['sell_trade']:.2f}")
        
        if dry_run:
            print("\n[DRY RUN] Alerts generated but not stored or sent")
            return
        
        # Send email if requested
        if send_email and alerts:
            # Format email
            html_content = alert_generator.format_alert_html(alerts, result['session'])
            text_summary = alert_generator.format_alert_summary(alerts)
            
            # Create subject
            from pytz import timezone
            eastern = timezone('America/New_York')
            now = datetime.now(eastern)
            subject = f"HE Alerts - {result['session']} Session ({result['alert_count']} alerts) - {now.strftime('%Y-%m-%d %H:%M')} ET"
            
            # Send email
            success = await email_sender.send_alert_email(
                subject=subject,
                html_content=html_content,
                text_content=text_summary
            )
            
            if success:
                print(f"\n[OK] Alert email sent: {subject}")
            else:
                print("\n[ERROR] Failed to send alert email")
        elif not send_email:
            print("\n[INFO] Email sending skipped (--no-email flag)")


async def test_email():
    """Send a test email to verify configuration."""
    email_sender = EmailSender()
    success = await email_sender.send_test_email()
    
    if success:
        print("[OK] Test email sent successfully")
    else:
        print("[ERROR] Failed to send test email")


async def main():
    parser = argparse.ArgumentParser(description='Generate and send stock alerts')
    parser.add_argument(
        '--session', 
        choices=['AM', 'PM'], 
        help='Trading session (AM or PM); auto-detect if omitted'
    )
    parser.add_argument(
        '--no-email', 
        action='store_true',
        help='Generate alerts but do not send email'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Generate alerts but do not store in database or send email'
    )
    parser.add_argument(
        '--test-email',
        action='store_true',
        help='Send a test email to verify configuration'
    )
    
    args = parser.parse_args()
    
    if args.test_email:
        await test_email()
    else:
        await generate_and_send_alerts(
            session=args.session,
            send_email=not args.no_email,
            dry_run=args.dry_run
        )


if __name__ == "__main__":
    asyncio.run(main())