import subprocess
import sys
import time
import logging
import os
import signal
import platform
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / 'data' / 'mcp_startup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def is_port_in_use(port):
    """Check if a port is in use"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def find_mcp_process():
    """Find if MCP server is already running"""
    try:
        if platform.system() == "Windows":
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and any('mcp_server.py' in cmd for cmd in cmdline):
                        return proc.info['pid']
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        else:
            # Unix-like systems
            import subprocess
            result = subprocess.run(['pgrep', '-f', 'mcp_server.py'], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   text=True)
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())
    except Exception as e:
        logger.error(f"Error finding MCP process: {e}")
    return None

def start_mcp_server():
    """Start the MCP server as a background process"""
    try:
        # Check if server is already running
        port = 8000  # Default port for MCP server
        if is_port_in_use(port):
            logger.info(f"Port {port} is already in use, MCP server might be running")
            pid = find_mcp_process()
            if pid:
                logger.info(f"MCP server is already running with PID {pid}")
                return True
            else:
                logger.warning(f"Port {port} is in use but no MCP server process found")
        
        # Get the path to the MCP server script
        mcp_server_path = Path(__file__).parent / 'mcp_server.py'
        
        if not mcp_server_path.exists():
            logger.error(f"MCP server script not found at {mcp_server_path}")
            return False
        
        logger.info(f"Starting MCP server from {mcp_server_path}")
        
        # Create data directory if it doesn't exist
        data_dir = Path(__file__).parent.parent / 'data'
        data_dir.mkdir(exist_ok=True)
        
        # Redirect stdout and stderr to log files
        stdout_log = data_dir / 'mcp_server_stdout.log'
        stderr_log = data_dir / 'mcp_server_stderr.log'
        
        with open(stdout_log, 'w') as stdout_file, open(stderr_log, 'w') as stderr_file:
            # Start the server using Python
            if platform.system() == "Windows":
                # Use CREATE_NEW_PROCESS_GROUP flag on Windows to create a new process group
                process = subprocess.Popen(
                    [sys.executable, str(mcp_server_path)],
                    stdout=stdout_file,
                    stderr=stderr_file,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                # On Unix-like systems, use start_new_session=True
                process = subprocess.Popen(
                    [sys.executable, str(mcp_server_path)],
                    stdout=stdout_file,
                    stderr=stderr_file,
                    start_new_session=True
                )
        
        logger.info(f"MCP server process started with PID {process.pid}")
        
        # Wait a bit to ensure the server starts
        time.sleep(5)
        
        # Check if the process is still running
        if process.poll() is None:
            # Check if the server is responding
            if is_port_in_use(port):
                logger.info(f"MCP server started successfully on port {port}")
                return True
            else:
                logger.warning("MCP server process is running but not listening on port 8000")
                # Check the stderr log for errors
                with open(stderr_log, 'r') as f:
                    stderr_content = f.read()
                    if stderr_content:
                        logger.error(f"MCP server stderr output: {stderr_content}")
                return False
        else:
            # Process exited, check the logs
            with open(stderr_log, 'r') as f:
                stderr_content = f.read()
            
            logger.error(f"MCP server failed to start, exit code: {process.returncode}")
            if stderr_content:
                logger.error(f"MCP server stderr output: {stderr_content}")
            return False
            
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def stop_mcp_server():
    """Stop the MCP server if it's running"""
    try:
        pid = find_mcp_process()
        if pid:
            logger.info(f"Stopping MCP server with PID {pid}")
            if platform.system() == "Windows":
                # On Windows, use taskkill to kill the process
                subprocess.run(['taskkill', '/F', '/PID', str(pid)])
            else:
                # On Unix-like systems, use kill
                os.kill(pid, signal.SIGTERM)
            logger.info("MCP server stopped")
            return True
        else:
            logger.info("No running MCP server found")
            return False
    except Exception as e:
        logger.error(f"Error stopping MCP server: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def restart_mcp_server():
    """Restart the MCP server"""
    stop_mcp_server()
    time.sleep(2)  # Wait for the server to fully stop
    return start_mcp_server()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='MCP Server Control')
    parser.add_argument('action', choices=['start', 'stop', 'restart', 'status'],
                        help='Action to perform on the MCP server')
    
    args = parser.parse_args()
    
    if args.action == 'start':
        if start_mcp_server():
            print("MCP server started successfully")
        else:
            print("Failed to start MCP server")
            sys.exit(1)
    elif args.action == 'stop':
        if stop_mcp_server():
            print("MCP server stopped successfully")
        else:
            print("Failed to stop MCP server")
            sys.exit(1)
    elif args.action == 'restart':
        if restart_mcp_server():
            print("MCP server restarted successfully")
        else:
            print("Failed to restart MCP server")
            sys.exit(1)
    elif args.action == 'status':
        pid = find_mcp_process()
        if pid:
            print(f"MCP server is running with PID {pid}")
        else:
            print("MCP server is not running")
            if is_port_in_use(8000):
                print("Warning: Port 8000 is in use by another process")
            sys.exit(1)
