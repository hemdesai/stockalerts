"""Verify IDEAS prices after fix."""
import asyncio
from app.core.database import AsyncSessionLocal
from app.services.database.stock_service import StockService


async def verify_ideas():
    async with AsyncSessionLocal() as db:
        service = StockService()
        ideas = await service.get_stocks_by_category(db, 'ideas')
        
        print('IDEAS STOCK PRICES AFTER FIX:')
        print('-' * 60)
        print(f'{"Ticker":<8} {"Sentiment":<10} {"Buy Price":<12} {"Sell Price":<12}')
        print('-' * 60)
        
        for s in sorted(ideas, key=lambda x: x.ticker):
            print(f'{s.ticker:<8} {s.sentiment:<10} ${s.buy_trade:<11.2f} ${s.sell_trade:<11.2f}')
        
        # Check for generic prices
        generic = [s for s in ideas if s.buy_trade == 200.0 and s.sell_trade == 250.0]
        print(f'\nStocks with generic $200/$250: {len(generic)}')
        
        # Show correct extractions
        correct = {
            'DKNG': (41.42, 45.66),
            'CELH': (43.03, 46.56),
            'XYL': (128.00, 136.00),
            'COIN': (355.00, 431.00),
            'IVT': (26.40, 27.44),
            'GAP': (19.04, 23.01),
            'AMN': (18.09, 22.01)
        }
        
        print('\nValidation of key stocks:')
        matches = 0
        for ticker, (exp_buy, exp_sell) in correct.items():
            stock = next((s for s in ideas if s.ticker == ticker), None)
            if stock:
                buy_ok = abs(stock.buy_trade - exp_buy) < 0.01
                sell_ok = abs(stock.sell_trade - exp_sell) < 0.01
                if buy_ok and sell_ok:
                    matches += 1
                    print(f'  {ticker}: OK')
                else:
                    print(f'  {ticker}: Expected ${exp_buy}/${exp_sell}, got ${stock.buy_trade}/${stock.sell_trade}')
        
        print(f'\nCorrectly extracted: {matches}/{len(correct)}')


if __name__ == "__main__":
    asyncio.run(verify_ideas())