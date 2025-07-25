"""
Update the database with corrected crypto values and export CSV.
"""
import asyncio
from datetime import datetime
import pandas as pd
from app.core.database import AsyncSessionLocal
from app.services.database.stock_service import StockService

# Correct crypto values from extraction
CORRECT_CRYPTO_DATA = {
    'BTC': {'buy': 114852.00, 'sell': 120467.00, 'sentiment': 'bullish'},
    'ETH': {'buy': 3455.00, 'sell': 3896.00, 'sentiment': 'bullish'},
    'SOL': {'buy': 170.00, 'sell': 205.00, 'sentiment': 'bullish'},
    'AVAX': {'buy': 22.50, 'sell': 26.07, 'sentiment': 'bullish'},
    'AAVE': {'buy': 283.00, 'sell': 338.00, 'sentiment': 'bullish'},
    'IBIT': {'buy': 65.22, 'sell': 69.00, 'sentiment': 'bullish'},
    'MSTR': {'buy': 401.00, 'sell': 460.00, 'sentiment': 'bullish'},
    'MARA': {'buy': 17.01, 'sell': 20.44, 'sentiment': 'bullish'},
    'RIOT': {'buy': 12.97, 'sell': 15.48, 'sentiment': 'bullish'},
    'COIN': {'buy': 381.00, 'sell': 424.00, 'sentiment': 'bullish'},
    'BITO': {'buy': 22.01, 'sell': 25.52, 'sentiment': 'bullish'},
    'ETHA': {'buy': 22.99, 'sell': 30.39, 'sentiment': 'bullish'},
    'BLOK': {'buy': 58.41, 'sell': 62.90, 'sentiment': 'bullish'}
}

async def update_crypto_stocks():
    """Update crypto stocks with correct values."""
    async with AsyncSessionLocal() as db:
        stock_service = StockService()
        
        print("Updating crypto stocks with correct values...")
        print("="*60)
        
        for ticker, data in CORRECT_CRYPTO_DATA.items():
            # Get the stock
            stock = await stock_service.get_stock_by_ticker_and_category(db, ticker, 'digitalassets')
            
            if stock:
                # Update the stock
                stock.buy_trade = data['buy']
                stock.sell_trade = data['sell']
                stock.sentiment = data['sentiment']
                stock.updated_at = datetime.utcnow()
                
                print(f"Updated {ticker}: Buy=${data['buy']:,.2f}, Sell=${data['sell']:,.2f}, {data['sentiment']}")
            else:
                print(f"Warning: {ticker} not found in database")
        
        # Commit all updates
        await db.commit()
        print("\n[OK] All crypto stocks updated successfully")


async def export_updated_csv():
    """Export updated database to CSV."""
    async with AsyncSessionLocal() as db:
        stock_service = StockService()
        
        # Get all stocks by category
        all_stocks = []
        for category in ['daily', 'digitalassets', 'etfs', 'ideas']:
            stocks = await stock_service.get_stocks_by_category(db, category, active_only=False, limit=1000)
            all_stocks.extend(stocks)
        
        # Convert to DataFrame
        data = []
        for stock in all_stocks:
            data.append({
                'ticker': stock.ticker,
                'name': stock.name,
                'category': stock.category,
                'sentiment': stock.sentiment,
                'buy_trade': stock.buy_trade,
                'sell_trade': stock.sell_trade,
                'am_price': stock.am_price,
                'pm_price': stock.pm_price,
                'last_price_update': stock.last_price_update,
                'source_email_id': stock.source_email_id,
                'is_active': stock.is_active,
                'created_at': stock.created_at,
                'updated_at': stock.updated_at
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values(['category', 'ticker'])
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'stocks_corrected_{timestamp}.csv'
        
        # Export
        df.to_csv(filename, index=False)
        print(f"\n[OK] Exported {len(df)} stocks to {filename}")
        
        # Show summary
        print("\nCategory Summary:")
        for category, count in df['category'].value_counts().items():
            print(f"  {category}: {count} stocks")
            
        # Show active counts
        print("\nActive Stocks by Category:")
        active_df = df[df['is_active'] == True]
        for category, count in active_df['category'].value_counts().items():
            print(f"  {category}: {count} active stocks")
        
        # Show crypto stocks with new values
        print("\nCorrected Crypto Stocks:")
        crypto_df = df[df['category'] == 'digitalassets'].sort_values('ticker')
        print(f"{'Ticker':8} {'Sentiment':10} {'Buy':>12} {'Sell':>12} {'Active'}")
        print("-"*60)
        for _, row in crypto_df.iterrows():
            print(f"{row['ticker']:8} {row['sentiment']:10} ${row['buy_trade']:>11,.2f} ${row['sell_trade']:>11,.2f} {str(row['is_active']):>6}")
        
        return filename


async def main():
    """Main function."""
    # Update crypto stocks
    await update_crypto_stocks()
    
    # Export CSV
    csv_file = await export_updated_csv()
    
    print(f"\n{'='*60}")
    print("Update Complete!")
    print(f"CSV file: {csv_file}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())