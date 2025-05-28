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

from stockalert.utils.env_loader import load_environment, get_env

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
        if sentiment not in ("BULLISH", "BEARISH"):
            continue  # Ignore NEUTRAL and any other values
        # Ensure price and thresholds are not None
        if price is None:
            continue
        # BULLISH: BUY if price <= buy_trade, SELL if price >= sell_trade
        if sentiment == "BULLISH":
            if buy_trade is not None and price <= buy_trade:
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
            if sell_trade is not None and price >= sell_trade:
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
        # BEARISH: SHORT if price >= sell_trade, COVER if price <= buy_trade
        elif sentiment == "BEARISH":
            if sell_trade is not None and price >= sell_trade:
                alerts.append({
                    'ticker': ticker,
                    'name': name,
                    'sentiment': sentiment,
                    'current_price': price,
                    'buy_trade': buy_trade,
                    'sell_trade': sell_trade,
                    'category': category,
                    'type': 'SHORT',
                    'session': session
                })
            if buy_trade is not None and price <= buy_trade:
                alerts.append({
                    'ticker': ticker,
                    'name': name,
                    'sentiment': sentiment,
                    'current_price': price,
                    'buy_trade': buy_trade,
                    'sell_trade': sell_trade,
                    'category': category,
                    'type': 'COVER',
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
            .bullish-row {{ background-color: #e0ffe0 !important; }}
            .bearish-row {{ background-color: #ffe0e0 !important; }}
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
        sentiment = alert['sentiment']
        alert_type = alert['type']
        row_class = 'bullish-row' if sentiment == 'BULLISH' else 'bearish-row'
        # Determine which numbers to bold
        bold_buy = bold_sell = bold_price = False
        if alert_type in ('BUY', 'COVER'):
            bold_price = True
            bold_buy = True
        elif alert_type in ('SELL', 'SHORT'):
            bold_price = True
            bold_sell = True
        price_html = f"<b>${alert['current_price']:.2f}</b>" if bold_price else f"${alert['current_price']:.2f}"
        buy_html = f"<b>{alert['buy_trade']}</b>" if bold_buy and alert['buy_trade'] is not None else (alert['buy_trade'] if alert['buy_trade'] is not None else '')
        sell_html = f"<b>{alert['sell_trade']}</b>" if bold_sell and alert['sell_trade'] is not None else (alert['sell_trade'] if alert['sell_trade'] is not None else '')
        html += f"""
            <tr class='{row_class}'>
                <td><b>{alert['ticker']}</b></td>
                <td>{alert['name']}</td>
                <td>{alert['sentiment']}</td>
                <td>{price_html}</td>
                <td>{buy_html}</td>
                <td>{sell_html}</td>
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
    
    # Define primary recipient and BCC recipients
    primary_recipient = get_env('EMAIL_RECIPIENT', 'hemdesai@gmail.com')  # Primary recipient from env
    
    # Define BCC recipients
    bcc_recipients = [
        'parekhp@yahoo.com',  # Pranay
        'kuntalgandhi@hotmail.com',   # Kuntal
    ]
    bcc_str = ','.join(bcc_recipients)  # Join with commas for SMTP format
    
    # Send email with primary recipient and BCCs
    success = mcp_client.send_email(subject, html, primary_recipient, bcc=bcc_str)
    if success:
        logger.info(f"Alert email sent successfully to multiple recipients: {subject}")
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
