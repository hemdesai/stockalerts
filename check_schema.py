import sqlite3
import os

def check_schema():
    db_path = os.path.join('stockalert', 'data', 'stocks.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print("Tables in database:")
    for table in tables:
        print(f"- {table}")
    
    # Get schema for each table
    print("\nSchema for each table:")
    for table in tables:
        print(f"\n{table} schema:")
        cursor.execute(f"PRAGMA table_info({table})")
        for col in cursor.fetchall():
            pk = "PRIMARY KEY" if col[5] else ""
            print(f"  {col[1]} ({col[2]}) {pk}")
    
    # Get foreign keys for each table
    print("\nForeign keys for each table:")
    for table in tables:
        print(f"\n{table} foreign keys:")
        cursor.execute(f"PRAGMA foreign_key_list({table})")
        fks = cursor.fetchall()
        if not fks:
            print("  None")
        for fk in fks:
            print(f"  {fk[3]} -> {fk[2]}.{fk[4]}")
    
    conn.close()

if __name__ == "__main__":
    check_schema()
