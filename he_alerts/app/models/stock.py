"""
Stock model for storing financial instruments and trading data.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Float, DateTime, Text, Boolean, Index
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModel


class Stock(BaseModel):
    """
    Model for storing stock/financial instrument data.
    
    Based on the original SQLite schema with enhancements for PostgreSQL.
    """
    __tablename__ = "stocks"
    
    # Core identification
    ticker = Column(String(20), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    category = Column(String(50), nullable=False, index=True)  # daily, ideas, etfs, digitalassets
    
    # Trading data
    sentiment = Column(String(20), nullable=True)  # bullish, bearish, neutral
    buy_trade = Column(Float, nullable=True)
    sell_trade = Column(Float, nullable=True)
    
    # Price data
    am_price = Column(Float, nullable=True)
    pm_price = Column(Float, nullable=True)
    last_price_update = Column(DateTime, nullable=True)
    
    # IBKR integration
    ibkr_contract = Column(Text, nullable=True)  # Serialized contract data
    ibkr_contract_resolved = Column(Boolean, default=False, nullable=False)
    
    # Metadata
    source_email_id = Column(String(255), nullable=True)  # Gmail message ID
    extraction_metadata = Column(JSONB, nullable=True)  # AI extraction details
    
    # Status tracking
    is_active = Column(Boolean, default=True, nullable=False)
    last_alert_sent = Column(DateTime, nullable=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_stock_ticker_category', 'ticker', 'category'),
        Index('idx_stock_active_category', 'is_active', 'category'),
        Index('idx_stock_price_update', 'last_price_update'),
        Index('idx_stock_alert_sent', 'last_alert_sent'),
    )
    
    def __repr__(self) -> str:
        return f"<Stock(ticker={self.ticker}, category={self.category}, sentiment={self.sentiment})>"
    
    @property
    def current_price(self) -> Optional[float]:
        """Get the most recent price (AM or PM)."""
        if self.pm_price:
            return self.pm_price
        return self.am_price
    
    @property
    def price_vs_buy_threshold(self) -> Optional[float]:
        """Calculate price difference from buy threshold."""
        if not self.current_price or not self.buy_trade:
            return None
        return self.current_price - self.buy_trade
    
    @property
    def price_vs_sell_threshold(self) -> Optional[float]:
        """Calculate price difference from sell threshold."""
        if not self.current_price or not self.sell_trade:
            return None
        return self.current_price - self.sell_trade
    
    @property
    def should_alert_buy(self) -> bool:
        """Check if stock should trigger a buy alert."""
        if not self.is_active or not self.current_price or not self.buy_trade:
            return False
        return self.current_price <= self.buy_trade
    
    @property
    def should_alert_sell(self) -> bool:
        """Check if stock should trigger a sell alert."""
        if not self.is_active or not self.current_price or not self.sell_trade:
            return False
        return self.current_price >= self.sell_trade