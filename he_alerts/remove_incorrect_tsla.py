"""
Remove incorrect TSLA from ideas category.
"""
import asyncio
from app.core.database import AsyncSessionLocal
from app.services.database.stock_service import StockService

async def remove_incorrect_tsla():
    async with AsyncSessionLocal() as db:
        stock_service = StockService()
        
        # Get TSLA from ideas category
        tsla_ideas = await stock_service.get_stock_by_ticker_and_category(db, 'TSLA', 'ideas')
        
        if tsla_ideas:
            print(f'Found TSLA in ideas: Buy=${tsla_ideas.buy_trade}, Sell=${tsla_ideas.sell_trade}')
            print('Removing incorrect TSLA from ideas category...')
            
            # Delete the incorrect entry
            await db.delete(tsla_ideas)
            await db.commit()
            print('Successfully removed incorrect TSLA from ideas')
        else:
            print('No TSLA found in ideas category')
        
        # Check if TSLA exists in other categories
        all_tsla = await stock_service.search_stocks(db, 'TSLA')
        print(f'\nRemaining TSLA entries: {len(all_tsla)}')
        for stock in all_tsla:
            print(f'  - {stock.ticker} in {stock.category}: Buy=${stock.buy_trade}, Sell=${stock.sell_trade}')

if __name__ == "__main__":
    asyncio.run(remove_incorrect_tsla())