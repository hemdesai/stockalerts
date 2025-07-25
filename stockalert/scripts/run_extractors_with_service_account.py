#!/usr/bin/env python
"""Run extractors using service account credentials"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
import base64
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from stockalert.utils.env_loader import get_env
# Import extractors using file path approach
sys.path.append(str(Path(__file__).parent / '0_extractors'))
from crypto_extractor import CryptoEmailExtractor
from ideas_extractor import IdeasEmailExtractor

class ServiceAccountGmailExtractor:
    """Gmail extractor using service account"""
    
    def __init__(self):
        self.service_account_path = Path(__file__).parent.parent / 'credentials' / 'service_account.json'
        self.SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
        self.gmail_service = self.setup_gmail()
        
    def setup_gmail(self):
        """Setup Gmail service using service account"""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                str(self.service_account_path),
                scopes=self.SCOPES
            )
            
            # For Gmail API, service accounts need domain-wide delegation
            # We'll need to impersonate a user email
            user_email = get_env('EMAIL_SENDER', 'hemdesai@gmail.com')
            delegated_credentials = credentials.with_subject(user_email)
            
            service = build('gmail', 'v1', credentials=delegated_credentials)
            print(f"Gmail service initialized with service account for {user_email}")
            return service
        except Exception as e:
            print(f"Error setting up Gmail with service account: {e}")
            return None
    
    def get_email_attachments(self, query):
        """Get attachments from email matching query"""
        try:
            response = self.gmail_service.users().messages().list(
                userId='me', q=query, maxResults=1
            ).execute()
            
            messages = response.get('messages', [])
            if not messages:
                print(f"No emails found for query: {query}")
                return []
            
            msg_id = messages[0]['id']
            message = self.gmail_service.users().messages().get(
                userId='me', id=msg_id
            ).execute()
            
            parts = message['payload'].get('parts', [])
            attachments = []
            
            for part in parts:
                if part.get('filename'):
                    attachment_id = part['body'].get('attachmentId')
                    if attachment_id:
                        attachment = self.gmail_service.users().messages().attachments().get(
                            userId='me', messageId=msg_id, id=attachment_id
                        ).execute()
                        file_data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))
                        attachments.append({
                            'filename': part['filename'],
                            'data': file_data
                        })
            
            print(f"Found {len(attachments)} attachments")
            return attachments
        except Exception as e:
            print(f"Error getting attachments: {e}")
            return []

def extract_crypto_with_service_account():
    """Extract crypto data using service account"""
    print("\n" + "="*60)
    print("Extracting Crypto Data with Service Account")
    print("="*60)
    
    try:
        extractor = ServiceAccountGmailExtractor()
        if not extractor.gmail_service:
            print("Failed to initialize Gmail service")
            return
        
        # Search for today's crypto email
        today = datetime.now().strftime('%Y/%m/%d')
        query = f'subject:"FW: CRYPTO QUANT" after:{today}'
        print(f"Searching for crypto email: {query}")
        
        attachments = extractor.get_email_attachments(query)
        
        if not attachments:
            # Try yesterday
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y/%m/%d')
            query = f'subject:"FW: CRYPTO QUANT" after:{yesterday}'
            print(f"Trying yesterday: {query}")
            attachments = extractor.get_email_attachments(query)
        
        if attachments:
            # Process the attachments using the crypto extractor's image processing
            crypto_extractor = CryptoEmailExtractor()
            crypto_assets = []
            
            for i, att in enumerate(attachments):
                if att['filename'].lower().endswith('.png'):
                    print(f"Processing {att['filename']}...")
                    assets = crypto_extractor.process_image(att['data'])
                    crypto_assets.extend(assets)
            
            if crypto_assets:
                # Save to CSV
                df = pd.DataFrame(crypto_assets)
                csv_path = Path(__file__).parent.parent / 'data' / 'digitalassets.csv'
                df.to_csv(csv_path, index=False)
                print(f"Saved {len(crypto_assets)} crypto assets to {csv_path}")
            else:
                print("No crypto assets extracted")
        else:
            print("No crypto emails found")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def extract_ideas_with_service_account():
    """Extract ideas data using service account"""
    print("\n" + "="*60)
    print("Extracting Ideas Data with Service Account")
    print("="*60)
    
    try:
        extractor = ServiceAccountGmailExtractor()
        if not extractor.gmail_service:
            print("Failed to initialize Gmail service")
            return
        
        # Search for this week's ideas email
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y/%m/%d')
        query = f'subject:"FW: Investing Ideas Newsletter:" after:{seven_days_ago}'
        print(f"Searching for ideas email: {query}")
        
        attachments = extractor.get_email_attachments(query)
        
        if attachments:
            # Process the first PNG attachment
            ideas_extractor = IdeasEmailExtractor()
            
            for att in attachments:
                if att['filename'].lower().endswith('.png'):
                    print(f"Processing {att['filename']}...")
                    
                    # Save temporarily and process
                    temp_path = Path(__file__).parent.parent / 'data' / 'temp_ideas.png'
                    with open(temp_path, 'wb') as f:
                        f.write(att['data'])
                    
                    ideas_data = ideas_extractor.process_image(str(temp_path))
                    
                    # Clean up
                    if temp_path.exists():
                        os.remove(temp_path)
                    
                    if ideas_data:
                        print(f"Extracted {len(ideas_data)} ideas")
                        # The process_image method already saves to CSV
                    else:
                        print("No ideas extracted")
                    break
        else:
            print("No ideas emails found")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("Stock Alert Service Account Extractor")
    print("="*60)
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if service account exists
    service_account_path = Path(__file__).parent.parent / 'credentials' / 'service_account.json'
    if not service_account_path.exists():
        print(f"Error: Service account not found at {service_account_path}")
        return
    
    print(f"Using service account: {service_account_path}")
    
    # Extract crypto data
    extract_crypto_with_service_account()
    
    # Extract ideas data
    extract_ideas_with_service_account()
    
    print("\n" + "="*60)
    print("Extraction Complete")
    print("="*60)

if __name__ == "__main__":
    main()