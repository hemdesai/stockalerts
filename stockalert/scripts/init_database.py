#!/usr/bin/env python
"""
Initialize database tables for Stock Alert system
"""
import os
import sys
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from stockalert.scripts.db_manager import StockAlertDBManager
from stockalert.utils.env_loader import load_environment

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

def main():
    """Initialize database tables"""
    # Load environment variables
    load_environment()
    
    logging.info("Initializing database tables...")
    
    # Create database manager
    db_manager = StockAlertDBManager()
    
    # Create tables
    success = db_manager.create_tables()
    
    if success:
        logging.info("Database tables created successfully")
    else:
        logging.error("Failed to create database tables")
    
    # Let's check if the stocks table has any records
    db_manager.connect()
    db_manager.cursor.execute("SELECT COUNT(*) FROM stocks")
    count = db_manager.cursor.fetchone()[0]
    db_manager.close()
    
    logging.info(f"Found {count} records in the stocks table")
    
    if count == 0:
        logging.warning("The stocks table is empty. You may need to import data first.")
        logging.info("Run the data import scheduler to populate the database.")

if __name__ == "__main__":
    main()
