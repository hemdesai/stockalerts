import os
import sys
import pandas as pd
from pathlib import Path

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from scripts.email_extractors.etf_extractor import ETFEmailExtractor

def test_etf_extraction_from_gmail():
    """Test ETF extraction directly from Gmail"""
    print("\nRunning ETF Extraction from Gmail with Mistral OCR")
    
    # Initialize the ETF extractor
    extractor = ETFEmailExtractor()
    
    # Extract ETF data from Gmail
    etf_data = extractor.extract()
    
    if not etf_data:
        print("Failed to extract ETF data from Gmail")
        return
    
    # Print the extracted data
    print(f"\nExtracted {len(etf_data)} ETF records:")
    
    # Count sentiments
    bullish_count = 0
    bearish_count = 0
    
    for asset in etf_data:
        print(f"✓ {asset['ticker']:<6} {asset['sentiment']:<8} Buy: {asset['buy_trade']:8.2f}, Sell: {asset['sell_trade']:8.2f}")
        if asset['sentiment'] == 'BULLISH':
            bullish_count += 1
        elif asset['sentiment'] == 'BEARISH':
            bearish_count += 1
    
    print(f"\nSentiment Summary:")
    print(f"BULLISH: {bullish_count}")
    print(f"BEARISH: {bearish_count}")
    print("\nETF extraction from Gmail complete!")

if __name__ == "__main__":
    test_etf_extraction_from_gmail()