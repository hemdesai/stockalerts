"""Check all stocks in database grouped by category."""
import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import text


async def check_all_stocks():
    async with AsyncSessionLocal() as db:
        # Get counts by category
        result = await db.execute(
            text("""
                SELECT category, COUNT(*) as count 
                FROM stocks 
                WHERE is_active = true
                GROUP BY category
                ORDER BY category
            """)
        )
        counts = result.fetchall()
        
        print("Stock counts by category:")
        print("-" * 40)
        total = 0
        for cat in counts:
            print(f"{cat.category:<15} {cat.count:>5}")
            total += cat.count
        print("-" * 40)
        print(f"{'TOTAL':<15} {total:>5}")
        
        # Get crypto/digital assets details
        print("\nDigital Assets Details:")
        print("-" * 80)
        result = await db.execute(
            text("""
                SELECT ticker, sentiment, buy_trade, sell_trade, created_at 
                FROM stocks 
                WHERE category = 'digitalassets' AND is_active = true
                ORDER BY ticker
            """)
        )
        crypto = result.fetchall()
        
        if crypto:
            print(f"{'Ticker':<10} {'Sentiment':<10} {'Buy':<12} {'Sell':<12} {'Created'}")
            print("-" * 80)
            for stock in crypto:
                print(f"{stock.ticker:<10} {stock.sentiment:<10} ${stock.buy_trade:<11.2f} ${stock.sell_trade:<11.2f} {stock.created_at}")
        else:
            print("No digital assets found")


if __name__ == "__main__":
    asyncio.run(check_all_stocks())