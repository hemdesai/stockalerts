"""
Stock management endpoints.
"""
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_database
from app.core.logging import get_logger
from app.services.database import StockService
from app.schemas.stock import Stock, StockList, StockCreate, StockUpdate

logger = get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=List[Stock])
async def get_stocks(
    category: Optional[str] = Query(None, description="Filter by category"),
    active_only: bool = Query(True, description="Only active stocks"),
    limit: int = Query(100, description="Maximum results", ge=1, le=500),
    db: AsyncSession = Depends(get_database)
) -> List[Stock]:
    """
    Get stocks with optional filtering.
    
    Args:
        category: Filter by category (daily, digitalassets, ideas, etfs)
        active_only: Only return active stocks
        limit: Maximum number of results
        db: Database session
        
    Returns:
        List of stocks
    """
    try:
        if category:
            stocks = await StockService.get_stocks_by_category(
                db=db,
                category=category,
                active_only=active_only,
                limit=limit
            )
        else:
            # Get all categories
            all_stocks = []
            for cat in ["daily", "digitalassets", "ideas", "etfs"]:
                cat_stocks = await StockService.get_stocks_by_category(
                    db=db,
                    category=cat,
                    active_only=active_only,
                    limit=limit // 4
                )
                all_stocks.extend(cat_stocks)
            
            stocks = all_stocks[:limit]
        
        return [Stock.from_orm(stock) for stock in stocks]
        
    except Exception as e:
        logger.error(f"Error getting stocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-category/{category}", response_model=List[Stock])
async def get_stocks_by_category(
    category: str,
    active_only: bool = Query(True, description="Only active stocks"),
    limit: int = Query(100, description="Maximum results", ge=1, le=500),
    db: AsyncSession = Depends(get_database)
) -> List[Stock]:
    """
    Get stocks by specific category.
    
    Args:
        category: Stock category
        active_only: Only return active stocks
        limit: Maximum number of results
        db: Database session
        
    Returns:
        List of stocks in category
    """
    valid_categories = ["daily", "digitalassets", "ideas", "etfs"]
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category: {category}. Valid categories: {valid_categories}"
        )
    
    try:
        stocks = await StockService.get_stocks_by_category(
            db=db,
            category=category,
            active_only=active_only,
            limit=limit
        )
        
        return [Stock.from_orm(stock) for stock in stocks]
        
    except Exception as e:
        logger.error(f"Error getting stocks by category {category}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ticker/{ticker}")
async def get_stock_by_ticker(
    ticker: str,
    category: Optional[str] = Query(None, description="Specific category to search"),
    db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Get stock by ticker symbol.
    
    Args:
        ticker: Stock ticker symbol
        category: Specific category to search in
        db: Database session
        
    Returns:
        Stock data or list if multiple categories
    """
    try:
        if category:
            stock = await StockService.get_stock_by_ticker_and_category(
                db=db,
                ticker=ticker.upper(),
                category=category
            )
            
            if not stock:
                raise HTTPException(
                    status_code=404,
                    detail=f"Stock {ticker} not found in category {category}"
                )
            
            return Stock.from_orm(stock).dict()
        else:
            # Search all categories
            stocks = []
            for cat in ["daily", "digitalassets", "ideas", "etfs"]:
                stock = await StockService.get_stock_by_ticker_and_category(
                    db=db,
                    ticker=ticker.upper(),
                    category=cat
                )
                if stock:
                    stock_data = Stock.from_orm(stock).dict()
                    stocks.append(stock_data)
            
            if not stocks:
                raise HTTPException(
                    status_code=404,
                    detail=f"Stock {ticker} not found in any category"
                )
            
            return {
                'ticker': ticker.upper(),
                'found_in_categories': len(stocks),
                'stocks': stocks
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stock {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_stocks_for_alerts(
    session: Optional[str] = Query(None, description="Trading session (AM/PM)"),
    db: AsyncSession = Depends(get_database)
) -> List[Dict[str, Any]]:
    """
    Get stocks that should trigger alerts.
    
    Args:
        session: Filter by trading session
        db: Database session
        
    Returns:
        List of stocks ready for alerts
    """
    try:
        stocks = await StockService.get_stocks_for_alerts(db, session=session)
        
        alert_stocks = []
        for stock in stocks:
            stock_data = Stock.from_orm(stock).dict()
            
            # Add alert information
            alert_info = {
                'should_alert_buy': stock.should_alert_buy,
                'should_alert_sell': stock.should_alert_sell,
                'current_price': stock.current_price,
                'price_vs_buy': stock.price_vs_buy_threshold,
                'price_vs_sell': stock.price_vs_sell_threshold
            }
            
            stock_data.update(alert_info)
            alert_stocks.append(stock_data)
        
        return alert_stocks
        
    except Exception as e:
        logger.error(f"Error getting stocks for alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/need-updates")
async def get_stocks_needing_updates(
    db: AsyncSession = Depends(get_database)
) -> List[Dict[str, Any]]:
    """
    Get stocks that need price updates.
    
    Args:
        db: Database session
        
    Returns:
        List of stocks needing price updates
    """
    try:
        stocks = await StockService.get_stocks_needing_price_updates(db)
        
        return [
            {
                'id': stock.id,
                'ticker': stock.ticker,
                'category': stock.category,
                'name': stock.name,
                'last_price_update': stock.last_price_update.isoformat() if stock.last_price_update else None,
                'am_price': stock.am_price,
                'pm_price': stock.pm_price,
                'buy_trade': stock.buy_trade,
                'sell_trade': stock.sell_trade
            }
            for stock in stocks
        ]
        
    except Exception as e:
        logger.error(f"Error getting stocks needing updates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{stock_id}/update-price")
async def update_stock_price(
    stock_id: int,
    am_price: Optional[float] = Query(None, description="AM session price"),
    pm_price: Optional[float] = Query(None, description="PM session price"),
    db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Update stock price manually.
    
    Args:
        stock_id: Stock ID
        am_price: AM session price
        pm_price: PM session price
        db: Database session
        
    Returns:
        Updated stock data
    """
    if not am_price and not pm_price:
        raise HTTPException(
            status_code=400,
            detail="At least one price (am_price or pm_price) must be provided"
        )
    
    try:
        update_data = StockUpdate()
        if am_price is not None:
            update_data.am_price = am_price
        if pm_price is not None:
            update_data.pm_price = pm_price
        
        stock = await StockService.update_stock(db, stock_id, update_data)
        
        if not stock:
            raise HTTPException(status_code=404, detail=f"Stock {stock_id} not found")
        
        return Stock.from_orm(stock).dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating stock price {stock_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stock_statistics(
    db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Get stock statistics by category.
    
    Args:
        db: Database session
        
    Returns:
        Stock statistics
    """
    try:
        stats = {
            'by_category': {},
            'total_active': 0,
            'total_all': 0,
            'with_prices': 0,
            'need_updates': 0,
            'ready_for_alerts': 0
        }
        
        # Count by category
        for category in ["daily", "digitalassets", "ideas", "etfs"]:
            active_stocks = await StockService.get_stocks_by_category(
                db=db, category=category, active_only=True, limit=1000
            )
            all_stocks = await StockService.get_stocks_by_category(
                db=db, category=category, active_only=False, limit=1000
            )
            
            stats['by_category'][category] = {
                'active': len(active_stocks),
                'total': len(all_stocks),
                'with_prices': len([s for s in active_stocks if s.current_price]),
                'with_thresholds': len([s for s in active_stocks if s.buy_trade or s.sell_trade])
            }
            
            stats['total_active'] += len(active_stocks)
            stats['total_all'] += len(all_stocks)
            stats['with_prices'] += stats['by_category'][category]['with_prices']
        
        # Get stocks needing updates
        needs_updates = await StockService.get_stocks_needing_price_updates(db)
        stats['need_updates'] = len(needs_updates)
        
        # Get stocks ready for alerts
        alert_ready = await StockService.get_stocks_for_alerts(db)
        stats['ready_for_alerts'] = len(alert_ready)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting stock statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))