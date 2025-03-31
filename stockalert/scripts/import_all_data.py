import os
from pathlib import Path
import logging
from datetime import datetime
import pandas as pd
from stockalert.scripts.db_manager import StockAlertDBManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=Path(__file__).parent.parent / 'data' / 'data_import.log',
    filemode='a'
)
logger = logging.getLogger('import_all_data')

def import_all_data(force_update=False, skip_name_updates=True):
    """
    Import all CSV data into the database
    
    Args:
        force_update (bool): If True, update all categories regardless of update frequency
        skip_name_updates (bool): If True, skip updating ticker names to avoid rate limiting
                                 Default is True to avoid yfinance API calls
    """
    # Log start of import process
    logger.info(f"Starting data import process at {datetime.now().isoformat()}")
    
    # Initialize the database manager
    db_manager = StockAlertDBManager()
    
    # Define the CSV files and their categories
    project_root = Path(__file__).parent.parent
    data_dir = project_root / 'data'
    
    csv_files = [
        {'path': data_dir / 'ideas.csv', 'category': 'ideas'},
        {'path': data_dir / 'digitalassets.csv', 'category': 'digitalassets'},
        {'path': data_dir / 'etfs.csv', 'category': 'etfs'},
        {'path': data_dir / 'daily.csv', 'category': 'daily'}
    ]
    
    # Import each CSV file if it needs updating
    results = {}
    
    for csv_file in csv_files:
        category = csv_file['category']
        file_path = csv_file['path']
        
        # Check if this category needs to be updated
        should_update = force_update or db_manager.should_update_category(category, file_path)
        
        if os.path.exists(file_path) and should_update:
            logger.info(f"Updating category: {category} from {file_path}")
            print(f"Updating {category} from {file_path}...")
            
            # Delete existing data for this category
            delete_result = db_manager.delete_category_data(category)
            if delete_result['success']:
                logger.info(f"Deleted {delete_result['deleted_count']} records for {category}")
                print(f"  Deleted {delete_result['deleted_count']} records for {category}")
            else:
                logger.error(f"Error deleting data for {category}: {delete_result['error']}")
                print(f"  Error deleting data for {category}: {delete_result['error']}")
            
            # Import the CSV data without validation
            try:
                # Read the CSV file
                df = pd.read_csv(file_path)
                
                # Connect to the database
                conn = db_manager.connect()
                
                # Insert the data directly without validation
                if 'ticker' in df.columns:
                    # Ensure all column names are lowercase with underscores
                    df.columns = [col.lower().replace(' ', '_') for col in df.columns]
                    
                    # Add category column if not already present
                    if 'category' not in df.columns:
                        df['category'] = category
                    
                    # Insert into database
                    df.to_sql('stocks', conn, if_exists='append', index=False)
                    
                    # Record success
                    imported_count = len(df)
                    result = {
                        'success': True,
                        'imported_count': imported_count,
                        'error_count': 0,
                        'validation_errors': []
                    }
                    
                    logger.info(f"Imported {imported_count} records for {category}")
                    print(f"  Imported {imported_count} records")
                else:
                    error_msg = f"CSV file for {category} does not have a 'ticker' column"
                    logger.error(error_msg)
                    print(f"  Error: {error_msg}")
                    result = {
                        'success': False,
                        'error': error_msg
                    }
                
                # Update the log to record this update
                db_manager._update_log(category, file_path)
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error importing data for {category}: {error_msg}")
                print(f"  Error: {error_msg}")
                result = {
                    'success': False,
                    'error': error_msg
                }
                
            results[category] = result
            
        else:
            if not os.path.exists(file_path):
                logger.warning(f"CSV file not found: {file_path}")
                print(f"CSV file not found: {file_path}")
            else:
                logger.info(f"Skipping {category} - no update needed based on frequency and file modification time")
                print(f"Skipping {category} - no update needed")
    
    # Log completion of import process
    logger.info(f"Completed data import process at {datetime.now().isoformat()}")
    
    return results

if __name__ == "__main__":
    # Check for command line arguments
    import sys
    force_update = "--force" in sys.argv
    skip_name_updates = True  # Always skip name updates to avoid yfinance API calls
    
    if force_update:
        print("Forcing update of all categories regardless of update frequency")
    
    print("Skipping ticker name updates to avoid yfinance API calls")
    
    # Run the import process
    import_all_data(force_update=force_update, skip_name_updates=skip_name_updates)
    
    print("Import process completed")
