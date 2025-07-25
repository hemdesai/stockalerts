"""Test ETF sentiment parsing fix."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.email_processor import EmailProcessor
from app.core.database import AsyncSessionLocal


async def test_etf_sentiment():
    print('=' * 60)
    print('TESTING ETF SENTIMENT PARSING FIX')
    print('=' * 60)
    
    async with AsyncSessionLocal() as db:
        processor = EmailProcessor()
        
        # Process ETF emails
        results = await processor.process_recent_emails(
            db=db,
            email_types=['etf'],
            hours=168  # 7 days
        )
        
        # Check the results
        for result in results:
            extracted_items = result.get('extracted_items', [])
            print(f"\nExtracted {len(extracted_items)} ETF items:")
            
            sentiment_counts = {'bullish': 0, 'bearish': 0, 'neutral': 0}
            
            for item in extracted_items:
                sentiment = item.get('sentiment', 'unknown')
                ticker = item.get('ticker', 'UNKNOWN')
                buy_trade = item.get('buy_trade', 0)
                sell_trade = item.get('sell_trade', 0)
                
                sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
                print(f"  {ticker}: {sentiment} - Buy: {buy_trade}, Sell: {sell_trade}")
            
            print(f"\nSentiment Summary:")
            for sentiment, count in sentiment_counts.items():
                print(f"  {sentiment}: {count}")
            
            # Success if we found both bullish and bearish sentiments
            success = sentiment_counts.get('bullish', 0) > 0 and sentiment_counts.get('bearish', 0) > 0
            print(f"\nFix successful: {success}")
            if success:
                print("✅ BULLISH and BEARISH sections detected correctly!")
            else:
                print("❌ Still not detecting sentiment sections properly")


if __name__ == "__main__":
    asyncio.run(test_etf_sentiment())