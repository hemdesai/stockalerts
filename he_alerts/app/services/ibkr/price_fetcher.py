"""
IBKR price fetching service.
Fetches real-time and snapshot prices for stocks.
"""
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from ib_async import IB, Contract
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.stock import Stock
from app.services.ibkr.contract_resolver import ContractResolver
from app.core.config import settings

logger = structlog.get_logger(__name__)


class PriceFetcher:
    """Handles price fetching from IBKR."""
    
    def __init__(self):
        self.ib = IB()
        self.contract_resolver = ContractResolver()
        self.connected = False
        
    async def connect(self):
        """Connect to IBKR Gateway/TWS."""
        if not self.connected:
            try:
                await self.ib.connectAsync(
                    host=settings.IBKR_HOST,
                    port=settings.IBKR_PORT,
                    clientId=settings.IBKR_CLIENT_ID
                )
                self.connected = True
                logger.info("Connected to IBKR")
            except Exception as e:
                logger.error(f"Failed to connect to IBKR: {e}")
                raise
    
    async def disconnect(self):
        """Disconnect from IBKR."""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from IBKR")
    
    async def resolve_and_store_contract(self, stock: Stock) -> Optional[Contract]:
        """
        Resolve IBKR contract for a stock and store it in database.
        
        Args:
            stock: Stock model instance
            
        Returns:
            Resolved IBKR Contract or None
        """
        # Check if we already have a resolved contract
        if stock.ibkr_contract_resolved and stock.ibkr_contract:
            try:
                contract_data = json.loads(stock.ibkr_contract)
                return self.contract_resolver.json_to_contract(contract_data)
            except Exception as e:
                logger.warning(f"Failed to load stored contract for {stock.ticker}: {e}")
        
        # Classify and create contract
        asset_type = self.contract_resolver.classify_asset(
            stock.ticker, 
            stock.name or "", 
            stock.category
        )
        contract = self.contract_resolver.create_contract(stock.ticker, asset_type)
        
        if not contract:
            logger.error(f"Failed to create contract for {stock.ticker}")
            return None
        
        try:
            # Resolve contract details with IBKR
            details = await self.ib.reqContractDetailsAsync(contract)
            
            if not details:
                logger.warning(f"No contract details found for {stock.ticker}")
                return None
            
            # Use the first matching contract
            resolved_contract = details[0].contract
            
            # Store contract data
            contract_data = self.contract_resolver.contract_to_json(resolved_contract)
            stock.ibkr_contract = json.dumps(contract_data)
            stock.ibkr_contract_resolved = True
            
            logger.info(f"Resolved contract for {stock.ticker}: {contract_data}")
            return resolved_contract
            
        except Exception as e:
            logger.error(f"Error resolving contract for {stock.ticker}: {e}")
            return None
    
    async def fetch_price(self, contract: Contract) -> Optional[float]:
        """
        Fetch current price for a contract.
        
        Args:
            contract: IBKR Contract object
            
        Returns:
            Current price or None
        """
        try:
            # Request market data snapshot
            ticker = self.ib.reqMktData(contract, snapshot=True)
            
            # Wait for data to be populated
            await asyncio.sleep(2)
            
            # Log available data
            logger.info(
                f"Market data for {contract.symbol}: "
                f"last={ticker.last}, close={ticker.close}, "
                f"bid={ticker.bid}, ask={ticker.ask}, "
                f"volume={ticker.volume}, time={ticker.time}"
            )
            
            # Use last price as primary, fall back to close
            price = ticker.last
            
            # Check if price is NaN or invalid
            import math
            if price is None or math.isnan(price) or price <= 0:
                price = ticker.close
                if price and not math.isnan(price) and price > 0:
                    logger.info(f"Using close price for {contract.symbol}: {price}")
            
            if price is None or math.isnan(price) or price <= 0:
                # Try midpoint of bid/ask
                if ticker.bid and ticker.ask and not math.isnan(ticker.bid) and not math.isnan(ticker.ask) and ticker.bid > 0 and ticker.ask > 0:
                    price = (ticker.bid + ticker.ask) / 2
                    logger.info(f"Using bid/ask midpoint for {contract.symbol}: {price}")
            
            # Cancel market data subscription
            self.ib.cancelMktData(ticker)
            
            return price
            
        except Exception as e:
            logger.error(f"Error fetching price for {contract.symbol}: {e}")
            return None
    
    async def update_stock_prices(self, db: AsyncSession, session_type: str = "AM"):
        """
        Update prices for all active stocks.
        
        Args:
            db: Database session
            session_type: "AM" or "PM" to determine which price column to update
        """
        await self.connect()
        
        try:
            # Get all active stocks
            result = await db.execute(
                select(Stock).where(Stock.is_active == True)
            )
            stocks = result.scalars().all()
            
            logger.info(f"Updating prices for {len(stocks)} active stocks")
            
            updated_count = 0
            alerts = []
            
            for stock in stocks:
                try:
                    # Resolve contract
                    contract = await self.resolve_and_store_contract(stock)
                    if not contract:
                        logger.warning(f"Skipping {stock.ticker} - no contract")
                        continue
                    
                    # Fetch price
                    price = await self.fetch_price(contract)
                    if price is None:
                        logger.warning(f"No price available for {stock.ticker}")
                        continue
                    
                    # Update price in database
                    price_field = "am_price" if session_type == "AM" else "pm_price"
                    setattr(stock, price_field, price)
                    stock.last_price_update = datetime.utcnow()
                    
                    logger.info(f"Updated {stock.ticker}: {price_field} = {price}")
                    updated_count += 1
                    
                    # Check for alerts
                    if stock.buy_trade and price <= stock.buy_trade:
                        alerts.append({
                            'ticker': stock.ticker,
                            'type': 'BUY',
                            'price': price,
                            'threshold': stock.buy_trade,
                            'sentiment': stock.sentiment
                        })
                    
                    if stock.sell_trade and price >= stock.sell_trade:
                        alerts.append({
                            'ticker': stock.ticker,
                            'type': 'SELL', 
                            'price': price,
                            'threshold': stock.sell_trade,
                            'sentiment': stock.sentiment
                        })
                    
                    # Small delay to avoid rate limits
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error updating price for {stock.ticker}: {e}")
                    continue
            
            # Commit all changes
            await db.commit()
            
            logger.info(f"Price update complete: {updated_count} stocks updated")
            
            # Log alerts
            for alert in alerts:
                logger.info(
                    f"ALERT: {alert['type']} signal for {alert['ticker']} "
                    f"at ${alert['price']:.2f} (threshold: ${alert['threshold']:.2f})"
                )
            
            return {
                'updated_count': updated_count,
                'total_stocks': len(stocks),
                'alerts': alerts,
                'session': session_type
            }
            
        finally:
            await self.disconnect()
    
    async def get_single_price(self, ticker: str) -> Optional[float]:
        """
        Get price for a single ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Current price or None
        """
        await self.connect()
        
        try:
            # Create contract
            asset_type = self.contract_resolver.classify_asset(ticker)
            contract = self.contract_resolver.create_contract(ticker, asset_type)
            
            if not contract:
                return None
            
            # Resolve contract
            details = await self.ib.reqContractDetailsAsync(contract)
            if not details:
                return None
            
            resolved_contract = details[0].contract
            
            # Fetch price
            return await self.fetch_price(resolved_contract)
            
        finally:
            await self.disconnect()