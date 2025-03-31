#!/usr/bin/env python
"""
Check the database schema for the Stock Alert system
"""
import os
import sys
import sqlite3
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from stockalert.utils.env_loader import load_environment

def main():
    """Check the database schema"""
    # Load environment variables
    load_environment()
    
    # Get database path
    db_path = os.path.join(project_root, "stockalert", "data", "stocks.db")
    print(f"Checking database at: {db_path}")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get list of tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"Tables in database: {[table[0] for table in tables]}")
    
    # Check schema for each table
    for table in tables:
        table_name = table[0]
        print(f"\nSchema for table: {table_name}")
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        for column in columns:
            col_id, col_name, col_type, not_null, default_val, pk = column
            print(f"  {col_name} ({col_type}), PK: {pk}, NOT NULL: {not_null}, DEFAULT: {default_val}")
    
    # Check for sample data in stocks table
    try:
        cursor.execute("SELECT * FROM stocks LIMIT 5")
        rows = cursor.fetchall()
        if rows:
            print("\nSample data from stocks table:")
            
            # Get column names
            cursor.execute("PRAGMA table_info(stocks)")
            columns = [column[1] for column in cursor.fetchall()]
            print(f"Columns: {columns}")
            
            # Print sample data
            for row in rows:
                row_dict = {columns[i]: row[i] for i in range(len(columns))}
                print(f"Row: {row_dict}")
        else:
            print("\nNo data found in stocks table")
    except Exception as e:
        print(f"Error getting sample data: {e}")
    
    # Close connection
    conn.close()
    
    print("\nDatabase schema check completed")

if __name__ == "__main__":
    main()