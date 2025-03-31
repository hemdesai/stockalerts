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
        # Escape quotes in the message
        message = message.replace('"', '\\"')
        command.extend(["-m", message])
    
    # Run the command
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(result.stdout)
        if "Failed to commit changes" in result.stdout or "Failed to push changes" in result.stdout:
            print("\nRepository sync failed. See above for details.")
            return 1
        print("\nRepository sync completed successfully!")
        return 0
    except subprocess.CalledProcessError as e:
        print(e.stdout)
        print(e.stderr)
        print("\nError syncing repository. See above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
