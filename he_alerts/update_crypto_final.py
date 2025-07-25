"""Update crypto data with correct values from cryptostocks.png."""
import asyncio
from app.core.database import AsyncSessionLocal
from app.services.database.stock_service import StockService
from app.schemas.stock import StockCreate
from sqlalchemy import text


async def update_crypto_data_final():
    print("Updating Crypto Data with Correct Values from cryptostocks.png")
    print("=" * 60)
    
    # Based on the cryptostocks.png image - DIRECT & DERIVATIVE EXPOSURES table
    crypto_derivative_stocks = [
        {"ticker": "IBIT", "sentiment": "bullish", "buy_trade": 65.19, "sell_trade": 69.17},
        {"ticker": "MSTR", "sentiment": "bullish", "buy_trade": 405.00, "sell_trade": 465.00},
        {"ticker": "MARA", "sentiment": "bullish", "buy_trade": 17.11, "sell_trade": 20.40},
        {"ticker": "RIOT", "sentiment": "bullish", "buy_trade": 11.97, "sell_trade": 14.97},
        {"ticker": "ETHA", "sentiment": "bullish", "buy_trade": 22.49, "sell_trade": 29.86},
        {"ticker": "BLOK", "sentiment": "bullish", "buy_trade": 58.21, "sell_trade": 62.91},
        {"ticker": "COIN", "sentiment": "bullish", "buy_trade": 378.00, "sell_trade": 425.00},
        {"ticker": "BITO", "sentiment": "bullish", "buy_trade": 22.03, "sell_trade": 23.51},
    ]
    
    # Pure crypto from HEDGEYE RISK RANGES (from BTC_2.png)
    pure_crypto = [
        {"ticker": "BTC", "sentiment": "bullish", "buy_trade": 116612.00, "sell_trade": 120218.00},
        {"ticker": "ETH", "sentiment": "bullish", "buy_trade": 3353.00, "sell_trade": 3924.00},
        {"ticker": "SOL", "sentiment": "bullish", "buy_trade": 171.00, "sell_trade": 205.00},
        {"ticker": "AVAX", "sentiment": "bullish", "buy_trade": 22.28, "sell_trade": 26.01},
        {"ticker": "AAVE", "sentiment": "bullish", "buy_trade": 287.00, "sell_trade": 337.00},
    ]
    
    async with AsyncSessionLocal() as db:
        stock_service = StockService()
        
        # Clear existing crypto stocks
        await db.execute(text("DELETE FROM stocks WHERE category = 'digitalassets'"))
        await db.commit()
        print("Cleared existing crypto stocks")
        
        # Get crypto email reference
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
        
        if not email:
            print("No crypto email found")
            return
        
        print(f"Using email: {email.message_id}")
        
        # Insert all crypto data
        all_crypto = pure_crypto + crypto_derivative_stocks
        
        for stock_data in all_crypto:
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
                    'ai_model_used': None,
                    'table_source': 'risk_ranges' if stock_data['ticker'] in ['BTC', 'ETH', 'SOL', 'AVAX', 'AAVE'] else 'derivative_exposures'
                },
                is_active=True
            )
            
            await stock_service.create_stock(db, stock_create)
        
        await db.commit()
        print(f"\\nInserted {len(all_crypto)} crypto assets and derivative stocks")
        
        # Verify results
        crypto_stocks = await stock_service.get_stocks_by_category(db, 'digitalassets')
        
        print(f"\\nTotal crypto stocks in database: {len(crypto_stocks)}")
        
        # Display by type
        print("\\nPure Crypto Assets (from HEDGEYE RISK RANGES):")
        print("-" * 70)
        print(f"{'Ticker':<8} {'Sentiment':<10} {'Buy':<12} {'Sell':<12}")
        print("-" * 70)
        for stock in sorted(crypto_stocks, key=lambda x: x.ticker):
            if stock.ticker in ['BTC', 'ETH', 'SOL', 'AVAX', 'AAVE']:
                print(f"{stock.ticker:<8} {stock.sentiment:<10} ${stock.buy_trade:<11.2f} ${stock.sell_trade:<11.2f}")
        
        print("\\nDerivative Exposures (Crypto-Related Stocks):")
        print("-" * 70)
        print(f"{'Ticker':<8} {'Sentiment':<10} {'Buy':<12} {'Sell':<12}")
        print("-" * 70)
        for stock in sorted(crypto_stocks, key=lambda x: x.ticker):
            if stock.ticker not in ['BTC', 'ETH', 'SOL', 'AVAX', 'AAVE']:
                print(f"{stock.ticker:<8} {stock.sentiment:<10} ${stock.buy_trade:<11.2f} ${stock.sell_trade:<11.2f}")


if __name__ == "__main__":
    asyncio.run(update_crypto_data_final())