1. #!/usr/bin/env python
"""Test script to verify email extractors are working correctly"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from stockalert.scripts.0_extractors.crypto_extractor import CryptoEmailExtractor
from stockalert.scripts.0_extractors.ideas_extractor import IdeasEmailExtractor
from stockalert.scripts.0_extractors.etf_extractor import ETFEmailExtractor

def test_crypto_extractor():
    print("\n" + "="*60)
    print("Testing Crypto Email Extractor")
    print("="*60)
    
    try:
        extractor = CryptoEmailExtractor()
        crypto_data = extractor.extract()
        
        if crypto_data:
            print(f"\nSuccessfully extracted {len(crypto_data)} crypto assets")
            print("\nSample data (first 3 assets):")
            for i, asset in enumerate(crypto_data[:3]):
                print(f"  {i+1}. {asset}")
        else:
            print("\nNo crypto data extracted")
            
    except Exception as e:
        print(f"\nError testing crypto extractor: {e}")
        import traceback
        traceback.print_exc()

def test_ideas_extractor():
    print("\n" + "="*60)
    print("Testing Ideas Email Extractor")
    print("="*60)
    
    try:
        extractor = IdeasEmailExtractor()
        ideas_data = extractor.extract()
        
        if ideas_data:
            print(f"\nSuccessfully extracted {len(ideas_data)} ideas")
            print("\nSample data (first 3 ideas):")
            for i, idea in enumerate(ideas_data[:3]):
                print(f"  {i+1}. {idea}")
        else:
            print("\nNo ideas data extracted")
            
    except Exception as e:
        print(f"\nError testing ideas extractor: {e}")
        import traceback
        traceback.print_exc()

def test_etf_extractor():
    print("\n" + "="*60)
    print("Testing ETF Email Extractor")
    print("="*60)
    
    try:
        extractor = ETFEmailExtractor()
        etf_data = extractor.extract()
        
        if etf_data:
            print(f"\nSuccessfully extracted {len(etf_data)} ETF assets")
            print("\nSample data (first 3 ETFs):")
            for i, etf in enumerate(etf_data[:3]):
                print(f"  {i+1}. {etf}")
        else:
            print("\nNo ETF data extracted")
            
    except Exception as e:
        print(f"\nError testing ETF extractor: {e}")
        import traceback
        traceback.print_exc()

def main():
    print(f"Starting extractor tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test all extractors
    test_crypto_extractor()
    test_ideas_extractor()
    test_etf_extractor()
    
    print("\n" + "="*60)
    print("Testing completed")
    print("="*60)
    
    # Check if CSV files were created
    data_dir = Path(__file__).parent.parent / 'data'
    csv_files = {
        'digitalassets.csv': 'Crypto assets',
        'ideas.csv': 'Ideas',
        'etfs.csv': 'ETFs'
    }
    
    print("\nChecking CSV files:")
    for csv_file, description in csv_files.items():
        csv_path = data_dir / csv_file
        if csv_path.exists():
            print(f"  ✓ {csv_file} exists - {description}")
        else:
            print(f"  ✗ {csv_file} missing - {description}")

if __name__ == "__main__":
    main()