"""
Script to start both the data import scheduler and alert scheduler
"""
import os
import sys
import time
import logging
import subprocess
import signal
import psutil
from pathlib import Path
from datetime import datetime
import pytz

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from stockalert.utils.env_loader import load_environment

# Load environment variables
load_environment()

# Configure logging
log_dir = Path(__file__).parent.parent / 'data' / 'logs'
log_dir.mkdir(exist_ok=True, parents=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'start_script.log'),
        logging.StreamHandler()
    ]
)

def is_mcp_server_running():
    """Check if MCP server is running"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and len(cmdline) > 1:
                if 'python' in cmdline[0].lower() and 'mcp_server.py' in cmdline[1]:
                    logging.info(f"MCP server is running with PID {proc.info['pid']}")
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

def start_mcp_server():
    """Start the MCP server if it's not already running"""
    if is_mcp_server_running():
        logging.info("MCP server is already running")
        return
    
    logging.info("Starting MCP server...")
    
    # Path to the start_mcp_server.py script
    mcp_start_script = Path(project_root) / 'stockalert' / 'scripts' / 'start_mcp_server.py'
    
    # Start the MCP server
    try:
        subprocess.Popen([sys.executable, str(mcp_start_script), 'start'],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        
        # Wait a bit for the server to start
        time.sleep(5)
        logging.info("MCP server started successfully")
    except Exception as e:
        logging.error(f"Failed to start MCP server: {e}")

def start_data_import_scheduler():
    """Start the data import scheduler in a separate process"""
    logging.info("Starting data import scheduler...")
    
    # Path to the data_import_scheduler.py script
    scheduler_script = Path(project_root) / 'stockalert' / 'scripts' / 'data_import_scheduler.py'
    
    # Create a dedicated log file for the data import scheduler
    log_file = log_dir / f'data_import_scheduler_{datetime.now(pytz.timezone("America/New_York")).strftime("%Y%m%d")}.log'
    
    # Start the scheduler with its output redirected to the log file
    try:
        with open(log_file, 'a') as f:
            process = subprocess.Popen([sys.executable, str(scheduler_script)],
                                      stdout=f,
                                      stderr=f,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
        
        logging.info(f"Data import scheduler started with PID {process.pid}")
        logging.info(f"Logs are being written to {log_file}")
        return process
    except Exception as e:
        logging.error(f"Failed to start data import scheduler: {e}")
        return None

def start_alert_scheduler():
    """Start the alert scheduler in a separate process"""
    logging.info("Starting alert scheduler...")
    
    # Path to the alert_scheduler.py script
    scheduler_script = Path(project_root) / 'stockalert' / 'scripts' / 'alert_scheduler.py'
    
    # Create a dedicated log file for the alert scheduler
    log_file = log_dir / f'alert_scheduler_{datetime.now(pytz.timezone("America/New_York")).strftime("%Y%m%d")}.log'
    
    # Start the scheduler with its output redirected to the log file
    try:
        with open(log_file, 'a') as f:
            process = subprocess.Popen([sys.executable, str(scheduler_script)],
                                      stdout=f,
                                      stderr=f,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
        
        logging.info(f"Alert scheduler started with PID {process.pid}")
        logging.info(f"Logs are being written to {log_file}")
        return process
    except Exception as e:
        logging.error(f"Failed to start alert scheduler: {e}")
        return None

def main():
    """Main function to start all schedulers"""
    logging.info("Starting Stock Alert Schedulers...")
    
    # First, make sure MCP server is running
    start_mcp_server()
    
    # Start data import scheduler
    data_import_process = start_data_import_scheduler()
    
    # Start alert scheduler
    alert_process = start_alert_scheduler()
    
    # Monitor processes
    try:
        logging.info("All schedulers started. Press Ctrl+C to stop.")
        
        # Keep the main process running to monitor the child processes
        while True:
            # Check if processes are still running
            if data_import_process and not psutil.pid_exists(data_import_process.pid):
                logging.warning("Data import scheduler process has stopped. Restarting...")
                data_import_process = start_data_import_scheduler()
            
            if alert_process and not psutil.pid_exists(alert_process.pid):
                logging.warning("Alert scheduler process has stopped. Restarting...")
                alert_process = start_alert_scheduler()
            
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        logging.info("Stopping schedulers...")
        
        # Terminate processes
        if data_import_process:
            data_import_process.terminate()
            logging.info("Data import scheduler stopped")
        
        if alert_process:
            alert_process.terminate()
            logging.info("Alert scheduler stopped")
        
        logging.info("All schedulers stopped")
    
    except Exception as e:
        logging.error(f"Error in main process: {e}")
        
        # Attempt to clean up
        if data_import_process:
            data_import_process.terminate()
        
        if alert_process:
            alert_process.terminate()

if __name__ == "__main__":
    main()
