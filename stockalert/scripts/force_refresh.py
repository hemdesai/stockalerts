"""
Force Refresh Script

This script triggers an immediate data refresh by creating a trigger file
that will be detected by the data_import_scheduler.py script.

Usage:
    python -m stockalert.scripts.force_refresh
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scripts.data_import_scheduler import force_refresh

if __name__ == "__main__":
    print("Forcing immediate data refresh...")
    force_refresh()
    print("Done. The scheduler will detect the trigger file and refresh all data.")
    print("Check the data_import.log file for results.")
