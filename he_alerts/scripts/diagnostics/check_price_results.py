"""Check price update results."""
import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import select, func
from app.models.stock import Stock


async def check_prices():
    async with AsyncSessionLocal() as db:
        # Count stocks with prices
        am_count = await db.scalar(
            select(func.count(Stock.id))
            .where(Stock.is_active == True)
            .where(Stock.am_price != None)
        )
        
        pm_count = await db.scalar(
            select(func.count(Stock.id))
            .where(Stock.is_active == True)
            .where(Stock.pm_price != None)
        )
        
        total = await db.scalar(
            select(func.count(Stock.id))
            .where(Stock.is_active == True)
        )
        
        print(f"Price Update Status:")
        print(f"- Total active stocks: {total}")
        print(f"- Stocks with AM prices: {am_count} ({am_count/total*100:.1f}%)")
        print(f"- Stocks with PM prices: {pm_count} ({pm_count/total*100:.1f}%)")
        
        # Show some samples
        result = await db.execute(
            select(Stock)
            .where(Stock.is_active == True)
            .where(Stock.am_price != None)
            .limit(10)
        )
        stocks = result.scalars().all()
        
        if stocks:
            print("\nSample stocks with AM prices:")
            print("-" * 50)
            for stock in stocks:
                print(f"{stock.ticker:<8} AM: ${stock.am_price:>8.2f}  Buy: ${stock.buy_trade:>8.2f}  Sell: ${stock.sell_trade:>8.2f}")


if __name__ == "__main__":
    asyncio.run(check_prices())