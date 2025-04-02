#!/usr/bin/env python
"""
Unified price update script for stock alert system.
Fetches same-day prices from yfinance and triggers alerts.
For PM sessions after 4PM Eastern, uses the closing price.
"""
import os, sys, sqlite3, logging, time, random, subprocess, argparse
from pathlib import Path
from datetime import datetime, time as dtime
import pytz
import yfinance as yf
import pandas as pd

from stockalert.utils.env_loader import load_environment

project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(project_root) / "data" / "price_update.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PriceUpdate")

def get_current_session():
    eastern = pytz.timezone('America/New_York')
    return 'AM' if datetime.now(eastern).hour < 12 else 'PM'

def update_names(cursor, tickers):
    """Update ticker names individually using yfinance info with retries."""
    total_updated = 0
    for ticker in tickers:
        for attempt in range(3):
            try:
                info = yf.Ticker(ticker).info
                name = info.get('longName', info.get('shortName', ticker))
                cursor.execute("UPDATE stocks SET name = ? WHERE ticker = ?", (name, ticker))
                logger.info(f"Updated name for {ticker}: {name}")
                total_updated += 1
                time.sleep(random.uniform(3, 5))
                break
            except Exception as e:
                if attempt < 2 and "Rate" in str(e):
                    wait = 5 * (2 ** attempt)
                    logger.warning(f"Rate limit for {ticker}, retrying in {wait} seconds (attempt {attempt+1}/3)")
                    time.sleep(wait)
                else:
                    logger.error(f"Error updating name for {ticker}: {e}")
                    break
    return total_updated

def update_prices(conn, cursor, tickers, session):
    """
    Batch download same-day price data using yfinance.
    Uses the latest available price:
      - For PM sessions after 4PM Eastern, this is the closing price.
      - Otherwise, uses the current/latest price.
    """
    logger.info(f"Batch updating prices for {len(tickers)} tickers in {session} session...")
    # Download one day's data for all tickers.
    # Use 0.5m interval for more frequent updates instea of 1m, which worked!
    data = yf.download(tickers, period="1d", interval="0.5m", progress=False, group_by='ticker')
    eastern = pytz.timezone('America/New_York')
    now = datetime.now(eastern)
    eastern_time = now.strftime("%Y-%m-%d %H:%M:%S")
    total_updated = 0

    for ticker in tickers:
        try:
            # When multiple tickers, data columns are MultiIndex.
            if isinstance(data.columns, pd.MultiIndex):
                df = data[ticker]
            else:
                df = data
            if df.empty:
                logger.warning(f"No data returned for {ticker}")
                continue

            # If PM session and after 4PM, use closing price; otherwise, use the latest price.
            if session == 'PM' and now.time() >= dtime(16, 0):
                price = df["Close"].iloc[-1]
            else:
                price = df["Close"].iloc[-1]
            cursor.execute(
                f"UPDATE stocks SET {session}_Price = ?, Last_Price_Update = ? WHERE ticker = ?",
                (price, eastern_time, ticker)
            )
            logger.info(f"{ticker} {session} price updated to {price}")
            total_updated += 1
        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
    conn.commit()
    logger.info(f"Updated prices for {total_updated} tickers in {session} session")
    return total_updated

def run_alerts():
    """Run the alert system via subprocess."""
    logger.info("Running alert system...")
    try:
        subprocess.run([sys.executable, "-m", "stockalert.scripts.alert_system"], check=True)
        logger.info("Alert system completed successfully")
    except Exception as e:
        logger.error(f"Error running alert system: {e}")

def force_price_update(session, update_names_flag=False, run_alerts_flag=True, update_prices_flag=True):
    load_environment()
    db_path = os.path.join(project_root, "stockalert", "data", "stocks.db")
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
        logger.info("Updating ticker names...")
        update_names(cursor, tickers)
        conn.commit()

    if update_prices_flag:
        update_prices(conn, cursor, tickers, session)
        logger.info(f"Sample updated {price_col} values:")
        for t in sample:
            cursor.execute(f"SELECT ticker, {price_col}, Last_Price_Update FROM stocks WHERE ticker = ?", (t,))
            res = cursor.fetchone()
            if res:
                logger.info(f"After update - {res[0]}: {price_col} = {res[1]}, Last_Update = {res[2]}")

    conn.close()

    if run_alerts_flag:
        run_alerts()

def main():
    parser = argparse.ArgumentParser(description='Force price update and alert generation')
    parser.add_argument('--session', choices=['AM', 'PM'], help='Session to update (AM or PM); auto-detect if omitted')
    parser.add_argument('--update-names', action='store_true', help='Update ticker names')
    parser.add_argument('--no-alerts', action='store_true', help='Skip running alerts')
    parser.add_argument('--skip-price-updates', action='store_true', help='Skip price updates and only run alerts')
    args = parser.parse_args()

    session = args.session if args.session else get_current_session()
    logger.info(f"Using {session} session")
    update_names_flag = args.update_names
    update_prices_flag = not args.skip_price_updates
    run_alerts_flag = not args.no_alerts

    force_price_update(session, update_names_flag, run_alerts_flag, update_prices_flag)

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