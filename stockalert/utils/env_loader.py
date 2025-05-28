"""
Environment variable loader utility.
Centralizes environment variable loading across the application.
"""
from pathlib import Path
from dotenv import load_dotenv
import os
import logging

def load_environment():
    """
    Load environment variables from central .env file
    
    Returns:
        dict: Environment variables dictionary
    """
    # Get the path to the root directory .env file
    env_path = Path(__file__).parent.parent.parent / '.env'
    
    # Log the path being used
    logging.info(f"Loading environment from: {env_path}")
    
    # Load the environment variables
    load_dotenv(dotenv_path=env_path)
    
    # Return the environment variables dictionary
    return os.environ

# Preload environment variables when the module is imported
env_vars = load_environment()

def get_env(key, default=None):
    """
    Get an environment variable with an optional default value
    
    Args:
        key (str): Environment variable name
        default: Default value if environment variable is not set
        
    Returns:
        The environment variable value or the default
    """
    return os.getenv(key, default)
