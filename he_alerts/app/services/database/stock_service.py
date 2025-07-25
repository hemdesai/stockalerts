"""
Database service for stock operations.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock
from app.schemas.stock import StockCreate, StockUpdate, StockBulkCreate
from app.core.logging import get_logger

logger = get_logger(__name__)


class StockService:
    """Service for stock database operations."""
    
    @staticmethod
    async def create_stock(db: AsyncSession, stock_data: StockCreate) -> Stock:
        """
        Create a new stock entry.
        
        Args:
            db: Database session
            stock_data: Stock creation data
            
        Returns:
            Created stock instance
        """
        try:
            stock = Stock(**stock_data.dict())
            db.add(stock)
            await db.commit()
            await db.refresh(stock)
            
            logger.info(f"Created stock: {stock.ticker} ({stock.category})")
            return stock
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating stock {stock_data.ticker}: {e}")
            raise
    
    @staticmethod
    async def delete_stocks_by_category(db: AsyncSession, category: str) -> int:
        """
        Delete all stocks in a specific category.
        
        Args:
            db: Database session
            category: Stock category to delete
            
        Returns:
            Number of deleted stocks
        """
        try:
            result = await db.execute(
                delete(Stock).where(Stock.category == category)
            )
            await db.commit()
            deleted_count = result.rowcount
            logger.info(f"Deleted {deleted_count} stocks from category: {category}")
            return deleted_count
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error deleting stocks from category {category}: {e}")
            raise
    
    @staticmethod
    async def bulk_create_stocks(db: AsyncSession, stocks_data: List[StockCreate]) -> List[Stock]:
        """
        Create multiple stocks in bulk.
        
        Args:
            db: Database session
            stocks_data: List of stock creation data
            
        Returns:
            List of created stock instances
        """
        try:
            stocks = [Stock(**stock_data.dict()) for stock_data in stocks_data]
            db.add_all(stocks)
            await db.commit()
            
            for stock in stocks:
                await db.refresh(stock)
            
            logger.info(f"Created {len(stocks)} stocks in bulk")
            return stocks
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating stocks in bulk: {e}")
            raise
    
    @staticmethod
    async def get_stock_by_ticker_and_category(
        db: AsyncSession, 
        ticker: str, 
        category: str
    ) -> Optional[Stock]:
        """
        Get stock by ticker and category.
        
        Args:
            db: Database session
            ticker: Stock ticker
            category: Stock category
            
        Returns:
            Stock instance or None
        """
        try:
            result = await db.execute(
                select(Stock).where(
                    and_(Stock.ticker == ticker.upper(), Stock.category == category)
                )
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error fetching stock {ticker} in {category}: {e}")
            return None
    
    @staticmethod
    async def get_stocks_by_category(
        db: AsyncSession, 
        category: str, 
        active_only: bool = True,
        limit: int = 100
    ) -> List[Stock]:
        """
        Get stocks by category.
        
        Args:
            db: Database session
            category: Stock category
            active_only: Only return active stocks
            limit: Maximum number of results
            
        Returns:
            List of stock instances
        """
        try:
            query = select(Stock).where(Stock.category == category)
            
            if active_only:
                query = query.where(Stock.is_active == True)
            
            query = query.limit(limit).order_by(Stock.updated_at.desc())
            
            result = await db.execute(query)
            stocks = result.scalars().all()
            
            logger.debug(f"Retrieved {len(stocks)} stocks for category {category}")
            return list(stocks)
            
        except Exception as e:
            logger.error(f"Error fetching stocks for category {category}: {e}")
            return []
    
    @staticmethod
    async def update_stock(db: AsyncSession, stock_id: int, stock_data: StockUpdate) -> Optional[Stock]:
        """
        Update a stock entry.
        
        Args:
            db: Database session
            stock_id: Stock ID
            stock_data: Update data
            
        Returns:
            Updated stock instance or None
        """
        try:
            # Get existing stock
            result = await db.execute(select(Stock).where(Stock.id == stock_id))
            stock = result.scalar_one_or_none()
            
            if not stock:
                return None
            
            # Update fields
            update_data = stock_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(stock, field, value)
            
            stock.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(stock)
            
            logger.info(f"Updated stock: {stock.ticker} ({stock.category})")
            return stock
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating stock {stock_id}: {e}")
            raise
    
    @staticmethod
    async def update_stock_prices(
        db: AsyncSession, 
        ticker: str, 
        category: str,
        am_price: Optional[float] = None,
        pm_price: Optional[float] = None
    ) -> Optional[Stock]:
        """
        Update stock prices by ticker and category.
        
        Args:
            db: Database session
            ticker: Stock ticker
            category: Stock category
            am_price: AM session price
            pm_price: PM session price
            
        Returns:
            Updated stock instance or None
        """
        try:
            stock = await StockService.get_stock_by_ticker_and_category(db, ticker, category)
            if not stock:
                logger.warning(f"Stock {ticker} not found in category {category}")
                return None
            
            # Update prices
            if am_price is not None:
                stock.am_price = am_price
            if pm_price is not None:
                stock.pm_price = pm_price
            
            stock.last_price_update = datetime.utcnow()
            stock.updated_at = datetime.utcnow()
            
            await db.commit()
            await db.refresh(stock)
            
            logger.info(f"Updated prices for {ticker}: AM={am_price}, PM={pm_price}")
            return stock
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating prices for {ticker}: {e}")
            raise
    
    @staticmethod
    async def get_stocks_needing_price_updates(db: AsyncSession) -> List[Stock]:
        """
        Get stocks that need price updates.
        
        Args:
            db: Database session
            
        Returns:
            List of stocks needing updates
        """
        try:
            # Get active stocks without recent price updates
            cutoff_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            query = select(Stock).where(
                and_(
                    Stock.is_active == True,
                    or_(
                        Stock.last_price_update == None,
                        Stock.last_price_update < cutoff_time
                    )
                )
            )
            
            result = await db.execute(query)
            stocks = result.scalars().all()
            
            logger.info(f"Found {len(stocks)} stocks needing price updates")
            return list(stocks)
            
        except Exception as e:
            logger.error(f"Error fetching stocks needing updates: {e}")
            return []
    
    @staticmethod
    async def get_stocks_for_alerts(db: AsyncSession, session: str = None) -> List[Stock]:
        """
        Get stocks that may trigger alerts.
        
        Args:
            db: Database session
            session: Trading session (AM/PM) filter
            
        Returns:
            List of stocks with prices and thresholds
        """
        try:
            query = select(Stock).where(
                and_(
                    Stock.is_active == True,
                    Stock.last_price_update != None,
                    or_(
                        and_(Stock.am_price != None, Stock.buy_trade != None),
                        and_(Stock.am_price != None, Stock.sell_trade != None),
                        and_(Stock.pm_price != None, Stock.buy_trade != None),
                        and_(Stock.pm_price != None, Stock.sell_trade != None)
                    )
                )
            )
            
            result = await db.execute(query)
            stocks = result.scalars().all()
            
            # Filter stocks that should alert
            alert_stocks = []
            for stock in stocks:
                if stock.should_alert_buy or stock.should_alert_sell:
                    alert_stocks.append(stock)
            
            logger.info(f"Found {len(alert_stocks)} stocks ready for alerts")
            return alert_stocks
            
        except Exception as e:
            logger.error(f"Error fetching stocks for alerts: {e}")
            return []
    
    @staticmethod
    async def deactivate_old_stocks(db: AsyncSession, category: str, email_id: str) -> int:
        """
        Deactivate stocks not in the latest email for a category.
        
        Args:
            db: Database session
            category: Stock category
            email_id: Latest email message ID
            
        Returns:
            Number of stocks deactivated
        """
        try:
            # Deactivate stocks in category that don't have the latest email ID
            result = await db.execute(
                update(Stock)
                .where(
                    and_(
                        Stock.category == category,
                        Stock.source_email_id != email_id,
                        Stock.is_active == True
                    )
                )
                .values(is_active=False, updated_at=datetime.utcnow())
            )
            
            deactivated_count = result.rowcount
            await db.commit()
            
            logger.info(f"Deactivated {deactivated_count} old stocks in {category}")
            return deactivated_count
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error deactivating old stocks: {e}")
            raise
    
    @staticmethod
    async def upsert_stocks_from_email(
        db: AsyncSession, 
        stocks_data: List[Dict[str, Any]], 
        email_id: str,
        category: str
    ) -> Dict[str, int]:
        """
        Replace all stocks in a category with new data from email.
        
        Args:
            db: Database session
            stocks_data: List of stock data dictionaries
            email_id: Source email message ID
            category: Stock category
            
        Returns:
            Dictionary with counts of created/deleted stocks
        """
        try:
            # Delete all existing stocks in this category first
            deleted_count = await StockService.delete_stocks_by_category(db, category)
            
            # Create all new stocks
            stock_creates = [StockCreate(**stock_data) for stock_data in stocks_data]
            await StockService.bulk_create_stocks(db, stock_creates)
            created_count = len(stock_creates)
            
            logger.info(f"Replaced stocks in {category}: {deleted_count} deleted, {created_count} created")
            
            return {
                'created': created_count,
                'updated': 0,
                'deleted': deleted_count
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error replacing stocks from email: {e}")
            raise