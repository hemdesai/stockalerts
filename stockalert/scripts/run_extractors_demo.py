#!/usr/bin/env python
"""Demo script showing the extractors would update the CSV files"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def main():
    print("Stock Alert Extractors Demo")
    print("="*60)
    print("\nNOTE: This demo shows how the extractors would work.")
    print("Actual execution requires:")
    print("1. MCP server running (python scripts/1_mcp_server.py)")
    print("2. Gmail credentials configured")
    print("3. Mistral API key in environment")
    
    print("\n" + "="*60)
    print("CRYPTO EXTRACTOR (Daily)")
    print("="*60)
    
    print("\nWhen running crypto_extractor.py:")
    print("1. Searches Gmail for: subject:\"FW: CRYPTO QUANT\" after:today")
    print("2. Extracts 2 PNG attachments from the email")
    print("3. Processes images with Mistral OCR")
    print("4. Parses crypto data (BTC, ETH, SOL, etc.)")
    print("5. Saves to: stockalert/data/digitalassets.csv")
    
    print("\nExpected CSV format:")
    print("ticker,sentiment,buy_trade,sell_trade,category")
    print("BTC-USD,BULLISH,80012.0,93968.0,digitalassets")
    print("ETH-USD,BEARISH,3200.0,3800.0,digitalassets")
    print("SOL-USD,BULLISH,150.0,180.0,digitalassets")
    
    print("\n" + "="*60)
    print("IDEAS EXTRACTOR (Weekly - Monday)")
    print("="*60)
    
    print("\nWhen running ideas_extractor.py:")
    print("1. Searches Gmail for: subject:\"FW: Investing Ideas Newsletter:\" after:last_7_days")
    print("2. Extracts 1 PNG attachment from the email")
    print("3. Processes image with Mistral OCR")
    print("4. Parses stock ideas (Longs and Shorts)")
    print("5. Saves to: stockalert/data/ideas.csv")
    
    print("\nExpected CSV format:")
    print("ticker,sentiment,buy_trade,sell_trade,category")
    print("AAPL,BULLISH,175.50,195.00,ideas")
    print("MSFT,BULLISH,420.00,450.00,ideas")
    print("TSLA,BEARISH,250.00,220.00,ideas")
    
    print("\n" + "="*60)
    print("VERIFICATION")
    print("="*60)
    
    # Check current CSV files
    data_dir = Path(__file__).parent.parent / 'data'
    
    print("\nChecking existing CSV files:")
    
    # Check digitalassets.csv
    digitalassets_csv = data_dir / 'digitalassets.csv'
    if digitalassets_csv.exists():
        print(f"\n✓ {digitalassets_csv} exists")
        with open(digitalassets_csv, 'r') as f:
            lines = f.readlines()
            print(f"  Current rows: {len(lines) - 1}")  # -1 for header
            if len(lines) > 1:
                print("  Sample data:")
                for line in lines[:4]:  # Header + 3 rows
                    print(f"    {line.strip()}")
    else:
        print(f"\n✗ {digitalassets_csv} not found")
    
    # Check ideas.csv
    ideas_csv = data_dir / 'ideas.csv'
    if ideas_csv.exists():
        print(f"\n✓ {ideas_csv} exists")
        with open(ideas_csv, 'r') as f:
            lines = f.readlines()
            print(f"  Current rows: {len(lines) - 1}")  # -1 for header
            if len(lines) > 1:
                print("  Sample data:")
                for line in lines[:4]:  # Header + 3 rows
                    print(f"    {line.strip()}")
    else:
        print(f"\n✗ {ideas_csv} not found")
    
    print("\n" + "="*60)
    print("To run the extractors and update CSV files:")
    print("1. Start MCP server: python scripts/1_mcp_server.py")
    print("2. Run crypto extractor: python scripts/0_extractors/crypto_extractor.py")
    print("3. Run ideas extractor: python scripts/0_extractors/ideas_extractor.py")
    print("="*60)

if __name__ == "__main__":
    main()