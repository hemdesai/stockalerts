"""
4_send_alerts.py

Generates trade alerts based on cached IBKR prices in the database and sends them via Gmail using the MCP server.
No price fetching is performed here; prices must already be updated in the stocks.db by ibkr_price_update_async.py.
"""
import os
import sys
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
import pytz
import json

# Ensure project root is on sys.path for imports
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from stockalert.utils.env_loader import load_environment

# MCP client for sending emails
from stockalert.scripts.mcp_client import MCPClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(project_root) / "logs" / "send_alerts.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("SendAlerts")

DB_PATH = Path(project_root) / "stockalert" / "data" / "stocks.db"


def get_current_session():
    eastern = pytz.timezone('America/New_York')
    return 'AM' if datetime.now(eastern).hour < 12 else 'PM'


def fetch_alerts_from_db(session):
    """Fetch tickers with triggered alerts from the database for the given session."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    alerts = []
    # Fetch all relevant fields for alerting
    cursor.execute(f"""
        SELECT ticker, name, sentiment, {session}_Price, buy_trade, sell_trade, category
        FROM stocks
        WHERE {session}_Price IS NOT NULL
    """)
    rows = cursor.fetchall()
    for row in rows:
        ticker, name, sentiment, price, buy_trade, sell_trade, category = row
        # Alert logic: Buy if price <= buy_trade, Sell if price >= sell_trade
        if buy_trade is not None and price is not None and price <= buy_trade:
            alerts.append({
                'ticker': ticker,
                'name': name,
                'sentiment': sentiment,
                'current_price': price,
                'buy_trade': buy_trade,
                'sell_trade': sell_trade,
                'category': category,
                'type': 'BUY',
                'session': session
            })
        if sell_trade is not None and price is not None and price >= sell_trade:
            alerts.append({
                'ticker': ticker,
                'name': name,
                'sentiment': sentiment,
                'current_price': price,
                'buy_trade': buy_trade,
                'sell_trade': sell_trade,
                'category': category,
                'type': 'SELL',
                'session': session
            })
    conn.close()
    return alerts


def format_alert_email(alerts, session):
    if not alerts:
        return None, None
    eastern = pytz.timezone('America/New_York')
    now = datetime.now(eastern)
    subject = f"Stock Alerts - {session} Session ({len(alerts)} alerts) - {now.strftime('%Y-%m-%d %H:%M')} ET"
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
            th {{ background-color: #f2f2f2; }}
            .buy {{ background-color: #e0ffe0; }}
            .sell {{ background-color: #ffe0e0; }}
        </style>
    </head>
    <body>
        <h2>{len(alerts)} Stock Alerts - {session} Session</h2>
        <table>
            <tr>
                <th>Ticker</th>
                <th>Name</th>
                <th>Sentiment</th>
                <th>Current Price</th>
                <th>Buy Threshold</th>
                <th>Sell Threshold</th>
                <th>Category</th>
                <th>Type</th>
            </tr>
    """
    for alert in alerts:
        row_class = 'buy' if alert['type'] == 'BUY' else 'sell'
        html += f"""
            <tr class='{row_class}'>
                <td><b>{alert['ticker']}</b></td>
                <td>{alert['name']}</td>
                <td>{alert['sentiment']}</td>
                <td>${alert['current_price']:.2f}</td>
                <td>{alert['buy_trade'] if alert['buy_trade'] is not None else ''}</td>
                <td>{alert['sell_trade'] if alert['sell_trade'] is not None else ''}</td>
                <td>{alert['category']}</td>
                <td>{alert['type']}</td>
            </tr>
        """
    html += """
        </table>
    </body>
    </html>
    """
    return subject, html


def send_alerts(session=None):
    load_environment()
    session = session or get_current_session()
    logger.info(f"Generating alerts for {session} session...")
    alerts = fetch_alerts_from_db(session)
    if not alerts:
        logger.info("No alerts to send.")
        return False
    subject, html = format_alert_email(alerts, session)
    if not subject or not html:
        logger.warning("Failed to format alert email.")
        return False
    # Send via MCP
    mcp_client = MCPClient()
    if not mcp_client.connected:
        logger.error("MCP server is not connected. Cannot send alerts.")
        return False
    success = mcp_client.send_email(subject, html)
    if success:
        logger.info(f"Alert email sent successfully: {subject}")
    else:
        logger.error("Failed to send alert email via MCP server.")
    return success


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate and send stock alerts based on cached IBKR prices.')
    parser.add_argument('--session', choices=['AM', 'PM'], help='Session to use for alerting (AM or PM); auto-detect if omitted')
    args = parser.parse_args()
    send_alerts(args.session)

if __name__ == "__main__":
    main()
