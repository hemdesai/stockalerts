import os
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv # type: ignore
import sqlite3
from pathlib import Path
from datetime import datetime

# Load environment variables
load_dotenv()

def setup_google_sheets():
    """Setup Google Sheets connection"""
    try:
        # Get the absolute path to the project root directory
        root_dir = Path(__file__).parent.parent
        credentials_path = root_dir / 'service_account.json'
        
        print(f"Looking for credentials at: {credentials_path}")  # Debug line
        
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"Credentials file not found at: {credentials_path}")
        
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            str(credentials_path),
            scope
        )
        client = gspread.authorize(credentials)
        print("Successfully connected to Google Sheets")
        return client
    except Exception as e:
        print(f"Error setting up Google Sheets connection: {e}")
        return None

def process_dataframe(df, category):
    """Process the dataframe to ensure correct data types"""
    try:
        # Debug print before processing
        print(f"\nProcessing {category} worksheet:")
        print("Columns:", df.columns.tolist())
        
        # Convert numeric columns
        numeric_columns = ['Buy Trade', 'Sell Trade']
        for col in numeric_columns:
            # Check if column exists
            if col not in df.columns:
                print(f"Warning: {col} column not found in {category} worksheet")
                continue
            
            # Convert to numeric and show any errors
            df[col] = pd.to_numeric(df[col], errors='coerce')
            null_count = df[col].isnull().sum()
            if null_count > 0:
                print(f"Warning: {null_count} NULL values in {col} for {category}")
        
        # Ensure Sentiment is uppercase
        df['Sentiment'] = df['Sentiment'].str.upper()
        
        # Add category column
        df['Category'] = category
        
        # Debug print after processing
        print("Sample data after processing:")
        print(df[['Ticker', 'Buy Trade', 'Sell Trade']].head())
        
        return df
    except Exception as e:
        print(f"Error processing dataframe: {e}")
        return df

def get_sheet_data(worksheet_name):
    """Get data from specific worksheet"""
    try:
        client = setup_google_sheets()
        if not client:
            return None
            
        sheet_name = os.getenv('SHEET_NAME', 'Stock Trading Signals')
        workbook = client.open(sheet_name)
        worksheet = workbook.worksheet(worksheet_name)
        
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            print(f"No data found in worksheet: {worksheet_name}")
            return None
            
        # Process the dataframe with category
        df = process_dataframe(df, worksheet_name)
        
        print(f"Successfully retrieved {len(df)} rows from {worksheet_name}")
        return df
    except Exception as e:
        print(f"Error fetching data from {worksheet_name}: {e}")
        return None

def save_to_sqlite(df):
    """Save DataFrame to SQLite database"""
    try:
        root_dir = Path(__file__).parent.parent
        db_path = root_dir / 'data' / 'stocks.db'
        db_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Database path: {db_path}")
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # First, delete all existing records
        try:
            cursor.execute("DELETE FROM stocks")
            deleted_count = cursor.rowcount
            print(f"Deleted {deleted_count} existing records from stocks table")
        except sqlite3.OperationalError:
            print("Table doesn't exist yet, will create new")
        

        # Save with specific data types
        df.to_sql(
            'stocks', 
            conn, 
            if_exists='replace',  
            index=False,
            dtype={
                'Category': 'TEXT',
                'Ticker': 'TEXT',
                'Sentiment': 'TEXT',
                'Name': 'TEXT',
                'Buy Trade': 'FLOAT',
                'Sell Trade': 'FLOAT',                
            }
        )
        
        # Get the count of inserted records
        cursor.execute("SELECT COUNT(*) FROM stocks")
        inserted_count = cursor.fetchone()[0]
        print(f"Successfully inserted {inserted_count} records into stocks table")
        

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving to database: {e}")

def process_all_sheets():
    """Process all worksheets"""
    worksheets = ['daily', 'ideas', 'etfs', 'digitalassets']
    
    all_data = []
    success_count = 0
    
    for worksheet_name in worksheets:
        print(f"\nProcessing worksheet: {worksheet_name}")
        df = get_sheet_data(worksheet_name)
        if df is not None and not df.empty:
            all_data.append(df)
            success_count += 1
        else:
            print(f"Skipping {worksheet_name} due to empty or invalid data")
    
    if all_data:
        # Combine all dataframes
        combined_df = pd.concat(all_data, ignore_index=True)
        save_to_sqlite(combined_df)
    
    return success_count

def main():
    print("Starting data pipeline...")
    success_count = process_all_sheets()
    print(f"\nData pipeline completed. Successfully processed {success_count} out of 4 sheets.")

if __name__ == "__main__":
    main()
