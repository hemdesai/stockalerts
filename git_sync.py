#!/usr/bin/env python
"""
Git Sync Script for StockAlert

This script automates the process of committing and pushing changes to GitHub.
It checks for changes, adds them, commits with a meaningful message, and pushes to the remote repository.
"""

import os
import sys
import subprocess
import datetime
import argparse
from pathlib import Path

def run_command(command, cwd=None):
    """Run a shell command and return the output"""
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            text=True,
            capture_output=True,
            shell=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {command}")
        print(f"Error message: {e.stderr}")
        return None

def get_status(repo_path):
    """Get the current git status"""
    return run_command("git status", cwd=repo_path)

def has_changes(repo_path):
    """Check if there are any changes to commit"""
    status = get_status(repo_path)
    return "nothing to commit, working tree clean" not in status

def get_changed_files(repo_path):
    """Get a list of changed files"""
    result = run_command("git status --porcelain", cwd=repo_path)
    if not result:
        return []
    
    files = []
    for line in result.split('\n'):
        if line.strip():
            # Extract the filename (after the status code)
            status_code = line[:2]
            filename = line[3:].strip()
            files.append((status_code, filename))
    
    return files

def generate_commit_message(changed_files):
    """Generate a meaningful commit message based on changed files"""
    # Count files by type
    counts = {}
    for _, filename in changed_files:
        file_type = Path(filename).suffix
        if not file_type and '/' in filename:
            # It might be a directory operation
            file_type = "directory"
        elif not file_type:
            file_type = "file"
            
        counts[file_type] = counts.get(file_type, 0) + 1
    
    # Generate message parts
    parts = []
    for file_type, count in counts.items():
        if file_type == ".py":
            parts.append(f"Update {count} Python files")
        elif file_type == ".md":
            parts.append(f"Update {count} documentation files")
        elif file_type == ".csv":
            parts.append(f"Update {count} data files")
        elif file_type == "directory":
            parts.append(f"Update {count} directories")
        else:
            parts.append(f"Update {count} {file_type} files")
    
    # Join parts
    if parts:
        message = ", ".join(parts)
    else:
        message = "Update files"
    
    # Add timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"{message} [{timestamp}]"

def commit_changes(repo_path, message=None, files=None):
    """Commit changes to the repository"""
    if files is None:
        # Add all changes
        run_command("git add .", cwd=repo_path)
    else:
        # Add specific files
        for _, file in files:
            run_command(f'git add "{file}"', cwd=repo_path)
    
    # Generate commit message if not provided
    if not message:
        changed_files = get_changed_files(repo_path)
        message = generate_commit_message(changed_files)
    
    # Commit with the message
    result = run_command(f'git commit -m "{message}"', cwd=repo_path)
    return result

def push_changes(repo_path, branch="main"):
    """Push changes to the remote repository"""
    return run_command(f"git push origin {branch}", cwd=repo_path)

def main():
    """Main function to sync the repository"""
    parser = argparse.ArgumentParser(description="Sync StockAlert repository with GitHub")
    parser.add_argument("--message", "-m", help="Custom commit message")
    parser.add_argument("--no-push", action="store_true", help="Don't push changes to remote")
    parser.add_argument("message", nargs="?", help="Commit message (positional argument)")
    args = parser.parse_args()
    
    # Get repository path (script's parent directory)
    repo_path = Path(__file__).parent.absolute()
    print(f"Repository path: {repo_path}")
    
    # Check if there are changes to commit
    if not has_changes(repo_path):
        print("No changes to commit.")
        return
    
    # Get changed files
    changed_files = get_changed_files(repo_path)
    print(f"Found {len(changed_files)} changed files:")
    for status, filename in changed_files:
        print(f"  {status} {filename}")
    
    # Determine commit message (positional argument takes precedence)
    commit_message = None
    if args.message:
        commit_message = args.message
    elif hasattr(args, 'm') and args.m:
        commit_message = args.m
    
    # Commit changes
    commit_result = commit_changes(repo_path, message=commit_message, files=changed_files)
    if commit_result:
        print(f"Committed changes: {commit_result}")
    else:
        print("Failed to commit changes.")
        return
    
    # Push changes if requested
    if not args.no_push:
        push_result = push_changes(repo_path)
        if push_result:
            print(f"Pushed changes: {push_result}")
        else:
            print("Failed to push changes.")
    else:
        print("Skipping push as requested.")

if __name__ == "__main__":
    main()
