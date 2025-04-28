#!/usr/bin/env python
"""
Unified price update script for stock alert system.
Fetches same-day prices from yfinance and triggers alerts.
For PM sessions after 4PM Eastern, uses the closing price.
"""
import os, sys, sqlite3, logging, time, random, argparse
from pathlib import Path
# ensure project root on sys.path for imports
if str(Path(__file__).parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from datetime import datetime
import pytz
import random
import json

from stockalert.utils.env_loader import load_environment
# from yfmcp.server import get_ticker_info as yfmcp_get_ticker_info

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent.parent / "data" / "price_update.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PriceUpdate")

def get_current_session():
    eastern = pytz.timezone('America/New_York')
    return 'AM' if datetime.now(eastern).hour < 12 else 'PM'



def run_alerts():
    """Run the alert system via subprocess."""
    logger.info("Running alert system...")
    try:
        subprocess.run([sys.executable, "-m", "stockalert.scripts.alert_system"], check=True)
        logger.info("Alert system completed successfully")
    except Exception as e:
        logger.error(f"Error running alert system: {e}")

def force_price_update(session, update_names_flag=False, run_alerts_flag=True, update_prices_flag=True, use_ibkr=False):
    """
    Unified price update function. If use_ibkr is True, use IBKR for price fetching instead of yfinance.
    """
    load_environment()
    db_path = os.path.join(str(Path(__file__).parent.parent.parent), "stockalert", "data", "stocks.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT ticker FROM stocks")
    tickers = [row[0] for row in cursor.fetchall()]
    if not tickers:
        logger.warning("No tickers found in the database")
        conn.close()
        return

    sample = tickers[:5]
    price_col = f"{session}_Price"
    logger.info(f"Sample current {price_col} values:")
    for t in sample:
        cursor.execute(f"SELECT ticker, {price_col}, Last_Price_Update FROM stocks WHERE ticker = ?", (t,))
        res = cursor.fetchone()
        if res:
            logger.info(f"Before update - {res[0]}: {price_col} = {res[1]}, Last_Update = {res[2]}")

    if update_names_flag:
        logger.info("Ticker name updates via yfinance are deprecated and have been disabled.")

    if update_prices_flag:
        logger.info("Using IBKR for price updates...")
        from stockalert.scripts import ibkr_price_update
        ibkr_price_update.run_ibkr_price_update(session)

    conn.close()

    if run_alerts_flag:
        run_alerts()

def main():
    parser = argparse.ArgumentParser(description='Force price update and alert generation')
    parser.add_argument('--session', choices=['AM', 'PM'], help='Session to update (AM or PM); auto-detect if omitted')
    parser.add_argument('--update-names', action='store_true', help='Update ticker names')
    parser.add_argument('--no-alerts', action='store_true', help='Skip running alerts')
    parser.add_argument('--skip-price-updates', action='store_true', help='Skip price updates and only run alerts')
    parser.add_argument('--use-ibkr', action='store_true', help='Use IBKR API for price updates instead of yfinance')
    args = parser.parse_args()

    session = args.session if args.session else get_current_session()
    logger.info(f"Using {session} session")
    update_names_flag = args.update_names
    update_prices_flag = not args.skip_price_updates
    run_alerts_flag = not args.no_alerts
    use_ibkr = args.use_ibkr

    force_price_update(session, update_names_flag, run_alerts_flag, update_prices_flag, use_ibkr=use_ibkr)

if __name__ == "__main__":
    load_environment()
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Script interrupted by user. Exiting gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        sys.exit(1)