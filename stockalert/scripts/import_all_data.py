import os
from pathlib import Path
from db_manager import StockAlertDBManager

def import_all_data():
    """Import all CSV data into the database"""
    # Initialize the database manager
    db_manager = StockAlertDBManager()
    db_manager.initialize_database()
    
    # Define the CSV files and their categories
    project_root = Path(__file__).parent.parent
    data_dir = project_root / 'data'
    
    csv_files = [
        {'path': data_dir / 'ideas.csv', 'category': 'ideas'},
        {'path': data_dir / 'digitalassets.csv', 'category': 'digitalassets'},
        {'path': data_dir / 'etfs.csv', 'category': 'etfs'},
        {'path': data_dir / 'daily.csv', 'category': 'daily'}
    ]
    
    # Import each CSV file
    results = {}
    
    for csv_file in csv_files:
        if os.path.exists(csv_file['path']):
            print(f"Importing {csv_file['path']}...")
            result = db_manager.import_csv_data(csv_file['path'], csv_file['category'])
            results[csv_file['category']] = result
            
            if result['success']:
                print(f"  Imported {result['imported_count']} records")
                if result['error_count'] > 0:
                    print(f"  Encountered {result['error_count']} errors")
                    for error in result['validation_errors']:
                        print(f"    {error['ticker']}: {error['error']}")
            else:
                print(f"  Error: {result['error']}")
        else:
            print(f"CSV file not found: {csv_file['path']}")
    
    # Purge old data
    print("Purging old data...")
    purge_result = db_manager.purge_old_data(retention_days=30)
    if purge_result['success']:
        print(f"  Deleted {purge_result['deleted_count']} old records")
    else:
        print(f"  Error: {purge_result['error']}")
    
    return results

if __name__ == "__main__":
    import_all_data()
