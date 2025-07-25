"""Test batch price update with just a few stocks."""
import asyncio
from app.core.database import AsyncSessionLocal
from app.services.ibkr.price_fetcher import PriceFetcher
from sqlalchemy import select
from app.models.stock import Stock


async def test_batch_update():
    print("Testing batch price update with daily stocks...")
    
    price_fetcher = PriceFetcher()
    
    async with AsyncSessionLocal() as db:
        # Get just the daily stocks (13 stocks)
        result = await db.execute(
            select(Stock)
            .where(Stock.is_active == True)
            .where(Stock.category == "daily")
        )
        stocks = result.scalars().all()
        
        print(f"Found {len(stocks)} daily stocks to update")
        
        # Connect once
        await price_fetcher.connect()
        
        updated = 0
        failed = 0
        
        for stock in stocks:
            try:
                print(f"\nProcessing {stock.ticker}...")
                
                # Resolve contract
                contract = await price_fetcher.resolve_and_store_contract(stock)
                if not contract:
                    print(f"  [FAIL] Failed to resolve contract")
                    failed += 1
                    continue
                
                # Fetch price
                price = await price_fetcher.fetch_price(contract)
                if price is None:
                    print(f"  [FAIL] No price available")
                    failed += 1
                    continue
                
                # Update in database
                stock.am_price = price
                from datetime import datetime
                stock.last_price_update = datetime.utcnow()
                
                print(f"  [OK] Price: ${price:.2f}")
                
                # Check alerts
                if stock.buy_trade and price <= stock.buy_trade:
                    print(f"  [BUY ALERT] Price ${price:.2f} <= Buy threshold ${stock.buy_trade:.2f}")
                if stock.sell_trade and price >= stock.sell_trade:
                    print(f"  [SELL ALERT] Price ${price:.2f} >= Sell threshold ${stock.sell_trade:.2f}")
                
                updated += 1
                
                # Small delay
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"  [ERROR] {e}")
                failed += 1
        
        # Disconnect
        await price_fetcher.disconnect()
        
        # Commit changes
        await db.commit()
        
        print(f"\n{'='*50}")
        print(f"Summary: {updated} updated, {failed} failed")
        
        # Verify updates
        result = await db.execute(
            select(Stock)
            .where(Stock.category == "daily")
            .where(Stock.am_price != None)
        )
        verified = result.scalars().all()
        
        print(f"Verified: {len(verified)} daily stocks have AM prices")
        
        if verified:
            print("\nUpdated stocks:")
            for stock in verified:
                print(f"  {stock.ticker:<6} ${stock.am_price:>8.2f}")


if __name__ == "__main__":
    asyncio.run(test_batch_update())