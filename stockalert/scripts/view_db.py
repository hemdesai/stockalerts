import sqlite3
import pandas as pd
from pathlib import Path

def view_db_data():
    try:
        # Connect to database
        root_dir = Path(__file__).parent.parent
        db_path = root_dir / 'data' / 'stocks.db'
        
        if not db_path.exists():
            print("Database file not found!")
            return
            
        conn = sqlite3.connect(str(db_path))
        
        # Query examples
        print("\n1. View all data:")
        df = pd.read_sql("SELECT * FROM stocks LIMIT 5", conn)
        print(df)
        
        print("\n2. Count by category:")
        df = pd.read_sql("SELECT Category, COUNT(*) as count FROM stocks GROUP BY Category", conn)
        print(df)
        
        conn.close()
        
    except Exception as e:
        print(f"Error viewing database: {e}")


if __name__ == "__main__":
    view_db_data() 