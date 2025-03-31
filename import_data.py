import sys
from pathlib import Path

# Add the project root to Python path
project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from stockalert.scripts.data_import_scheduler import DataImportScheduler

# Create an instance of the scheduler
scheduler = DataImportScheduler()

# Import the data to the database
print("Starting database import...")
scheduler.import_to_database()
print("Database import complete.")
