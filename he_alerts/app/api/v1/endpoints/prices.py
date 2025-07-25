"""
Price management API endpoints.
"""
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.services.ibkr.price_fetcher import PriceFetcher

router = APIRouter()


@router.post("/update/{session_type}")
async def update_prices(
    session_type: str,
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """
    Manually trigger a price update.
    
    Args:
        session_type: AM or PM
        db: Database session
        
    Returns:
        Update results including alerts
    """
    if session_type not in ["AM", "PM"]:
        raise HTTPException(status_code=400, detail="Session type must be AM or PM")
    
    price_fetcher = PriceFetcher()
    
    try:
        # Run price update
        result = await price_fetcher.update_stock_prices(db, session_type)
        
        return {
            "status": "success",
            "session": session_type,
            "updated_count": result['updated_count'],
            "total_stocks": result['total_stocks'],
            "alerts_count": len(result['alerts']),
            "alerts": result['alerts']
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Price update failed: {str(e)}")


@router.get("/ticker/{ticker}")
async def get_ticker_price(ticker: str) -> Dict:
    """
    Get current price for a single ticker.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Current price information
    """
    price_fetcher = PriceFetcher()
    
    try:
        price = await price_fetcher.get_single_price(ticker.upper())
        
        if price is None:
            raise HTTPException(status_code=404, detail=f"Price not found for {ticker}")
        
        return {
            "ticker": ticker.upper(),
            "price": price,
            "status": "success"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch price: {str(e)}")


@router.get("/status")
async def get_price_status(db: AsyncSession = Depends(get_db)) -> Dict:
    """
    Get price update status for all stocks.
    
    Args:
        db: Database session
        
    Returns:
        Summary of stocks with/without prices
    """
    from sqlalchemy import select, func
    from app.models.stock import Stock
    
    # Count stocks by price status
    total_stocks = await db.scalar(
        select(func.count(Stock.id)).where(Stock.is_active == True)
    )
    
    stocks_with_am_price = await db.scalar(
        select(func.count(Stock.id))
        .where(Stock.is_active == True)
        .where(Stock.am_price != None)
    )
    
    stocks_with_pm_price = await db.scalar(
        select(func.count(Stock.id))
        .where(Stock.is_active == True)
        .where(Stock.pm_price != None)
    )
    
    stocks_with_both = await db.scalar(
        select(func.count(Stock.id))
        .where(Stock.is_active == True)
        .where(Stock.am_price != None)
        .where(Stock.pm_price != None)
    )
    
    return {
        "total_active_stocks": total_stocks,
        "stocks_with_am_price": stocks_with_am_price,
        "stocks_with_pm_price": stocks_with_pm_price,
        "stocks_with_both_prices": stocks_with_both,
        "stocks_missing_am_price": total_stocks - stocks_with_am_price,
        "stocks_missing_pm_price": total_stocks - stocks_with_pm_price,
        "completion_percentage": {
            "am": round((stocks_with_am_price / total_stocks * 100), 2) if total_stocks > 0 else 0,
            "pm": round((stocks_with_pm_price / total_stocks * 100), 2) if total_stocks > 0 else 0
        }
    }