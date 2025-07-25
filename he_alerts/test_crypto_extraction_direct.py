"""Test crypto extraction directly."""
import asyncio
from app.services.email.extractors.crypto import CryptoExtractor
from app.core.database import AsyncSessionLocal
from app.services.database.stock_service import StockService


async def test_crypto_extraction():
    print("Testing Crypto Extraction...")
    print("=" * 60)
    
    async with AsyncSessionLocal() as db:
        # Clear existing crypto stocks first
        from sqlalchemy import text
        await db.execute(text("DELETE FROM stocks WHERE category = 'digitalassets'"))
        await db.commit()
        print("Cleared existing crypto stocks")
        
        # Extract crypto emails
        extractor = CryptoExtractor()
        results = await extractor.extract_from_recent_emails(hours=72)  # Last 3 days
        
        print(f"\nProcessed {len(results)} crypto emails")
        
        if results:
            # Process the first result
            result = results[0]
            items = result.get('extracted_items', [])
            email_data = result.get('email_data', {})
            
            print(f"\nExtracted {len(items)} items from email:")
            print(f"Subject: {email_data.get('subject')}")
            print(f"Date: {email_data.get('received_date')}")
            
            if items:
                print("\nExtracted items:")
                print("-" * 60)
                for item in items:
                    print(f"{item['ticker']:<10} {item.get('sentiment', 'N/A'):<10} "
                          f"Buy: ${item.get('buy_trade', 0):<10.2f} "
                          f"Sell: ${item.get('sell_trade', 0):<10.2f}")
                
                # Save to database
                stock_service = StockService()
                stock_data = extractor.prepare_stock_data(items, email_data)
                
                for stock in stock_data:
                    await stock_service.create_or_update_stock(db, stock)
                
                await db.commit()
                print(f"\nSaved {len(stock_data)} stocks to database")
            else:
                print("\nNo items extracted - crypto extraction may need debugging")
        else:
            print("\nNo crypto emails found")
        
        # Check final results
        crypto_stocks = await stock_service.get_stocks_by_category(db, 'digitalassets')
        print(f"\nFinal crypto stocks in database: {len(crypto_stocks)}")
        if crypto_stocks:
            for stock in sorted(crypto_stocks, key=lambda x: x.ticker):
                print(f"  {stock.ticker}: Buy=${stock.buy_trade:.2f}, Sell=${stock.sell_trade:.2f}")


if __name__ == "__main__":
    asyncio.run(test_crypto_extraction())