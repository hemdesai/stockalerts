#!/usr/bin/env python
"""Verify Gmail setup and credentials"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from stockalert.utils.gmail_config import get_credentials_path, get_token_path
from stockalert.scripts.mcp_client import MCPClient

def main():
    print("Gmail Setup Verification")
    print("="*60)
    
    # Check credentials file
    creds_path = get_credentials_path()
    token_path = get_token_path()
    
    print(f"\nCredentials file: {creds_path}")
    if creds_path.exists():
        print("✓ Gmail OAuth2 credentials found")
    else:
        print("✗ Gmail OAuth2 credentials NOT FOUND")
        return
    
    print(f"\nToken file: {token_path}")
    if token_path.exists():
        print("✓ Authentication token found")
    else:
        print("✗ Authentication token not found (will be created on first use)")
    
    # Test MCP server connection
    print(f"\nTesting MCP server connection...")
    client = MCPClient()
    if client.check_connection():
        print("✓ MCP server is running and accessible")
        
        # Test a simple Gmail query
        print(f"\nTesting Gmail access...")
        try:
            # Try to get recent emails (any subject)
            content = client.get_email_content("is:unread", max_results=1)
            if content is not None:
                print("✓ Gmail API access is working")
                print(f"  Found email content ({len(content)} characters)")
            else:
                print("! No unread emails found (Gmail access appears to work)")
        except Exception as e:
            print(f"✗ Gmail API test failed: {e}")
    else:
        print("✗ MCP server is not accessible")
        print("  Make sure to run: python scripts/1_mcp_server.py")
    
    print(f"\n" + "="*60)
    print("Summary")
    print("="*60)
    
    if creds_path.exists() and client.check_connection():
        print("✓ Gmail setup is complete and working!")
        print("\nYou can now run the extractors:")
        print("  python scripts/0_extractors/crypto_extractor.py")
        print("  python scripts/0_extractors/ideas_extractor.py")
        print("  python scripts/0_extractors/etf_extractor.py")
        print("  python scripts/0_extractors/daily_extractor.py")
    else:
        print("✗ Gmail setup needs attention")
        if not creds_path.exists():
            print("  1. Download OAuth2 credentials from Google Cloud Console")
            print(f"  2. Save them as: {creds_path}")
        if not client.check_connection():
            print("  3. Start MCP server: python scripts/1_mcp_server.py")

if __name__ == "__main__":
    main()