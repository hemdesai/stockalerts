"""Export all stocks to CSV file."""
import asyncio
import csv
from datetime import datetime
from pathlib import Path

from app.core.database import AsyncSessionLocal
from sqlalchemy import text


async def export_stocks_to_csv():
    async with AsyncSessionLocal() as db:
        # Get all active stocks
        result = await db.execute(
            text("""
                SELECT 
                    id, ticker, name, category, sentiment, 
                    buy_trade, sell_trade, am_price, pm_price, 
                    last_price_update, ibkr_contract, ibkr_contract_resolved,
                    source_email_id, is_active, last_alert_sent,
                    created_at, updated_at, extraction_metadata
                FROM stocks 
                WHERE is_active = true
                ORDER BY category, ticker
            """)
        )
        stocks = result.fetchall()
        
        # Create CSV file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stocks_db_export_{timestamp}.csv"
        filepath = Path(__file__).parent / filename
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'id', 'ticker', 'name', 'category', 'sentiment', 
                'buy_trade', 'sell_trade', 'am_price', 'pm_price', 
                'last_price_update', 'ibkr_contract', 'ibkr_contract_resolved',
                'source_email_id', 'is_active', 'last_alert_sent',
                'created_at', 'updated_at', 'extraction_metadata'
            ])
            
            # Write data
            for stock in stocks:
                writer.writerow([
                    stock.id, stock.ticker, stock.name, stock.category, stock.sentiment,
                    stock.buy_trade, stock.sell_trade, stock.am_price, stock.pm_price,
                    stock.last_price_update, stock.ibkr_contract, stock.ibkr_contract_resolved,
                    stock.source_email_id, stock.is_active, stock.last_alert_sent,
                    stock.created_at, stock.updated_at, stock.extraction_metadata
                ])
        
        print(f"Exported {len(stocks)} stocks to {filename}")
        
        # Print summary by category
        categories = {}
        for stock in stocks:
            cat = stock.category
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += 1
        
        print("\nSummary by category:")
        for cat, count in sorted(categories.items()):
            print(f"  {cat}: {count}")
        print(f"  Total: {len(stocks)}")
        
        return filepath


if __name__ == "__main__":
    asyncio.run(export_stocks_to_csv())