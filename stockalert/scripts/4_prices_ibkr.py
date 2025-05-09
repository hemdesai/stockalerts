"""
ibkr_price_update_async.py

IBKR price update script using ib_async (recommended by IBKR team).
- Reads tickers and thresholds from stocks.db
- Resolves contracts using ib_async (robust asset classification)
- Fetches latest prices asynchronously for all assets
- Updates AM/PM prices in stocks.db and logs alerts
- All timestamps are in Eastern Time (America/New_York)
"""
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
import pytz
import asyncio
from ib_async import IB, Stock, Index, Forex, Crypto, Future, Bond

DB_PATH = Path(__file__).parent.parent / 'data' / 'stocks.db'
LOG_FILE = Path(__file__).resolve().parent.parent.parent / 'logs' / '4_prices_ibkr.log'

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# --- STEP 1: Extract tickers and thresholds ---
def extract_tickers_and_thresholds():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, name, buy_trade, sell_trade FROM stocks")
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        ticker, name, buy_trade, sell_trade = row
        result.append({
            'ticker': ticker,
            'name': name or '',
            'buy_trade': buy_trade,
            'sell_trade': sell_trade
        })
    return result

# --- STEP 2: Asset classification (ported from ibkr_asset_checker.py) ---
# Mapping for user-friendly crypto names to IBKR symbols
CRYPTO_SYMBOL_MAP = {
    "BITCOIN": "BTC",
    "ETHEREUM": "ETH",
    "SOLANA": "SOL",
    # Add more as needed
}

def get_crypto_symbol(symbol):
    return CRYPTO_SYMBOL_MAP.get(symbol.upper(), symbol)

def classify_asset(symbol, name_hint):
    symbol = symbol.upper()
    if symbol.endswith('=F') or symbol in {'CL=F', 'BZ=F', 'NG=F', 'GC=F', 'HG=F', 'SI=F'}:
        return 'future'
    if symbol.startswith('^') or 'INDEX' in name_hint.upper():
        return 'index'
    if symbol.endswith('USD') or 'CRYPTO' in name_hint.upper() or symbol in CRYPTO_SYMBOL_MAP:
        return 'crypto'
    # Add more rules as needed
    return 'stock'

import json

# --- STEP 3: Build IBKR contract from JSON or resolve/store if missing ---
def build_contract_from_json(contract_json):
    # contract_json is a dict with keys: conId, symbol, secType, exchange, currency
    if not contract_json:
        return None
    secType = contract_json.get('secType', 'STK')
    if secType == 'STK':
        return Stock(contract_json['symbol'], contract_json['exchange'], contract_json['currency'])
    elif secType == 'FUT':
        return Future(contract_json['symbol'], contract_json['exchange'], contract_json['currency'])
    elif secType == 'INDEX':
        return Index(contract_json['symbol'], contract_json['exchange'], contract_json['currency'])
    elif secType == 'CASH':
        return Forex(contract_json['symbol'], contract_json['exchange'])
    elif secType == 'CRYPTO':
        return Crypto(contract_json['symbol'], contract_json['exchange'], contract_json['currency'])
    else:
        return Stock(contract_json['symbol'], contract_json['exchange'], contract_json['currency'])

async def fetch_and_update_prices(session):
    tz = pytz.timezone('America/New_York')
    now = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    assets = extract_tickers_and_thresholds()
    ib = IB()
    await ib.connectAsync('127.0.0.1', 4001, clientId=999)
    updated = 0
    alerts = []
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for asset in assets:
        symbol = asset['ticker']
        name = asset['name']
        buy_trade = asset['buy_trade']
        sell_trade = asset['sell_trade']
        asset_type = classify_asset(symbol, name)
        # Try to load contract JSON from DB
        cursor.execute("SELECT ibkr_contract FROM stocks WHERE ticker = ?", (symbol,))
        row = cursor.fetchone()
        contract_json = None
        if row and row[0]:
            try:
                contract_json = json.loads(row[0])
            except Exception as e:
                logger.warning(f"Could not parse ibkr_contract for {symbol}: {e}")
        contract = build_contract_from_json(contract_json) if contract_json else None
        # If contract not in DB, resolve and store it
        if not contract:
            contract = None
            try:
                # Use the old logic to resolve contract
                if asset_type == 'stock':
                    contract = Stock(symbol, 'SMART', 'USD')
                elif asset_type == 'future':
                    contract = Future(symbol, 'CME', 'USD')
                elif asset_type == 'index':
                    contract = Index(symbol, 'CBOE', 'USD')
                elif asset_type == 'forex':
                    contract = Forex(symbol, 'IDEALPRO')
                elif asset_type == 'crypto':
                    # Map user-friendly names (BITCOIN, etc) to IBKR symbols (BTC, etc)
                    base = get_crypto_symbol(symbol.replace('.USD', ''))
                    contract = Crypto(base, 'PAXOS', 'USD')
                else:
                    contract = Stock(symbol, 'SMART', 'USD')
                details = await ib.reqContractDetailsAsync(contract)
                if not details:
                    logger.warning(f"No contract details for {symbol}")
                    continue
                detail = details[0].contract
                contract_json = {
                    'conId': getattr(detail, 'conId', None),
                    'symbol': getattr(detail, 'symbol', symbol),
                    'secType': getattr(detail, 'secType', asset_type.upper()),
                    'exchange': getattr(detail, 'exchange', 'SMART'),
                    'currency': getattr(detail, 'currency', 'USD')
                }
                cursor.execute("UPDATE stocks SET ibkr_contract = ? WHERE ticker = ?", (json.dumps(contract_json), symbol))
                conn.commit()
                contract = build_contract_from_json(contract_json)
            except Exception as e:
                logger.error(f"Error resolving contract for {symbol}: {e}")
                continue
        try:
            ticker = ib.reqMktData(contract, snapshot=True)
            await asyncio.sleep(2)  # Give IBKR time to fill in data
            # Debug logging: log all available key fields
            logger.info(f"Ticker fields for {symbol}: last={ticker.last}, close={ticker.close}, bid={ticker.bid}, ask={ticker.ask}, volume={ticker.volume}, time={ticker.time}")
            # IBKR price snapshot: always use last price per user confirmation
            price = ticker.last
            if price is None:
                logger.warning(f"No last price for {symbol}")
                continue
            # Store price in the correct AM/PM column in the stocks table
            price_col = f"{session}_Price"
            cursor.execute(f"UPDATE stocks SET {price_col} = ?, Last_Price_Update = ? WHERE ticker = ?", (price, now, symbol))
            logger.info(f"Updated {symbol}: {price_col} = {price}")
            # Alert logic (price used here as well)
            if buy_trade is not None and price <= buy_trade:
                alerts.append({'ticker': symbol, 'type': 'BUY', 'price': price})
            if sell_trade is not None and price >= sell_trade:
                alerts.append({'ticker': symbol, 'type': 'SELL', 'price': price})
            updated += 1
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
        await asyncio.sleep(1)  # Avoid rate limits
    conn.commit()
    conn.close()
    ib.disconnect()
    logger.info(f"Updated prices for {updated} tickers in {session} session.")
    for alert in alerts:
        logger.info(f"ALERT: {alert['type']} {alert['ticker']} at {alert['price']}")
    return alerts

# --- MAIN ENTRYPOINT ---
def run_ibkr_price_update_async(session):
    asyncio.run(fetch_and_update_prices(session))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Async IBKR Price Update for Stock Alert')
    parser.add_argument('--session', choices=['AM', 'PM'], required=True, help='Session to update (AM/PM)')
    args = parser.parse_args()
    run_ibkr_price_update_async(args.session)
