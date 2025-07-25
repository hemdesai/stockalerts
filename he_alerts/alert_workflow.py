"""
Complete alert workflow: Fetch IBKR prices, generate alerts, and send email.
"""
import asyncio
import argparse
from datetime import datetime
from typing import Optional, List, Dict, Any
import pytz

from app.core.database import AsyncSessionLocal
from app.services.ibkr.price_fetcher import PriceFetcher
from app.services.alert_generator import AlertGenerator
from app.services.email_sender import EmailSender
from app.core.logging import get_logger

logger = get_logger(__name__)


class AlertWorkflow:
    """Complete alert workflow orchestrator."""
    
    def __init__(self):
        self.price_fetcher = PriceFetcher()
        self.alert_generator = AlertGenerator()
        self.email_sender = EmailSender()
        self.eastern = pytz.timezone('America/New_York')
    
    async def run_complete_workflow(
        self, 
        session: Optional[str] = None,
        skip_price_fetch: bool = False,
        send_email: bool = True,
        test_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Run the complete alert workflow.
        
        Args:
            session: Trading session (AM/PM) or None for auto-detect
            skip_price_fetch: Skip IBKR price fetching
            send_email: Whether to send alert email
            test_mode: Test mode (don't save to DB)
            
        Returns:
            Workflow result
        """
        if not session:
            session = self._get_current_session()
        
        logger.info(f"Starting alert workflow for {session} session")
        
        results = {
            'session': session,
            'timestamp': datetime.now(self.eastern).isoformat(),
            'price_fetch': None,
            'alerts': None,
            'email_sent': False
        }
        
        try:
            # Step 1: Fetch IBKR prices
            if not skip_price_fetch:
                logger.info("Step 1: Fetching IBKR prices...")
                price_result = await self._fetch_prices(session)
                results['price_fetch'] = price_result
                
                if not price_result['success']:
                    logger.error(f"Price fetch failed: {price_result['message']}")
                    return results
            else:
                logger.info("Step 1: Skipping price fetch (using existing prices)")
                results['price_fetch'] = {'skipped': True}
            
            # Step 2: Generate alerts
            logger.info("Step 2: Generating alerts...")
            alert_result = await self._generate_alerts(session, test_mode)
            results['alerts'] = alert_result
            
            if not alert_result['success']:
                logger.error(f"Alert generation failed: {alert_result['message']}")
                return results
            
            # Step 3: Send alert email (if alerts exist)
            if alert_result['alert_count'] > 0 and send_email:
                logger.info("Step 3: Sending alert email...")
                email_result = await self._send_alert_email(alert_result, session)
                results['email_sent'] = email_result
            else:
                logger.info("Step 3: No alerts to send or email disabled")
            
            results['success'] = True
            return results
            
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            results['success'] = False
            results['error'] = str(e)
            return results
    
    async def _fetch_prices(self, session: str) -> Dict[str, Any]:
        """Fetch prices from IBKR."""
        try:
            # Connect to IBKR
            await self.price_fetcher.connect()
            
            async with AsyncSessionLocal() as db:
                # Fetch and update prices
                result = await self.price_fetcher.update_stock_prices(db, session)
                
                # Format response
                return {
                    'success': result.get('success', False),
                    'message': result.get('message', ''),
                    'stocks_checked': result.get('total_stocks', 0),
                    'prices_updated': result.get('updated_count', 0),
                    'error_count': result.get('error_count', 0)
                }
        except Exception as e:
            logger.error(f"Price fetch error: {e}")
            return {
                'success': False,
                'message': str(e),
                'stocks_checked': 0,
                'prices_updated': 0,
                'error_count': 0
            }
        finally:
            # Always disconnect
            await self.price_fetcher.disconnect()
    
    async def _generate_alerts(self, session: str, test_mode: bool) -> Dict[str, Any]:
        """Generate alerts based on current prices."""
        async with AsyncSessionLocal() as db:
            if test_mode:
                # Just check alerts without storing
                alerts = await self.alert_generator.check_alerts(db, session)
                return {
                    'success': True,
                    'alert_count': len(alerts),
                    'alerts': alerts,
                    'session': session
                }
            else:
                # Generate and store alerts
                return await self.alert_generator.generate_and_store_alerts(db, session)
    
    async def _send_alert_email(self, alert_result: Dict[str, Any], session: str) -> bool:
        """Send alert email."""
        try:
            alerts = alert_result.get('alerts', [])
            
            # Format email
            html_content = self.alert_generator.format_alert_html(alerts, session)
            text_summary = self.alert_generator.format_alert_summary(alerts)
            
            # Create subject
            now = datetime.now(self.eastern)
            subject = f"HE Alerts - {session} Session ({alert_result['alert_count']} alerts) - {now.strftime('%Y-%m-%d %H:%M')} ET"
            
            # Send email
            return await self.email_sender.send_alert_email(
                subject=subject,
                html_content=html_content,
                text_content=text_summary
            )
            
        except Exception as e:
            logger.error(f"Error sending alert email: {e}")
            return False
    
    def _get_current_session(self) -> str:
        """Determine current trading session."""
        now = datetime.now(self.eastern)
        return 'AM' if now.hour < 12 else 'PM'
    
    async def display_workflow_summary(self, results: Dict[str, Any]):
        """Display a summary of the workflow results."""
        print("\n" + "="*80)
        print("ALERT WORKFLOW SUMMARY")
        print("="*80)
        print(f"Session: {results['session']}")
        print(f"Timestamp: {results['timestamp']}")
        
        # Price fetch summary
        if results['price_fetch']:
            if results['price_fetch'].get('skipped'):
                print("\nPrice Fetch: SKIPPED")
            else:
                pf = results['price_fetch']
                print(f"\nPrice Fetch: {'SUCCESS' if pf.get('success') else 'FAILED'}")
                if pf.get('success'):
                    print(f"  Stocks checked: {pf.get('stocks_checked', 0)}")
                    print(f"  Prices updated: {pf.get('prices_updated', 0)}")
                    print(f"  Errors: {pf.get('error_count', 0)}")
        
        # Alert summary
        if results['alerts']:
            ar = results['alerts']
            print(f"\nAlert Generation: {'SUCCESS' if ar.get('success') else 'FAILED'}")
            if ar.get('success'):
                print(f"  Alerts generated: {ar.get('alert_count', 0)}")
                
                # Show alert breakdown
                if ar.get('summary'):
                    print("  Alert types:")
                    for action, tickers in ar['summary'].items():
                        print(f"    {action}: {', '.join(tickers)}")
        
        # Email summary
        print(f"\nEmail Sent: {'YES' if results.get('email_sent') else 'NO'}")
        
        print("\n" + "="*80)


async def main():
    """Main function with CLI interface."""
    parser = argparse.ArgumentParser(description='HE Alerts Workflow')
    parser.add_argument(
        '--session', 
        choices=['AM', 'PM'], 
        help='Trading session (AM or PM); auto-detect if omitted'
    )
    parser.add_argument(
        '--skip-prices',
        action='store_true',
        help='Skip IBKR price fetching (use existing prices)'
    )
    parser.add_argument(
        '--no-email',
        action='store_true',
        help='Generate alerts but do not send email'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode (no database updates)'
    )
    parser.add_argument(
        '--check-prices',
        action='store_true',
        help='Only check current prices and potential alerts'
    )
    
    args = parser.parse_args()
    
    workflow = AlertWorkflow()
    
    if args.check_prices:
        # Just show current prices and potential alerts
        await check_prices_and_alerts(args.session)
    else:
        # Run full workflow
        results = await workflow.run_complete_workflow(
            session=args.session,
            skip_price_fetch=args.skip_prices,
            send_email=not args.no_email,
            test_mode=args.test
        )
        
        # Display summary
        await workflow.display_workflow_summary(results)


async def check_prices_and_alerts(session: Optional[str] = None):
    """Check current prices and show potential alerts."""
    from app.services.database.stock_service import StockService
    
    if not session:
        eastern = pytz.timezone('America/New_York')
        now = datetime.now(eastern)
        session = 'AM' if now.hour < 12 else 'PM'
    
    async with AsyncSessionLocal() as db:
        stock_service = StockService()
        alert_generator = AlertGenerator()
        
        # Get stocks with prices
        stocks = await alert_generator._get_stocks_with_prices(db, session)
        
        print(f"\nSTOCKS WITH {session} PRICES")
        print("="*80)
        print(f"{'Ticker':8} {'Category':15} {'Sentiment':10} {'Price':>10} {'Buy':>10} {'Sell':>10} {'Alert'}")
        print("-"*80)
        
        alert_count = 0
        for stock in sorted(stocks, key=lambda x: (x.category, x.ticker)):
            price = stock.am_price if session == 'AM' else stock.pm_price
            
            # Check for alerts
            alerts = alert_generator._check_stock_alerts(stock, session)
            alert_type = alerts[0]['type'] if alerts else ''
            
            if alerts:
                alert_count += 1
                # Highlight alert rows
                print(f"{stock.ticker:8} {stock.category:15} {stock.sentiment:10} "
                      f"${price:>9.2f} ${stock.buy_trade:>9.2f} ${stock.sell_trade:>9.2f} "
                      f"*** {alert_type} ***")
            else:
                print(f"{stock.ticker:8} {stock.category:15} {stock.sentiment:10} "
                      f"${price:>9.2f} ${stock.buy_trade:>9.2f} ${stock.sell_trade:>9.2f}")
        
        print(f"\nTotal stocks with prices: {len(stocks)}")
        print(f"Potential alerts: {alert_count}")


if __name__ == "__main__":
    asyncio.run(main())