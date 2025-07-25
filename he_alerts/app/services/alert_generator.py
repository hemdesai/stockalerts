"""
Alert generation service that checks for price triggers and generates alerts.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.core.logging import get_logger
from app.models.stock import Stock

logger = get_logger(__name__)


class AlertGenerator:
    """
    Generate alerts based on current prices and thresholds.
    """
    
    def __init__(self):
        pass
    
    async def check_alerts(
        self, 
        db: AsyncSession,
        session: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Check all active stocks for alert conditions.
        
        Args:
            db: Database session
            session: Trading session (AM/PM) or None for auto-detect
            
        Returns:
            List of triggered alerts
        """
        if not session:
            session = self._get_current_session()
        
        logger.info(f"Checking alerts for {session} session")
        
        # Get stocks with prices for the current session
        stocks = await self._get_stocks_with_prices(db, session)
        
        alerts = []
        for stock in stocks:
            stock_alerts = self._check_stock_alerts(stock, session)
            alerts.extend(stock_alerts)
        
        logger.info(f"Found {len(alerts)} alerts for {len(stocks)} stocks")
        return alerts
    
    async def _get_stocks_with_prices(
        self, 
        db: AsyncSession, 
        session: str
    ) -> List[Stock]:
        """
        Get stocks that have prices for the given session.
        
        Args:
            db: Database session
            session: AM or PM
            
        Returns:
            List of stocks with prices
        """
        price_field = Stock.am_price if session == 'AM' else Stock.pm_price
        
        query = select(Stock).where(
            and_(
                Stock.is_active == True,
                price_field != None,
                Stock.sentiment.in_(['bullish', 'bearish'])
            )
        )
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    def _check_stock_alerts(
        self, 
        stock: Stock, 
        session: str
    ) -> List[Dict[str, Any]]:
        """
        Check if a stock triggers any alerts.
        
        Args:
            stock: Stock instance
            session: AM or PM
            
        Returns:
            List of triggered alerts for this stock
        """
        alerts = []
        current_price = stock.am_price if session == 'AM' else stock.pm_price
        
        if not current_price:
            return alerts
        
        sentiment = stock.sentiment.lower()
        
        # BULLISH: BUY if price <= buy_trade, SELL if price >= sell_trade
        if sentiment == 'bullish':
            if stock.buy_trade and current_price <= stock.buy_trade:
                alerts.append({
                    'ticker': stock.ticker,
                    'name': stock.name,
                    'sentiment': stock.sentiment,
                    'current_price': current_price,
                    'buy_trade': stock.buy_trade,
                    'sell_trade': stock.sell_trade,
                    'category': stock.category,
                    'type': 'BUY',
                    'session': session,
                    'threshold': stock.buy_trade,
                    'price': current_price
                })
            
            if stock.sell_trade and current_price >= stock.sell_trade:
                alerts.append({
                    'ticker': stock.ticker,
                    'name': stock.name,
                    'sentiment': stock.sentiment,
                    'current_price': current_price,
                    'buy_trade': stock.buy_trade,
                    'sell_trade': stock.sell_trade,
                    'category': stock.category,
                    'type': 'SELL',
                    'session': session,
                    'threshold': stock.sell_trade,
                    'price': current_price
                })
        
        # BEARISH: SHORT if price >= sell_trade, COVER if price <= buy_trade
        elif sentiment == 'bearish':
            if stock.sell_trade and current_price >= stock.sell_trade:
                alerts.append({
                    'ticker': stock.ticker,
                    'name': stock.name,
                    'sentiment': stock.sentiment,
                    'current_price': current_price,
                    'buy_trade': stock.buy_trade,
                    'sell_trade': stock.sell_trade,
                    'category': stock.category,
                    'type': 'SHORT',
                    'session': session,
                    'threshold': stock.sell_trade,
                    'price': current_price
                })
            
            if stock.buy_trade and current_price <= stock.buy_trade:
                alerts.append({
                    'ticker': stock.ticker,
                    'name': stock.name,
                    'sentiment': stock.sentiment,
                    'current_price': current_price,
                    'buy_trade': stock.buy_trade,
                    'sell_trade': stock.sell_trade,
                    'category': stock.category,
                    'type': 'COVER',
                    'session': session,
                    'threshold': stock.buy_trade,
                    'price': current_price
                })
        
        return alerts
    
    def _get_current_session(self) -> str:
        """
        Determine current trading session based on Eastern Time.
        
        Returns:
            'AM' or 'PM'
        """
        from pytz import timezone
        eastern = timezone('America/New_York')
        now = datetime.now(eastern)
        return 'AM' if now.hour < 12 else 'PM'
    
    async def generate_and_store_alerts(
        self, 
        db: AsyncSession,
        session: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate alerts and store them in the database.
        
        Args:
            db: Database session
            session: Trading session or None for auto-detect
            
        Returns:
            Result dictionary with alert count and status
        """
        try:
            # Check for alerts
            alerts = await self.check_alerts(db, session)
            
            if not alerts:
                return {
                    'success': True,
                    'message': 'No alerts triggered',
                    'alert_count': 0,
                    'session': session or self._get_current_session()
                }
            
            # Skip storing alerts - we don't need logging
            
            # Group alerts by type for summary
            alert_summary = {}
            for alert in alerts:
                alert_type = alert['type']
                if alert_type not in alert_summary:
                    alert_summary[alert_type] = []
                alert_summary[alert_type].append(alert['ticker'])
            
            return {
                'success': True,
                'message': f'Generated {len(alerts)} alerts',
                'alert_count': len(alerts),
                'session': session or self._get_current_session(),
                'alerts': alerts,
                'summary': alert_summary
            }
            
        except Exception as e:
            logger.error(f"Error generating alerts: {e}")
            return {
                'success': False,
                'message': f'Error generating alerts: {str(e)}',
                'alert_count': 0,
                'session': session or self._get_current_session()
            }
    
    def format_alert_html(
        self, 
        alerts: List[Dict[str, Any]], 
        session: str
    ) -> str:
        """
        Format alerts as HTML for email.
        
        Args:
            alerts: List of alert dictionaries
            session: Trading session
            
        Returns:
            HTML string
        """
        from pytz import timezone
        eastern = timezone('America/New_York')
        now = datetime.now(eastern)
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h2 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: center; }}
                th {{ background-color: #4CAF50; color: white; }}
                .bullish-row {{ background-color: #e8f5e9; }}
                .bearish-row {{ background-color: #ffebee; }}
                .buy-action {{ color: #2e7d32; font-weight: bold; }}
                .sell-action {{ color: #d32f2f; font-weight: bold; }}
                .short-action {{ color: #f57c00; font-weight: bold; }}
                .cover-action {{ color: #1976d2; font-weight: bold; }}
                .highlight {{ font-weight: bold; font-size: 1.1em; }}
                .footer {{ margin-top: 20px; font-size: 0.9em; color: #666; }}
            </style>
        </head>
        <body>
            <h2>HE Alerts - {session} Session</h2>
            <p><strong>Time:</strong> {now.strftime('%Y-%m-%d %H:%M:%S')} ET</p>
            <p><strong>Total Alerts:</strong> {len(alerts)}</p>
            
            <table>
                <tr>
                    <th>Ticker</th>
                    <th>Category</th>
                    <th>Sentiment</th>
                    <th>Action</th>
                    <th>Current Price</th>
                    <th>Buy Level</th>
                    <th>Sell Level</th>
                </tr>
        """
        
        for alert in alerts:
            sentiment = alert['sentiment'].lower()
            alert_type = alert['type']
            row_class = 'bullish-row' if sentiment == 'bullish' else 'bearish-row'
            action_class = f"{alert_type.lower()}-action"
            
            # Format prices
            current_price = f"${alert['current_price']:.2f}"
            buy_price = f"${alert['buy_trade']:.2f}" if alert['buy_trade'] else "-"
            sell_price = f"${alert['sell_trade']:.2f}" if alert['sell_trade'] else "-"
            
            # Highlight triggered threshold
            if alert_type in ('BUY', 'COVER'):
                buy_price = f'<span class="highlight">{buy_price}</span>'
                current_price = f'<span class="highlight">{current_price}</span>'
            elif alert_type in ('SELL', 'SHORT'):
                sell_price = f'<span class="highlight">{sell_price}</span>'
                current_price = f'<span class="highlight">{current_price}</span>'
            
            html += f"""
                <tr class="{row_class}">
                    <td><strong>{alert['ticker']}</strong></td>
                    <td>{alert['category'].upper()}</td>
                    <td>{alert['sentiment'].upper()}</td>
                    <td class="{action_class}">{alert_type}</td>
                    <td>{current_price}</td>
                    <td>{buy_price}</td>
                    <td>{sell_price}</td>
                </tr>
            """
        
        html += """
            </table>
            
            <div class="footer">
                <p><strong>Alert Logic:</strong></p>
                <ul>
                    <li>BULLISH: BUY when price ≤ buy level, SELL when price ≥ sell level</li>
                    <li>BEARISH: SHORT when price ≥ sell level, COVER when price ≤ buy level</li>
                </ul>
                <p>Generated by HE Alerts System</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def format_alert_summary(self, alerts: List[Dict[str, Any]]) -> str:
        """
        Format a brief text summary of alerts.
        
        Args:
            alerts: List of alert dictionaries
            
        Returns:
            Text summary
        """
        if not alerts:
            return "No alerts triggered"
        
        summary_lines = []
        
        # Group by action type
        actions = {}
        for alert in alerts:
            action = alert['type']
            if action not in actions:
                actions[action] = []
            actions[action].append(f"{alert['ticker']} (${alert['current_price']:.2f})")
        
        # Format summary
        for action, tickers in actions.items():
            summary_lines.append(f"{action}: {', '.join(tickers)}")
        
        return "\n".join(summary_lines)