"""
Test script to manually run IBKR price updates.
"""
import asyncio
import sys
from datetime import datetime
import pytz

from app.core.database import AsyncSessionLocal
from app.services.ibkr.price_fetcher import PriceFetcher
from app.services.database.alert_service import AlertService


async def test_price_update(session_type: str = "AM"):
    """Test price update functionality."""
    print(f"\n{'='*60}")
    print(f"Testing {session_type} Price Update")
    print(f"{'='*60}")
    
    # Get current time in ET
    et_tz = pytz.timezone('America/New_York')
    current_time = datetime.now(et_tz).strftime('%Y-%m-%d %H:%M:%S ET')
    print(f"Current time: {current_time}")
    
    price_fetcher = PriceFetcher()
    alert_service = AlertService()
    
    try:
        async with AsyncSessionLocal() as db:
            # Run price update
            print(f"\nFetching prices from IBKR...")
            result = await price_fetcher.update_stock_prices(db, session_type)
            
            print(f"\n{session_type} Price Update Results:")
            print(f"- Total stocks: {result['total_stocks']}")
            print(f"- Successfully updated: {result['updated_count']}")
            print(f"- Alerts triggered: {len(result['alerts'])}")
            
            # Display alerts
            if result['alerts']:
                print(f"\nPrice Alerts:")
                print("-" * 60)
                for alert in result['alerts']:
                    print(
                        f"{alert['type']} Alert: {alert['ticker']} "
                        f"at ${alert['price']:.2f} "
                        f"(threshold: ${alert['threshold']:.2f}, "
                        f"sentiment: {alert['sentiment']})"
                    )
                
                # Process alerts
                await alert_service.process_price_alerts(db, result['alerts'])
                print("\nAlerts have been logged to database.")
            
            # Show recent alerts
            print(f"\nRecent Alerts (last 10):")
            print("-" * 60)
            recent_alerts = await alert_service.get_recent_alerts(db, limit=10)
            
            if recent_alerts:
                for alert in recent_alerts:
                    print(
                        f"{alert.created_at.strftime('%Y-%m-%d %H:%M')} - "
                        f"{alert.alert_type} {alert.ticker} at ${alert.price:.2f}"
                    )
            else:
                print("No recent alerts found.")
            
    except Exception as e:
        print(f"\nError during price update: {e}")
        import traceback
        traceback.print_exc()


async def test_single_ticker(ticker: str):
    """Test fetching price for a single ticker."""
    print(f"\n{'='*60}")
    print(f"Testing Single Ticker: {ticker}")
    print(f"{'='*60}")
    
    price_fetcher = PriceFetcher()
    
    try:
        price = await price_fetcher.get_single_price(ticker)
        
        if price:
            print(f"{ticker}: ${price:.2f}")
        else:
            print(f"Failed to get price for {ticker}")
            
    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")


async def show_stocks_needing_prices():
    """Show stocks that need price updates."""
    print(f"\n{'='*60}")
    print(f"Stocks Needing Price Updates")
    print(f"{'='*60}")
    
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            from app.models.stock import Stock
            
            # Get stocks without prices
            result = await db.execute(
                select(Stock)
                .where(Stock.is_active == True)
                .where((Stock.am_price == None) | (Stock.pm_price == None))
                .order_by(Stock.category, Stock.ticker)
            )
            stocks = result.scalars().all()
            
            if stocks:
                print(f"\nFound {len(stocks)} stocks without prices:")
                print("-" * 60)
                current_category = None
                
                for stock in stocks:
                    if stock.category != current_category:
                        current_category = stock.category
                        print(f"\n{current_category.upper()}:")
                    
                    am_status = "✓" if stock.am_price else "✗"
                    pm_status = "✓" if stock.pm_price else "✗"
                    
                    am_price_str = f"${stock.am_price:.2f}" if stock.am_price else "N/A"
                    pm_price_str = f"${stock.pm_price:.2f}" if stock.pm_price else "N/A"
                    
                    print(
                        f"  {stock.ticker:<8} AM: {am_status} ({am_price_str}) | "
                        f"PM: {pm_status} ({pm_price_str})"
                    )
            else:
                print("All active stocks have prices!")
                
    except Exception as e:
        print(f"Error checking stocks: {e}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_price_update.py AM|PM     - Run AM or PM price update")
        print("  python test_price_update.py ticker SYMBOL - Get price for single ticker")
        print("  python test_price_update.py check     - Show stocks needing prices")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command in ['am', 'pm']:
        asyncio.run(test_price_update(command.upper()))
    elif command == 'ticker' and len(sys.argv) > 2:
        ticker = sys.argv[2].upper()
        asyncio.run(test_single_ticker(ticker))
    elif command == 'check':
        asyncio.run(show_stocks_needing_prices())
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()