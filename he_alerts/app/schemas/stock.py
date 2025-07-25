"""
Pydantic schemas for Stock model serialization and validation.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator


class StockBase(BaseModel):
    """Base schema for Stock with common fields."""
    ticker: str = Field(..., max_length=20, description="Stock ticker symbol")
    name: Optional[str] = Field(None, max_length=255, description="Company/instrument name")
    category: str = Field(..., max_length=50, description="Category: daily, ideas, etfs, digitalassets")
    sentiment: Optional[str] = Field(None, max_length=20, description="bullish, bearish, neutral")
    buy_trade: Optional[float] = Field(None, ge=0, description="Buy threshold price")
    sell_trade: Optional[float] = Field(None, ge=0, description="Sell threshold price")
    is_active: bool = Field(True, description="Whether stock is actively tracked")
    
    @validator('category')
    def validate_category(cls, v):
        allowed_categories = ['daily', 'ideas', 'etfs', 'digitalassets']
        if v not in allowed_categories:
            raise ValueError(f'Category must be one of: {allowed_categories}')
        return v
    
    @validator('sentiment')
    def validate_sentiment(cls, v):
        if v is not None:
            allowed_sentiments = ['bullish', 'bearish', 'neutral']
            if v not in allowed_sentiments:
                raise ValueError(f'Sentiment must be one of: {allowed_sentiments}')
        return v


class StockCreate(StockBase):
    """Schema for creating a new stock."""
    source_email_id: Optional[str] = Field(None, description="Gmail message ID")
    extraction_metadata: Optional[Dict[str, Any]] = Field(None, description="AI extraction details")


class StockUpdate(BaseModel):
    """Schema for updating a stock."""
    ticker: Optional[str] = Field(None, max_length=20)
    name: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=50)
    sentiment: Optional[str] = Field(None, max_length=20)
    buy_trade: Optional[float] = Field(None, ge=0)
    sell_trade: Optional[float] = Field(None, ge=0)
    am_price: Optional[float] = Field(None, ge=0)
    pm_price: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None
    ibkr_contract: Optional[str] = None
    ibkr_contract_resolved: Optional[bool] = None


class StockInDB(StockBase):
    """Schema representing stock as stored in database."""
    id: int
    am_price: Optional[float] = None
    pm_price: Optional[float] = None
    last_price_update: Optional[datetime] = None
    ibkr_contract: Optional[str] = None
    ibkr_contract_resolved: bool = False
    source_email_id: Optional[str] = None
    extraction_metadata: Optional[Dict[str, Any]] = None
    last_alert_sent: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class Stock(StockInDB):
    """Schema for returning stock data to clients."""
    current_price: Optional[float] = None
    price_vs_buy_threshold: Optional[float] = None
    price_vs_sell_threshold: Optional[float] = None
    should_alert_buy: bool = False
    should_alert_sell: bool = False
    
    class Config:
        from_attributes = True


class StockList(BaseModel):
    """Schema for paginated stock listings."""
    items: List[Stock]
    total: int
    page: int
    size: int
    pages: int


class StockBulkCreate(BaseModel):
    """Schema for bulk stock creation."""
    stocks: List[StockCreate]
    source_email_id: Optional[str] = None
    extraction_metadata: Optional[Dict[str, Any]] = None


class StockPriceUpdate(BaseModel):
    """Schema for updating stock prices."""
    ticker: str
    price: float
    session: str = Field(..., pattern="^(AM|PM)$")
    
    @validator('session')
    def validate_session(cls, v):
        if v not in ['AM', 'PM']:
            raise ValueError('Session must be AM or PM')
        return v


class StockBulkPriceUpdate(BaseModel):
    """Schema for bulk price updates."""
    updates: List[StockPriceUpdate]
    session: str = Field(..., pattern="^(AM|PM)$")