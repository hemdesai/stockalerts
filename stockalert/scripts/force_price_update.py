#!/usr/bin/env python
"""
Unified price update script for stock alert system
Updates AM or PM prices based on session and triggers alerts
"""
import os
import sys
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
import pytz
import time
import random
import subprocess
import pandas as pd
import yfinance as yf
from tqdm import tqdm

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from stockalert.utils.env_loader import load_environment

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(project_root) / "data" / "price_update.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PriceUpdate")

def update_price(ticker, session):
    """Update price for a specific ticker and session"""
    try:
        # Get current price from Yahoo Finance
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        
        # Get the appropriate price based on session
        if session == 'AM':
            price = info.get('regularMarketPrice') or info.get('currentPrice')
        else:  # PM
            price = info.get('regularMarketPreviousClose')
        
        if price is None:
            logger.warning(f"No price found for {ticker} in {session} session")
            return False
            
        logger.info(f"Updated {ticker} {session} price to {price}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating price for {ticker}: {str(e)}")
        return False

def update_prices(conn, cursor, session):
    """Update prices from yfinance for the specified session"""
    logger.info(f"Updating {session} prices...")
    
    # Get current Eastern Time for timestamp
    ny_tz = pytz.timezone('America/New_York')
    eastern_time = datetime.now(ny_tz).strftime("%Y-%m-%d %H:%M:%S")
    
    # Get all tickers from the database
    cursor.execute("SELECT ticker FROM stocks")
    tickers = [row[0] for row in cursor.fetchall()]
    
    if not tickers:
        logger.error("No tickers found in database")
        return
    
    # Process tickers in batches to avoid rate limiting
    batch_size = 5
    ticker_batches = [tickers[i:i+batch_size] for i in range(0, len(tickers), batch_size)]
    
    total_updated = 0
    
    try:
        for batch_idx, batch in enumerate(ticker_batches):
            logger.info(f"Processing price update batch {batch_idx+1}/{len(ticker_batches)} ({len(batch)} tickers)")
            
            for ticker in batch:
                if update_price(ticker, session):
                    # Update price in database
                    cursor.execute(
                        f"UPDATE stocks SET {session}_Price = ?, Last_Price_Update = ? WHERE ticker = ?",
                        (yf.Ticker(ticker).info.get('currentPrice'), eastern_time, ticker)
                    )
                    
                    logger.info(f"Updated {session}_Price for {ticker}")
                    total_updated += 1
                    
                    # Longer delay between individual ticker requests
                    time.sleep(random.uniform(3, 5))
            
            # Commit changes after each batch
            conn.commit()
            
            # Add delay between batches to avoid rate limiting
            if batch_idx < len(ticker_batches) - 1:
                delay = random.uniform(10, 15)
                logger.info(f"Waiting {delay:.1f} seconds before next batch...")
                time.sleep(delay)
    
    except Exception as e:
        logger.error(f"Error updating prices: {e}")
        
    logger.info(f"Updated {session}_Price for {total_updated} tickers")
    return total_updated

def force_price_update(session=None, update_names=False, run_alerts=True, should_update_prices=True):
    """
    Force price update and alert generation
    
    Args:
        session (str): 'AM' or 'PM'. If None, auto-detect based on current time
        update_names (bool): Whether to update ticker names (default: False)
        run_alerts (bool): Whether to run alerts after updating prices (default: True)
        should_update_prices (bool): Whether to update prices (default: True)
    """
    # Load environment variables
    load_environment()
    
    # Get database path
    db_path = os.path.join(project_root, "stockalert", "data", "stocks.db")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tickers from the database
    cursor.execute("SELECT ticker FROM stocks")
    tickers = [row[0] for row in cursor.fetchall()]
    
    # Check current price values for a few tickers
    sample_tickers = []
    if tickers:
        sample_tickers = tickers[:5]  # Get first 5 tickers
        price_column = f"{session}_Price"
        logger.info(f"Current {price_column} values for sample tickers:")
        for ticker in sample_tickers:
            cursor.execute(f"SELECT ticker, {price_column}, Last_Price_Update FROM stocks WHERE ticker = ?", (ticker,))
            result = cursor.fetchone()
            if result:
                ticker, price, last_update = result
                logger.info(f"Before update - {ticker}: {price_column} = {price}, Last_Update = {last_update}")
    
    logger.info(f"Found {len(tickers)} tickers in the database")
    
    # Update ticker names if requested (typically only in AM session)
    if update_names:
        # Update ticker names from yfinance
        logger.info("Updating ticker names...")
        
        # Get all tickers from the database
        cursor.execute("SELECT ticker FROM stocks")
        tickers = [row[0] for row in cursor.fetchall()]
        
        if not tickers:
            logger.error("No tickers found in database")
            return
        
        # Process tickers in batches to avoid rate limiting
        batch_size = 3
        ticker_batches = [tickers[i:i+batch_size] for i in range(0, len(tickers), batch_size)]
        
        total_updated = 0
        
        for batch_idx, batch in enumerate(ticker_batches):
            logger.info(f"Processing name update batch {batch_idx+1}/{len(ticker_batches)} ({len(batch)} tickers)")
            
            try:
                for ticker in batch:
                    max_retries = 3
                    retry_delay = 5
                    
                    for retry in range(max_retries):
                        try:
                            # Get ticker info from yfinance
                            ticker_obj = yf.Ticker(ticker)
                            info = ticker_obj.info
                            
                            # Get the name (longName or shortName)
                            name = info.get('longName', info.get('shortName', ticker))
                            
                            # Update name in database
                            cursor.execute(
                                "UPDATE stocks SET name = ? WHERE ticker = ?",
                                (name, ticker)
                            )
                            
                            logger.info(f"Updated name for {ticker}: {name}")
                            total_updated += 1
                            
                            # Longer delay between individual ticker requests
                            time.sleep(random.uniform(3, 5))
                            break  # Success, exit retry loop
                            
                        except Exception as e:
                            if "Rate limited" in str(e) and retry < max_retries - 1:
                                # Exponential backoff for rate limiting
                                wait_time = retry_delay * (2 ** retry)
                                logger.warning(f"Rate limit hit for {ticker}, retrying in {wait_time} seconds (attempt {retry+1}/{max_retries})")
                                time.sleep(wait_time)
                            else:
                                logger.error(f"Error updating name for {ticker}: {e}")
                                break  # Exit retry loop for other errors
                
                # Commit changes after each batch
                conn.commit()
                
            except Exception as e:
                logger.error(f"Error processing name update batch: {e}")
            
            # Add longer delay between batches to avoid rate limiting
            if batch_idx < len(ticker_batches) - 1:
                delay = random.uniform(20, 30)
                logger.info(f"Waiting {delay:.1f} seconds before next name update batch...")
                time.sleep(delay)
        
        logger.info(f"Updated names for {total_updated} tickers")
    
    # Update prices if requested
    if tickers and should_update_prices:
        update_prices(conn, cursor, session)
        
        # Check updated price values
        logger.info(f"Updated {session}_Price values for sample tickers:")
        for ticker in sample_tickers:
            cursor.execute(f"SELECT ticker, {session}_Price, Last_Price_Update FROM stocks WHERE ticker = ?", (ticker,))
            result = cursor.fetchone()
            if result:
                ticker, price, last_update = result
                logger.info(f"After update - {ticker}: {session}_Price = {price}, Last_Update = {last_update}")
    
    # Close database connection
    conn.close()
    
    # Run alerts if requested
    if run_alerts:
        logger.info("Running alert system...")
        try:
            # Use the -m flag to run as a module, which ensures proper Python path resolution
            subprocess.run([sys.executable, "-m", "stockalert.scripts.alert_system"], check=True)
            logger.info("Alert system completed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running alert system: {e}")
        except Exception as e:
            logger.error(f"Unexpected error running alert system: {e}")

def update_price(ticker, session):
    """Update price for a specific ticker and session"""
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        
        # Get company name using shortName with fallback to ticker
        name = info.get('shortName', ticker)
        
        # Get price with multiple fallbacks
        price = None
        if session == 'AM':
            price = (info.get('regularMarketPrice') or 
                    info.get('currentPrice') or
                    info.get('regularMarketOpen'))
        else:
            price = (info.get('regularMarketPreviousClose') or
                    info.get('previousClose'))
        
        if price is None:
            logging.warning(f"No price found for {ticker} ({name})")
            return None, None
            
        logging.info(f"Updated {name} ({ticker}) {session} price to {price}")
        return price, name
        
    except Exception as e:
        logging.error(f"Error updating {ticker}: {str(e)}")
        return None, None

def main():
    """Main entry point with command line argument parsing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Force price update and alert generation')
    parser.add_argument('--session', choices=['AM', 'PM'], help='Session to update (AM or PM). If not specified, auto-detect based on current time')
    parser.add_argument('--update-names', action='store_true', help='Update ticker names (typically only needed for AM session)')
    parser.add_argument('--no-alerts', action='store_true', help='Skip running alerts after price update')
    parser.add_argument('--skip-name-updates', action='store_true', help='Skip name updates even if --update-names is specified (useful when rate limited)')
    parser.add_argument('--skip-price-updates', action='store_true', help='Skip price updates and only run alerts')
    
    args = parser.parse_args()
    
    # Determine session (AM or PM)
    session = args.session if args.session else get_current_session()
    logger.info(f"Using {session} session")
    
    # Skip name updates if requested
    update_names = args.update_names and not args.skip_name_updates
    if args.update_names and args.skip_name_updates:
        logger.info("Name updates requested but explicitly skipped with --skip-name-updates")
    
    # Skip price updates if requested
    update_prices = not args.skip_price_updates
    if args.skip_price_updates:
        logger.info("Skipping price updates as requested")
    
    # Run alerts unless explicitly disabled
    run_alerts = not args.no_alerts
    
    # Call the price update function
    force_price_update(session, update_names, run_alerts, update_prices)

     # Update prices with progress bar
    eastern = pytz.timezone('America/New_York')
    eastern_time = datetime.now(eastern).strftime('%Y-%m-%d %H:%M:%S')
    
    for ticker in tqdm(tickers, desc="Updating Prices"):
        am_price, name = update_price(ticker, 'AM')
        pm_price, _ = update_price(ticker, 'PM')
        
        # Only update if we got prices
        if am_price and pm_price:
            try:
                cursor.execute('''
                    UPDATE stocks 
                    SET AM_Price = ?, PM_Price = ?, 
                        Last_Price_Update = ?, name = ?
                    WHERE ticker = ?
                ''', (am_price, pm_price, eastern_time, name, ticker))
                
            except Exception as e:
                logging.error(f"Database error for {ticker}: {str(e)}")


if __name__ == "__main__":
    # Load environment variables
    load_environment()
    
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Script interrupted by user. Exiting gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        sys.exit(1)