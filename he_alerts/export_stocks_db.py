"""Export all stocks from PostgreSQL database to CSV file."""
import asyncio
import csv
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.stock import Stock


async def export_stocks_to_csv():
    print("Exporting all stocks from PostgreSQL database to CSV...")
    
    async with AsyncSessionLocal() as db:
        # Get all stocks from database
        result = await db.execute(
            select(Stock).where(Stock.is_active == True).order_by(Stock.category, Stock.ticker)
        )
        stocks = result.scalars().all()
        
        if not stocks:
            print("No stocks found in database.")
            return
        
        # Create CSV file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"stocks_db_export_{timestamp}.csv"
        
        print(f"Found {len(stocks)} stocks. Writing to {csv_filename}...")
        
        # Define CSV headers
        headers = [
            'id',
            'ticker',
            'name',
            'category', 
            'sentiment',
            'buy_trade',
            'sell_trade',
            'am_price',
            'pm_price',
            'last_price_update',
            'ibkr_contract',
            'ibkr_contract_resolved',
            'source_email_id',
            'is_active',
            'last_alert_sent',
            'created_at',
            'updated_at',
            'extraction_metadata'
        ]
        
        # Write CSV file
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write headers
            writer.writerow(headers)
            
            # Write stock data
            for stock in stocks:
                row = [
                    stock.id,
                    stock.ticker,
                    stock.name or '',
                    stock.category,
                    stock.sentiment or '',
                    stock.buy_trade,
                    stock.sell_trade,
                    stock.am_price,
                    stock.pm_price,
                    stock.last_price_update.isoformat() if stock.last_price_update else '',
                    stock.ibkr_contract or '',
                    stock.ibkr_contract_resolved,
                    stock.source_email_id or '',
                    stock.is_active,
                    stock.last_alert_sent.isoformat() if stock.last_alert_sent else '',
                    stock.created_at.isoformat() if stock.created_at else '',
                    stock.updated_at.isoformat() if stock.updated_at else '',
                    str(stock.extraction_metadata) if stock.extraction_metadata else ''
                ]
                writer.writerow(row)
        
        print(f"Successfully exported {len(stocks)} stocks to {csv_filename}")
        
        # Print summary by category
        print("\nSUMMARY BY CATEGORY:")
        print("-" * 50)
        
        categories = {}
        for stock in stocks:
            cat = stock.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(stock)
        
        for category, cat_stocks in categories.items():
            print(f"{category.upper():<15}: {len(cat_stocks):>3} stocks")
            
            # Show first few tickers as sample
            sample_tickers = [s.ticker for s in cat_stocks[:5]]
            if len(cat_stocks) > 5:
                sample_tickers.append(f"... +{len(cat_stocks)-5} more")
            print(f"{'Sample tickers':<15}: {', '.join(sample_tickers)}")
            print()
        
        print(f"TOTAL: {len(stocks)} stocks")
        print(f"CSV file: {csv_filename}")


if __name__ == "__main__":
    asyncio.run(export_stocks_to_csv())