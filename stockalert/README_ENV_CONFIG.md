# Environment Configuration Guide

## Overview
This document explains the centralized environment configuration system implemented for the StockAlert application.

## Key Changes

### 1. Centralized Environment Loading
- Created a utility module `stockalert/utils/env_loader.py` that handles loading environment variables from a single source
- All application modules now use this centralized loader instead of loading environment variables directly
- This ensures consistent access to environment variables across the entire application

### 2. Environment Variables Template
- Created a template file `stockalert/env_template.txt` that contains all required environment variables
- You should rename this file to `.env` and place it in the `stockalert` directory

### 3. Updated Code References
- Modified all Python files to use the centralized environment loader
- Removed duplicate environment loading code
- Added proper imports and path handling

## How to Use

### Setting Up Your Environment
1. Copy the `env_template.txt` file to `.env` in the `stockalert` directory:
   ```
   copy stockalert\env_template.txt stockalert\.env
   ```

2. Edit the `.env` file to set your specific environment variables:
   ```
   # Mistral API key for ETF extraction
   MISTRAL_API_KEY=your_mistral_api_key

   # Path to data directory
   DATA_DIR=data

   # Email settings for alert system
   EMAIL_SENDER=your_email@gmail.com
   EMAIL_PASSWORD=your_app_password
   EMAIL_RECIPIENT=recipient_email@example.com

   # Add any other environment variables here
   # Database settings
   DB_PATH=data/stocks.db

   # Scheduler settings
   SCHEDULER_ENABLED=true
   CSV_IMPORT_TIME=08:45
   DB_IMPORT_TIME=10:55
   ALERT_TIMES=11:05,14:35
   ```

### Using Environment Variables in Your Code
To access environment variables in your code, use the utility functions:

```python
from stockalert.utils.env_loader import get_env

# Get an environment variable with a default value
api_key = get_env('MISTRAL_API_KEY', 'default_value')

# Get an environment variable without a default (returns None if not found)
email_sender = get_env('EMAIL_SENDER')
```

### Adding New Environment Variables
When adding new environment variables:
1. Add them to your `.env` file
2. Access them using the `get_env` function
3. Document them in the `env_template.txt` file for future reference

## Benefits
- Single source of truth for all environment variables
- Consistent access pattern across the codebase
- Easier to manage and update environment variables
- Better organization and maintainability
- Reduced code duplication
