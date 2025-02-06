import os
import sqlite3
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def test_code():
    try:
        # Get the absolute path to the project root directory
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Path to your credentials file
        credentials_path = os.path.join(current_dir, 'service_account.json')
        
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"Credentials file not found at: {credentials_path}")
        
        # Setup credentials using gspread
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
        client = gspread.authorize(creds)
        
        # Initialize SQLite database
        db_path = os.path.join(current_dir, 'data', 'stocks.db')
        conn = sqlite3.connect(db_path)
        
        print("Successfully connected to Google Sheets and SQLite!")
        
        conn.close()
    except Exception as e:
        print(f"Error: {str(e)}")
        print(f"Looking for credentials at: {credentials_path}")

if __name__ == "__main__":
    test_code()