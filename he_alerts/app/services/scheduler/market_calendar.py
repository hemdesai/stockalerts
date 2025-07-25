"""
Market calendar with US holiday awareness.
"""
from datetime import datetime, date, timedelta
from typing import List, Optional
import holidays
from app.core.logging import get_logger

logger = get_logger(__name__)


class MarketCalendar:
    """Handles market holidays and business day calculations."""
    
    def __init__(self):
        # Initialize US market holidays
        self.us_holidays = holidays.UnitedStates(years=range(2024, 2030))
        
        # Add market-specific holidays
        self._add_market_holidays()
    
    def _add_market_holidays(self):
        """Add NYSE/NASDAQ specific holiday rules."""
        current_year = datetime.now().year
        
        for year in range(current_year, current_year + 5):
            # Good Friday (Friday before Easter)
            easter = holidays.easter(year)
            good_friday = easter - timedelta(days=2)
            self.us_holidays.append({good_friday: "Good Friday"})
            
            # Handle special cases where market closes
            # If July 4th falls on Saturday, market closes Friday
            july_4 = date(year, 7, 4)
            if july_4.weekday() == 5:  # Saturday
                self.us_holidays.append({july_4 - timedelta(days=1): "Independence Day (Observed)"})
            elif july_4.weekday() == 6:  # Sunday
                self.us_holidays.append({july_4 + timedelta(days=1): "Independence Day (Observed)"})
            
            # Christmas Eve - early close (but we'll treat as closed for safety)
            dec_24 = date(year, 12, 24)
            if dec_24.weekday() < 5:  # Weekday
                self.us_holidays.append({dec_24: "Christmas Eve"})
    
    def is_market_open(self, check_date: Optional[date] = None) -> bool:
        """Check if market is open on given date."""
        if check_date is None:
            check_date = date.today()
        
        # Market closed on weekends
        if check_date.weekday() >= 5:
            return False
        
        # Market closed on holidays
        if check_date in self.us_holidays:
            logger.info(f"Market closed on {check_date}: {self.us_holidays.get(check_date)}")
            return False
        
        return True
    
    def get_next_market_day(self, from_date: Optional[date] = None) -> date:
        """Get next market open day."""
        if from_date is None:
            from_date = date.today()
        
        next_day = from_date
        while True:
            next_day += timedelta(days=1)
            if self.is_market_open(next_day):
                return next_day
    
    def get_previous_market_day(self, from_date: Optional[date] = None) -> date:
        """Get previous market open day."""
        if from_date is None:
            from_date = date.today()
        
        prev_day = from_date
        while True:
            prev_day -= timedelta(days=1)
            if self.is_market_open(prev_day):
                return prev_day
    
    def is_first_market_day_of_week(self, check_date: Optional[date] = None) -> bool:
        """Check if this is the first market day of the week."""
        if check_date is None:
            check_date = date.today()
        
        if not self.is_market_open(check_date):
            return False
        
        # Get start of week (Monday)
        start_of_week = check_date - timedelta(days=check_date.weekday())
        
        # Find first market day of this week
        current = start_of_week
        while current <= check_date:
            if self.is_market_open(current):
                return current == check_date
            current += timedelta(days=1)
        
        return False
    
    def get_market_holidays(self, year: int) -> List[tuple]:
        """Get list of market holidays for a given year."""
        holidays_list = []
        for holiday_date, holiday_name in sorted(self.us_holidays.items()):
            if holiday_date.year == year:
                holidays_list.append((holiday_date, holiday_name))
        return holidays_list