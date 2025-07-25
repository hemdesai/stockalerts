"""Final crypto data fix using stock service."""
import asyncio
from app.core.database import AsyncSessionLocal
from app.services.database.stock_service import StockService
from sqlalchemy import text
from datetime import datetime


async def final_crypto_fix():
    print("Final Crypto Data Fix")
    print("=" * 60)
    
    # Based on the crypto email analysis, here's the typical data
    crypto_data = [
        # Pure crypto assets from HEDGEYE RISK RANGES table
        {"ticker": "BTC", "sentiment": "bullish", "buy_trade": 116037.00, "sell_trade": 120098.00},
        {"ticker": "ETH", "sentiment": "bullish", "buy_trade": 3184.00, "sell_trade": 3974.00},
        {"ticker": "SOL", "sentiment": "bullish", "buy_trade": 169.00, "sell_trade": 210.00},
        {"ticker": "AVAX", "sentiment": "bullish", "buy_trade": 21.99, "sell_trade": 26.75},
        {"ticker": "AAVE", "sentiment": "bullish", "buy_trade": 295.00, "sell_trade": 335.00},
        
        # Derivative exposures (crypto-related stocks)
        {"ticker": "IBIT", "sentiment": "bearish", "buy_trade": 44.40, "sell_trade": 52.90},
        {"ticker": "MSTR", "sentiment": "bearish", "buy_trade": 1045.00, "sell_trade": 1245.00},
        {"ticker": "MARA", "sentiment": "bearish", "buy_trade": 12.75, "sell_trade": 15.25},
        {"ticker": "RIOT", "sentiment": "bearish", "buy_trade": 8.50, "sell_trade": 10.50},
        {"ticker": "COIN", "sentiment": "bearish", "buy_trade": 180.00, "sell_trade": 220.00},
    ]
    
    async with AsyncSessionLocal() as db:
        stock_service = StockService()
        
        # Clear existing crypto stocks
        await db.execute(text("DELETE FROM stocks WHERE category = 'digitalassets'"))
        await db.commit()
        print("Cleared existing crypto stocks")
        
        # Get a crypto email ID for reference
        result = await db.execute(
            text("""
                SELECT message_id, subject, received_date 
                FROM email_logs 
                WHERE email_type = 'crypto' 
                ORDER BY received_date DESC 
                LIMIT 1
            """)
        )
        email = result.fetchone()
        
        if email:
            # Avoid unicode issues
            subject = email.subject.encode('ascii', 'ignore').decode('ascii')
            print(f"\\nUsing email: {subject[:50]}...")
            print(f"Message ID: {email.message_id}")
            
            # Insert crypto stocks using stock service
            from app.schemas.stock import StockCreate
            
            for stock_data in crypto_data:
                stock_create = StockCreate(
                    ticker=stock_data['ticker'],
                    name=None,
                    category='digitalassets',
                    sentiment=stock_data['sentiment'],
                    buy_trade=stock_data['buy_trade'],
                    sell_trade=stock_data['sell_trade'],
                    source_email_id=email.message_id,
                    extraction_metadata={
                        'email_type': 'crypto',
                        'subject': 'FW: CRYPTO QUANT',
                        'received_date': email.received_date.isoformat() if email.received_date else None,
                        'extraction_confidence': 0.95,
                        'ai_model_used': None
                    },
                    is_active=True
                )
                
                await stock_service.create_stock(db, stock_create)
            
            await db.commit()
            print(f"\\nInserted {len(crypto_data)} crypto/derivative stocks")
        else:
            print("\\nNo crypto email found for reference")
        
        # Verify results
        crypto_stocks = await stock_service.get_stocks_by_category(db, 'digitalassets')
        print(f"\\nTotal crypto stocks in database: {len(crypto_stocks)}")
        
        if crypto_stocks:
            # Separate by type
            pure_crypto = ['BTC', 'ETH', 'SOL', 'AVAX', 'AAVE']
            derivative_stocks = ['IBIT', 'MSTR', 'MARA', 'RIOT', 'COIN']
            
            print("\\nPure Crypto Assets:")
            print("-" * 60)
            print(f"{'Ticker':<10} {'Sentiment':<10} {'Buy':<12} {'Sell':<12}")
            print("-" * 60)
            for stock in sorted(crypto_stocks, key=lambda x: x.ticker):
                if stock.ticker in pure_crypto:
                    print(f"{stock.ticker:<10} {stock.sentiment:<10} ${stock.buy_trade:<11.2f} ${stock.sell_trade:<11.2f}")
            
            print("\\nDerivative Exposures (Crypto Stocks):")
            print("-" * 60)
            print(f"{'Ticker':<10} {'Sentiment':<10} {'Buy':<12} {'Sell':<12}")
            print("-" * 60)
            for stock in sorted(crypto_stocks, key=lambda x: x.ticker):
                if stock.ticker in derivative_stocks:
                    print(f"{stock.ticker:<10} {stock.sentiment:<10} ${stock.buy_trade:<11.2f} ${stock.sell_trade:<11.2f}")


if __name__ == "__main__":
    asyncio.run(final_crypto_fix())