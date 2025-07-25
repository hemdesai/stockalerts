#!/usr/bin/env python
"""
Helper script to guide through OAuth2 credentials creation
"""

import json
from pathlib import Path

def main():
    print("Gmail OAuth2 Credentials Setup Helper")
    print("="*60)
    
    print("\nTo create OAuth2 credentials for Gmail access:")
    print("\n1. Go to: https://console.cloud.google.com/")
    print("2. Select project: stockalert-444519 (or create new)")
    print("3. Enable Gmail API if not already enabled")
    print("4. Create OAuth 2.0 Client ID (Desktop type)")
    print("5. Download the credentials JSON file")
    print("6. Save it in this directory (keep the original filename)")
    
    print("\n" + "="*60)
    print("Current Status:")
    
    creds_path = Path(__file__).parent / 'credentials.json'
    token_path = Path(__file__).parent / 'token.json'
    
    if creds_path.exists():
        print("✓ credentials.json found")
    else:
        print("✗ credentials.json NOT FOUND - You need to create this")
        
    if token_path.exists():
        print("✓ token.json found (authentication token)")
    else:
        print("✗ token.json not found (will be created on first run)")
    
    print("\n" + "="*60)
    print("\nOnce you have credentials.json, run:")
    print("python scripts/0_extractors/crypto_extractor.py")
    print("python scripts/0_extractors/ideas_extractor.py")
    print("\nThe first run will open a browser for authentication.")

if __name__ == "__main__":
    main()