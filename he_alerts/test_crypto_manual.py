"""
Manually test crypto email extraction to see what's wrong.
"""
import asyncio
from app.services.email.gmail_client import GmailClient
from app.services.email.extractors.crypto import CryptoExtractor

async def test_crypto_extraction():
    """Test crypto extraction manually."""
    gmail_client = GmailClient()
    crypto_extractor = CryptoExtractor()
    
    # Authenticate
    if not await gmail_client.authenticate():
        print("Failed to authenticate")
        return
    
    print("Authenticated successfully")
    
    # Get latest crypto email
    recent_emails = await gmail_client.fetch_recent_emails(hours=48)
    crypto_emails = [e for e in recent_emails if e.get('email_type') == 'crypto']
    
    if not crypto_emails:
        print("No crypto emails found")
        return
    
    latest_crypto = crypto_emails[0]
    print(f"\nProcessing crypto email: {latest_crypto['message_id']}")
    print(f"Subject: {latest_crypto['subject'].encode('ascii', 'replace').decode('ascii')}")
    
    # Extract directly using the extractor
    result = await crypto_extractor.extract_from_email_id(latest_crypto['message_id'])
    
    if result:
        items = result.get('extracted_items', [])
        print(f"\nExtracted {len(items)} items")
        
        # Group by type
        cryptos = []
        stocks = []
        
        for item in items:
            if item['ticker'] in ['BTC', 'ETH', 'SOL', 'AVAX', 'AAVE']:
                cryptos.append(item)
            else:
                stocks.append(item)
        
        if cryptos:
            print("\nCRYPTOCURRENCIES:")
            print("-" * 50)
            for item in sorted(cryptos, key=lambda x: x['ticker']):
                print(f"{item['ticker']:8} {item['sentiment']:10} Buy: ${item['buy_trade']:>10.2f}  Sell: ${item['sell_trade']:>10.2f}")
        
        if stocks:
            print("\nDERIVATIVE EXPOSURES (Crypto Stocks):")
            print("-" * 50) 
            for item in sorted(stocks, key=lambda x: x['ticker']):
                print(f"{item['ticker']:8} {item['sentiment']:10} Buy: ${item['buy_trade']:>10.2f}  Sell: ${item['sell_trade']:>10.2f}")
    else:
        print("No extraction result")

if __name__ == "__main__":
    asyncio.run(test_crypto_extraction())