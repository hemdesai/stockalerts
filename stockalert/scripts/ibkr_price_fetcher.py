#!/usr/bin/env python
"""
Script: ibkr_price_fetcher.py
Purpose: Fetch market data from IBKR Gateway for stocks, ETFs, and cryptocurrencies.
         Designed to integrate with the Stock Alert system by storing data in Eastern Time.
         
All timestamps are stored in Eastern Time (America/New_York timezone) to maintain consistency
with US stock markets as per the system requirements.
"""
import csv
import logging
import time
import sys
import os
import sqlite3
from datetime import datetime
from pathlib import Path
import pytz
from ib_async import IB, Stock, Crypto

# Configure paths
SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR.parent / 'data' / 'stocks.db'
LOG_FILE = SCRIPT_DIR.parent.parent / 'logs' / 'ibkr_price_fetcher.log'

# Configure logging
logging.basicConfig(
    filename=LOG_FILE, 
    level=logging.INFO, 
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Eastern Time zone for consistent timestamp handling
ET_TIMEZONE = pytz.timezone('America/New_York')

# Asset definitions with proper IBKR contract specifications
# Focus on assets that work reliably with IBKR Gateway
ASSETS = [
    # Stocks and ETFs
    {"symbol": "AAPL", "name": "Apple Inc.", "type": "stock", "exchange": "SMART", "currency": "USD"},
    {"symbol": "MSFT", "name": "Microsoft Corporation", "type": "stock", "exchange": "SMART", "currency": "USD"},
    {"symbol": "AMZN", "name": "Amazon.com Inc.", "type": "stock", "exchange": "SMART", "currency": "USD"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.", "type": "stock", "exchange": "SMART", "currency": "USD"},
    {"symbol": "META", "name": "Meta Platforms Inc.", "type": "stock", "exchange": "SMART", "currency": "USD"},
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "type": "stock", "exchange": "SMART", "currency": "USD"},
    {"symbol": "QQQ", "name": "Invesco QQQ Trust", "type": "stock", "exchange": "SMART", "currency": "USD"},
    {"symbol": "IWM", "name": "iShares Russell 2000 ETF", "type": "stock", "exchange": "SMART", "currency": "USD"},
    {"symbol": "GLD", "name": "SPDR Gold Shares", "type": "stock", "exchange": "SMART", "currency": "USD"},
    
    # Cryptocurrencies
    {"symbol": "BTC", "name": "Bitcoin", "type": "crypto", "exchange": "PAXOS", "currency": "USD"},
    {"symbol": "ETH", "name": "Ethereum", "type": "crypto", "exchange": "PAXOS", "currency": "USD"},
    {"symbol": "SOL", "name": "Solana", "type": "crypto", "exchange": "PAXOS", "currency": "USD"},
]

def create_contract(asset):
    """Create the appropriate IBKR contract based on asset type"""
    symbol = asset["symbol"]
    asset_type = asset["type"]
    exchange = asset["exchange"]
    currency = asset["currency"]
    
    if asset_type == "stock":
        return Stock(symbol, exchange, currency)
    elif asset_type == "crypto":
        return Crypto(symbol, exchange, currency)
    else:
        raise ValueError(f"Unsupported asset type: {asset_type}")

def get_contract_details(ib, asset):
    """Get contract details for an asset"""
    try:
        contract = create_contract(asset)
        logger.info(f"Requesting contract details for {asset['symbol']} ({asset['type']})")
        
        # Request contract details
        details = ib.reqContractDetails(contract)
        
        if details and len(details) > 0:
            # Extract relevant information
            detail = details[0]
            contract_desc = detail.contract
            
            # Get the official name
            official_name = getattr(contract_desc, 'longName', None) or \
                           getattr(contract_desc, 'description', None) or \
                           getattr(contract_desc, 'localSymbol', None) or \
                           getattr(contract_desc, 'symbol', '')
            
            logger.info(f"Resolved {asset['symbol']}: {contract_desc} | Name: {official_name}")
            
            return {
                "symbol": asset["symbol"],
                "name": asset["name"],
                "type": asset["type"],
                "exchange": asset["exchange"],
                "currency": asset["currency"],
                "ibkr_symbol": getattr(contract_desc, 'localSymbol', ''),
                "ibkr_name": official_name,
                "ibkr_conid": getattr(contract_desc, 'conId', ''),
                "ibkr_contract": str(contract_desc),
                "status": "resolved",
                "contract": contract_desc  # Keep the actual contract object for market data requests
            }
        else:
            logger.warning(f"Could not resolve {asset['symbol']}")
            return {
                "symbol": asset["symbol"],
                "name": asset["name"],
                "type": asset["type"],
                "exchange": asset["exchange"],
                "currency": asset["currency"],
                "ibkr_symbol": "",
                "ibkr_name": "",
                "ibkr_conid": "",
                "ibkr_contract": "",
                "status": "not_found",
                "contract": None
            }
    except Exception as e:
        logger.error(f"Error resolving contract for {asset['symbol']}: {e}")
        return {
            "symbol": asset["symbol"],
            "name": asset["name"],
            "type": asset["type"],
            "exchange": asset["exchange"],
            "currency": asset["currency"],
            "ibkr_symbol": "",
            "ibkr_name": "",
            "ibkr_conid": "",
            "ibkr_contract": "",
            "status": "error",
            "error": str(e),
            "contract": None
        }

def get_market_data(ib, asset_result):
    """Get market data for a resolved contract"""
    if asset_result["status"] != "resolved" or not asset_result["contract"]:
        return asset_result
    
    try:
        symbol = asset_result["symbol"]
        contract = asset_result["contract"]
        
        logger.info(f"Requesting market data for {symbol}")
        
        # Request market data with generic ticks for more data
        # 100: Option Volume, 101: Option Open Interest, 104: Historical Volatility, 106: Option Implied Volatility
        # 165: Fundamental Ratios, 221: Mark Price, 225: Auction Values, 233: RTVolume, 236: Shortable
        ticker = ib.reqMktData(contract, '100,101,104,106,165,221,225,233,236', False, False)
        
        # Wait longer for data to arrive (up to 10 seconds)
        price_found = False
        for i in range(20):  # 20 * 0.5 = 10 seconds
            # Check all possible price fields
            if (ticker.last and ticker.last != 0) or \
               (ticker.close and ticker.close != 0) or \
               (ticker.bid and ticker.bid != 0) or \
               (ticker.ask and ticker.ask != 0) or \
               (ticker.marketPrice() and ticker.marketPrice() != 0):
                price_found = True
                logger.info(f"Price data received for {symbol} after {i*0.5} seconds")
                break
            time.sleep(0.5)
        
        if not price_found:
            logger.warning(f"No price data received for {symbol} after 10 seconds")
            # Print all ticker attributes for debugging
            ticker_attrs = {attr: getattr(ticker, attr) for attr in dir(ticker) 
                          if not attr.startswith('_') and not callable(getattr(ticker, attr))}
            logger.debug(f"Ticker data for {symbol}: {ticker_attrs}")
        
        # Get current time in Eastern Time
        now = datetime.now(ET_TIMEZONE)
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S %Z")
        
        # Try to get the best price available
        last_price = ticker.last if ticker.last and ticker.last != 0 else None
        close_price = ticker.close if ticker.close and ticker.close != 0 else None
        market_price = ticker.marketPrice() if ticker.marketPrice() and ticker.marketPrice() != 0 else None
        mid_point = None
        
        # Calculate mid-point if bid and ask are available
        if ticker.bid and ticker.ask and ticker.bid != 0 and ticker.ask != 0:
            mid_point = (ticker.bid + ticker.ask) / 2
        
        # Use the best available price in this priority: last > market > close > mid-point > bid
        best_price = last_price or market_price or close_price or mid_point or ticker.bid
        
        # Add market data to result
        asset_result.update({
            "last_price": last_price,
            "bid_price": ticker.bid,
            "ask_price": ticker.ask,
            "close_price": close_price,
            "market_price": market_price,
            "mid_point": mid_point,
            "best_price": best_price,  # This is what we'll use for the database
            "high_price": ticker.high,
            "low_price": ticker.low,
            "volume": ticker.volume,
            "timestamp": timestamp
        })
        
        # Cancel the market data subscription
        ib.cancelMktData(ticker)
        
        return asset_result
    except Exception as e:
        logger.error(f"Error getting market data for {asset_result['symbol']}: {e}")
        asset_result.update({
            "market_data_error": str(e),
            "timestamp": datetime.now(ET_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S %Z")
        })
        return asset_result

def connect_to_ibkr():
    """Connect to IBKR Gateway with retry logic"""
    ib = IB()
    logger.info("Connecting to IBKR...")
    
    # Try different ports and client IDs
    ports_to_try = [
        (4001, 123, "Gateway API port"),  # Standard Gateway API port
        (7496, 456, "TWS API port"),      # Standard TWS API port
        (7497, 789, "TWS Paper API port") # Paper trading TWS API port
    ]
    
    for port, client_id, port_desc in ports_to_try:
        try:
            print(f"Attempting connection to {port_desc} (127.0.0.1:{port}, clientId={client_id})...")
            logger.info(f"Attempting connection to {port_desc} (127.0.0.1:{port}, clientId={client_id})...")
            
            # Set a shorter timeout for faster failure
            ib.RequestTimeout = 10
            ib.connect('127.0.0.1', port, clientId=client_id)
            
            print(f"✅ Connected to IBKR via {port_desc}")
            logger.info(f"Connected to IBKR via {port_desc}")
            return ib
        except Exception as e:
            print(f"❌ Failed to connect to {port_desc}: {e}")
            logger.error(f"Failed to connect to {port_desc}: {e}")
            continue
    
    # If we get here, all connection attempts failed
    raise ConnectionError("Failed to connect to IBKR on any port")

def update_database(results, session='AM'):
    """Update the stocks database with the fetched prices"""
    try:
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get current time in Eastern Time
        now = datetime.now(ET_TIMEZONE)
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        
        updated_count = 0
        for result in results:
            if result["status"] != "resolved":
                continue
                
            symbol = result["symbol"]
            
            # Use the best price available from our prioritized list
            price = result.get("best_price")
            
            if not price or price == 'nan' or price is None:
                # Try alternative price fields if best_price is not available
                price = result.get("last_price") or result.get("market_price") or \
                        result.get("close_price") or result.get("mid_point") or \
                        result.get("bid_price")
                
                if not price or price == 'nan' or price is None:
                    logger.warning(f"No valid price for {symbol}, skipping database update")
                    continue
            
            # Determine which price field to update based on session
            price_field = f"{session}_Price"  # Using correct column names: AM_Price or PM_Price
            
            # Update the stocks table
            try:
                # First check if the ticker exists
                cursor.execute("SELECT ticker FROM stocks WHERE ticker = ?", (symbol,))
                if cursor.fetchone():
                    # Update existing ticker
                    cursor.execute(
                        f"UPDATE stocks SET {price_field} = ?, Last_Price_Update = ? WHERE ticker = ?",
                        (price, timestamp, symbol)
                    )
                else:
                    # Insert new ticker with name from IBKR
                    name = result.get("ibkr_name") or result.get("name", "")
                    
                    # For new tickers, set both AM and PM prices to the same value initially
                    if session == 'AM':
                        cursor.execute(
                            "INSERT INTO stocks (ticker, name, AM_Price, PM_Price, Last_Price_Update) VALUES (?, ?, ?, ?, ?)",
                            (symbol, name, price, price, timestamp)
                        )
                    else:  # PM
                        cursor.execute(
                            "INSERT INTO stocks (ticker, name, AM_Price, PM_Price, Last_Price_Update) VALUES (?, ?, ?, ?, ?)",
                            (symbol, name, price, price, timestamp)
                        )
                
                updated_count += 1
                logger.info(f"Updated {symbol} {session} price to {price} in database")
            except Exception as e:
                logger.error(f"Error updating {symbol} in database: {e}")
        
        # Commit changes
        conn.commit()
        logger.info(f"Updated {updated_count} tickers in database with {session} prices")
        print(f"Updated {updated_count} tickers in database with {session} prices")
        
        return updated_count
    except Exception as e:
        logger.error(f"Database error: {e}")
        print(f"Database error: {e}")
        return 0
    finally:
        if 'conn' in locals():
            conn.close()

def fetch_prices(session='AM', batch_size=3, delay_between_batches=10, update_db=True):
    """
    Fetch market data for the specified assets and optionally update the database.
    
    Args:
        session: 'AM' or 'PM' to indicate which session prices to update
        batch_size: Number of assets to process in each batch
        delay_between_batches: Delay in seconds between batches
        update_db: Whether to update the database with the fetched prices
    
    Returns:
        List of asset results with market data.
    """
    # Connect to IBKR
    ib = connect_to_ibkr()
    
    try:
        # Process assets in batches (smaller batches to avoid overwhelming IBKR)
        results = []
        batches = [ASSETS[i:i+batch_size] for i in range(0, len(ASSETS), batch_size)]
        
        for batch_idx, batch in enumerate(batches):
            print(f"\nProcessing batch {batch_idx+1}/{len(batches)}...")
            
            batch_results = []
            for asset in batch:
                symbol = asset["symbol"]
                asset_type = asset["type"]
                
                print(f"Processing {symbol} ({asset_type})...")
                
                # Get contract details
                asset_result = get_contract_details(ib, asset)
                
                # If contract was resolved, get market data
                if asset_result["status"] == "resolved":
                    asset_result = get_market_data(ib, asset_result)
                
                # Remove the contract object before storing (not serializable)
                if "contract" in asset_result:
                    del asset_result["contract"]
                
                batch_results.append(asset_result)
                results.append(asset_result)
                
                # Print result summary
                if asset_result["status"] == "resolved":
                    # Show the best available price
                    best_price = asset_result.get("best_price")
                    last_price = asset_result.get("last_price")
                    market_price = asset_result.get("market_price")
                    close_price = asset_result.get("close_price")
                    mid_point = asset_result.get("mid_point")
                    
                    # Construct price string showing all available prices
                    price_details = []
                    if best_price is not None and best_price != 'nan':
                        price_details.append(f"Best: {best_price}")
                    if last_price is not None and last_price != 'nan':
                        price_details.append(f"Last: {last_price}")
                    if market_price is not None and market_price != 'nan':
                        price_details.append(f"Market: {market_price}")
                    if close_price is not None and close_price != 'nan':
                        price_details.append(f"Close: {close_price}")
                    if mid_point is not None and mid_point != 'nan':
                        price_details.append(f"Mid: {mid_point}")
                    
                    price_str = f" - {' | '.join(price_details)}" if price_details else ""
                    print(f"✅ {symbol}: Resolved{price_str}")
                else:
                    error = asset_result.get("error", "Unknown error")
                    print(f"❌ {symbol}: {asset_result['status'].title()} - {error}")
                
                # Small delay between assets
                time.sleep(0.5)
            
            # Delay between batches to avoid rate limiting
            if batch_idx < len(batches) - 1:
                print(f"Waiting {delay_between_batches} seconds before next batch...")
                time.sleep(delay_between_batches)
        
        # Update database if requested
        if update_db:
            update_database(results, session)
        
        return results
    
    finally:
        # Disconnect from IBKR
        if ib.isConnected():
            ib.disconnect()
            logger.info("Disconnected from IBKR Gateway")
            print("Disconnected from IBKR Gateway")

def trigger_alerts():
    """Trigger the alert system to generate alerts based on the updated prices"""
    try:
        # Path to the alert system script
        alert_script = SCRIPT_DIR / 'alert_system.py'
        
        # Check if the script exists
        if not alert_script.exists():
            logger.error(f"Alert system script not found at {alert_script}")
            print(f"Alert system script not found at {alert_script}")
            return False
        
        # Run the alert system script as a subprocess
        import subprocess
        print("Triggering alert system...")
        logger.info("Triggering alert system...")
        
        result = subprocess.run(
            [sys.executable, str(alert_script)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Alert system triggered successfully")
            print("Alert system triggered successfully")
            return True
        else:
            logger.error(f"Alert system error: {result.stderr}")
            print(f"Alert system error: {result.stderr}")
            return False
    
    except Exception as e:
        logger.error(f"Error triggering alerts: {e}")
        print(f"Error triggering alerts: {e}")
        return False

def main():
    """Main function to fetch prices and update the database"""
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Fetch prices from IBKR Gateway and update the database')
    parser.add_argument('--session', choices=['AM', 'PM'], default='AM', help='Session to update prices for (AM or PM)')
    parser.add_argument('--batch-size', type=int, default=3, help='Number of assets to process in each batch')
    parser.add_argument('--delay', type=int, default=10, help='Delay in seconds between batches')
    parser.add_argument('--no-db-update', action='store_true', help='Do not update the database')
    parser.add_argument('--trigger-alerts', action='store_true', help='Trigger the alert system after updating prices')
    
    args = parser.parse_args()
    
    print(f"\n=== IBKR Price Fetcher ({args.session} Session) ===")
    print("Fetching prices from IBKR Gateway for stocks, ETFs, and cryptocurrencies.")
    print("Make sure IBKR Gateway is running and API connections are enabled.")
    print("-" * 70)
    
    try:
        # Fetch prices
        results = fetch_prices(
            session=args.session,
            batch_size=args.batch_size,
            delay_between_batches=args.delay,
            update_db=not args.no_db_update
        )
        
        # Print summary
        resolved_count = sum(1 for r in results if r["status"] == "resolved")
        print("\n" + "-" * 70)
        print(f"Fetched prices for {len(results)} assets ({resolved_count} resolved)")
        
        # Trigger alerts if requested
        if args.trigger_alerts and not args.no_db_update:
            trigger_alerts()
        
        print("-" * 70)
        return 0
    
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        logger.error(f"Error in main function: {e}\n{error_msg}")
        print(f"\nERROR: {e}")
        print("Script execution failed")
        return 1

if __name__ == "__main__":
    # Set up console logging
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    sys.exit(main())
