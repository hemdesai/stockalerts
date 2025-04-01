import os
import logging
from pathlib import Path
from datetime import datetime, timedelta
import pytz
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=Path(__file__).parent.parent / 'data' / 'data_import.log',
    filemode='a'
)
logger = logging.getLogger('import_all_data')

def import_category_data(category, file_path):
    """Import data for a specific category"""
    try:
        df = pd.read_csv(file_path)
        logger.info(f"Successfully imported {len(df)} records for {category}")
        return True
    except Exception as e:
        logger.error(f"Error importing {category} data: {str(e)}")
        return False

def main(force_update=False):
    """Import all data from CSV files"""
    logger.info("Starting data import...")
    
    # Define categories and their update frequencies
    categories = {
        'daily': 1,  # Daily update
        'ideas': 7,  # Weekly update
        'etfs': 7,   # Weekly update
        'digitalassets': 1  # Daily update
    }
    
    # Get project root directory
    project_root = Path(__file__).parent.parent
    data_dir = project_root / 'data'
    
    # Import each category
    for category, frequency in categories.items():
        file_path = data_dir / f"{category}.csv"
        if file_path.exists():
            logger.info(f"Importing {category} data from {file_path}...")
            import_category_data(category, str(file_path))
        else:
            logger.warning(f"CSV file for {category} not found at {file_path}")
    
    logger.info("Data import completed")

if __name__ == "__main__":
    import sys
    force_update = len(sys.argv) > 1 and sys.argv[1].lower() == 'force'
    main(force_update)
