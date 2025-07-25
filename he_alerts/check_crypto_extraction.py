"""Check crypto extraction results in detail."""
import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import text


async def check_crypto():
    async with AsyncSessionLocal() as db:
        # Check all stocks in database
        result = await db.execute(
            text("SELECT ticker, category, sentiment, buy_trade, sell_trade, created_at FROM stocks WHERE category = 'digitalassets' ORDER BY created_at DESC")
        )
        crypto_stocks = result.fetchall()
        
        print("Crypto stocks in database:")
        print("-" * 80)
        if crypto_stocks:
            for stock in crypto_stocks:
                print(f"{stock.ticker:<8} {stock.sentiment:<10} Buy: ${stock.buy_trade:<12.2f} Sell: ${stock.sell_trade:<12.2f} Created: {stock.created_at}")
        else:
            print("No crypto stocks found in database")
            
        # Check email logs for crypto emails
        print("\nCrypto email processing logs:")
        print("-" * 80)
        result = await db.execute(
            text("SELECT message_id, subject, processed, extraction_successful, extracted_count, created_at FROM email_logs WHERE email_type = 'crypto' ORDER BY created_at DESC LIMIT 5")
        )
        logs = result.fetchall()
        
        for log in logs:
            print(f"Email: {log.message_id}")
            print(f"  Subject: {log.subject}")
            print(f"  Processed: {log.processed}, Successful: {log.extraction_successful}, Extracted: {log.extracted_count}")
            print(f"  Created: {log.created_at}")
            print()


if __name__ == "__main__":
    asyncio.run(check_crypto())