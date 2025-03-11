#!/usr/bin/env python
"""
Simple wrapper script to run git_sync.py with common options.
This makes it easier to sync the repository with a single command.
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Run the git_sync.py script with common options"""
    # Get the path to the git_sync.py script
    script_path = Path(__file__).parent / "git_sync.py"
    
    # Check if a commit message was provided
    message = None
    if len(sys.argv) > 1:
        message = sys.argv[1]
    
    # Build the command
    command = [sys.executable, str(script_path)]
    if message:
        command.extend(["-m", message])
    
    # Run the command
    try:
        subprocess.run(command, check=True)
        print("\nRepository sync completed successfully!")
    except subprocess.CalledProcessError:
        print("\nError syncing repository. See above for details.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
