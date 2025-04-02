#!/usr/bin/env python
"""
Unified price update script for stock alert system
Updates AM or PM prices based on session and triggers alerts
"""
import os, sys, sqlite3, logging, time, random, subprocess
from pathlib import Path
from datetime import datetime
import pytz
import yfinance as yf
from tqdm import tqdm
import argparse

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

def update_price(ticker, session, max_retries=3):
    """Update price for a specific ticker and session with retry for rate limiting."""
    for attempt in range(max_retries):
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info

            # Determine company name and price using fallbacks.
            name = info.get('shortName', ticker)
            if session == 'AM':
                price = (info.get('regularMarketPrice') or
                         info.get('currentPrice') or
                         info.get('regularMarketOpen'))
            else:  # PM session
                price = (info.get('regularMarketPreviousClose') or
                         info.get('previousClose'))
            if price is None:
                logger.warning(f"No price found for {ticker} ({name})")
                return None, name
            logger.info(f"Updated {name} ({ticker}) {session} price to {price}")
            return price, name

        except Exception as e:
            if "Too Many Requests" in str(e) or "Rate limited" in str(e):
                wait_time = 5 * (2 ** attempt)
                logger.warning(f"Rate limit hit for {ticker}, retrying in {wait_time} seconds (attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
            else:
                logger.error(f"Error updating {ticker}: {e}")
                break
    return None, ticker

def update_prices(conn, cursor, session):
    """Update prices from yfinance for the specified session."""
    logger.info(f"Updating {session} prices...")
    ny_tz = pytz.timezone('America/New_York')
    eastern_time = datetime.now(ny_tz).strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("SELECT ticker FROM stocks")
    tickers = [row[0] for row in cursor.fetchall()]
    if not tickers:
        logger.warning("No tickers found in the database")
        return

    batch_size = 5
    ticker_batches = [tickers[i:i+batch_size] for i in range(0, len(tickers), batch_size)]
    total_updated = 0

    for batch_idx, batch in enumerate(ticker_batches):
        logger.info(f"Processing batch {batch_idx+1}/{len(ticker_batches)} with {len(batch)} tickers")
        for ticker in batch:
            price, _ = update_price(ticker, session)
            if price is not None:
                cursor.execute(
                    f"UPDATE stocks SET {session}_Price = ?, Last_Price_Update = ? WHERE ticker = ?",
                    (price, eastern_time, ticker)
                )
                logger.info(f"Database updated for {ticker} in {session} session")
                total_updated += 1
                time.sleep(random.uniform(3, 5))
        conn.commit()
        if batch_idx < len(ticker_batches) - 1:
            delay = random.uniform(10, 15)
            logger.info(f"Waiting {delay:.1f} seconds before next batch...")
            time.sleep(delay)
    logger.info(f"Updated {session}_Price for {total_updated} tickers")
    return total_updated

def force_price_update(session, update_names=False, run_alerts=True, should_update_prices=True):
    """Force price update and alert generation."""
    load_environment()
    db_path = os.path.join(project_root, "stockalert", "data", "stocks.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT ticker FROM stocks")
    tickers = [row[0] for row in cursor.fetchall()]
    if not tickers:
        logger.warning("No tickers found in the database")
        return

    sample_tickers = tickers[:5]
    price_column = f"{session}_Price"
    logger.info(f"Sample current {price_column} values:")
    for ticker in sample_tickers:
        cursor.execute(f"SELECT ticker, {price_column}, Last_Price_Update FROM stocks WHERE ticker = ?", (ticker,))
        result = cursor.fetchone()
        if result:
            logger.info(f"Before update - {result[0]}: {price_column} = {result[1]}, Last_Update = {result[2]}")

    if update_names:
        logger.info("Updating ticker names...")
        batch_size = 3
        ticker_batches = [tickers[i:i+batch_size] for i in range(0, len(tickers), batch_size)]
        total_updated = 0
        for batch_idx, batch in enumerate(ticker_batches):
            logger.info(f"Processing name update batch {batch_idx+1}/{len(ticker_batches)} with {len(batch)} tickers")
            for ticker in batch:
                for retry in range(3):
                    try:
                        info = yf.Ticker(ticker).info
                        name = info.get('longName', info.get('shortName', ticker))
                        cursor.execute("UPDATE stocks SET name = ? WHERE ticker = ?", (name, ticker))
                        logger.info(f"Updated name for {ticker}: {name}")
                        total_updated += 1
                        time.sleep(random.uniform(3, 5))
                        break
                    except Exception as e:
                        if "Rate limited" in str(e) and retry < 2:
                            wait_time = 5 * (2 ** retry)
                            logger.warning(f"Rate limit for {ticker}, retrying in {wait_time} seconds (attempt {retry+1}/3)")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"Error updating name for {ticker}: {e}")
                            break
            conn.commit()
            if batch_idx < len(ticker_batches) - 1:
                delay = random.uniform(20, 30)
                logger.info(f"Waiting {delay:.1f} seconds before next name update batch...")
                time.sleep(delay)
        logger.info(f"Updated names for {total_updated} tickers")

    if should_update_prices:
        update_prices(conn, cursor, session)
        logger.info(f"Sample updated {price_column} values:")
        for ticker in sample_tickers:
            cursor.execute(f"SELECT ticker, {price_column}, Last_Price_Update FROM stocks WHERE ticker = ?", (ticker,))
            result = cursor.fetchone()
            if result:
                logger.info(f"After update - {result[0]}: {price_column} = {result[1]}, Last_Update = {result[2]}")

    conn.close()

    if run_alerts:
        logger.info("Running alert system...")
        try:
            subprocess.run([sys.executable, "-m", "stockalert.scripts.alert_system"], check=True)
            logger.info("Alert system completed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running alert system: {e}")
        except Exception as e:
            logger.error(f"Unexpected error running alert system: {e}")

def get_current_session():
    """Auto-detect session based on Eastern time."""
    eastern = pytz.timezone('America/New_York')
    current_hour = datetime.now(eastern).hour
    return 'AM' if current_hour < 12 else 'PM'

def main():
    parser = argparse.ArgumentParser(description='Force price update and alert generation')
    parser.add_argument('--session', choices=['AM', 'PM'], help='Session to update (AM or PM). Auto-detect if not specified')
    parser.add_argument('--update-names', action='store_true', help='Update ticker names (typically for AM session)')
    parser.add_argument('--no-alerts', action='store_true', help='Skip running alerts after price update')
    parser.add_argument('--skip-name-updates', action='store_true', help='Skip name updates even if --update-names specified')
    parser.add_argument('--skip-price-updates', action='store_true', help='Skip price updates and only run alerts')
    args = parser.parse_args()

    session = args.session if args.session else get_current_session()
    logger.info(f"Using {session} session")
    update_names = args.update_names and not args.skip_name_updates
    if args.skip_name_updates:
        logger.info("Name updates skipped as requested")
    should_update_prices = not args.skip_price_updates
    if args.skip_price_updates:
        logger.info("Price updates skipped as requested")
    run_alerts = not args.no_alerts

    force_price_update(session, update_names, run_alerts, should_update_prices)

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