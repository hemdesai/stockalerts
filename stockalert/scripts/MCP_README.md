# Mail Client Protocol (MCP) Server

## Overview

The Mail Client Protocol (MCP) Server is a centralized service that manages all Gmail and Google Drive interactions for the Stock Alert application. It provides a unified API for email operations and Google Sheets integration, reducing code duplication and improving maintainability.

## Features

- **Centralized Authentication**: All Gmail and Google Drive authentication is managed in one place.
- **Reduced API Calls**: Implements caching to reduce API calls to Google services.
- **Simplified Client Code**: Extractors and other components have a simpler interface to work with.
- **Better Error Handling**: Centralized error handling and logging.
- **Scalability**: The server can be deployed separately from the main application.
- **Reduced Credential Management**: Only the MCP server needs access to the credentials.
- **Fallback Mechanisms**: All components maintain direct API access as fallback if the MCP server is unavailable.

## Components

### 1. MCP Server (`mcp_server.py`)

The core server component that provides the following endpoints:

- `/email/content`: Get content from emails matching a query
- `/email/send`: Send emails with HTML content
- `/sheets/write`: Write data to Google Sheets

### 2. MCP Client (`mcp_client.py`)

A client library that communicates with the MCP server:

- `get_email_content()`: Retrieve email content
- `send_email()`: Send emails
- `write_to_sheet()`: Write data to Google Sheets

### 3. Server Startup Script (`start_mcp_server.py`)

A utility script to start the MCP server as a background process.

### 4. Demo Script (`mcp_demo.py`)

A demonstration script showing how to use the MCP server for various operations.

## Integration with Existing Components

The MCP server has been integrated with the following components:

1. **BaseEmailExtractor**: Now uses the MCP client to retrieve email content
2. **EmailService**: Uses the MCP client for sending emails and writing to Google Sheets

Both components maintain fallback mechanisms to direct API access if the MCP server is unavailable.

## Setup and Usage

### Installation

1. Install the required dependencies:
   ```
   pip install fastapi uvicorn requests
   ```

2. Start the MCP server:
   ```
   python -m stockalert.scripts.start_mcp_server
   ```

3. Run your application, which will now use the MCP client to interact with Gmail and Google Sheets.

### Using the MCP Client

```python
from stockalert.scripts.mcp_client import MCPClient

# Initialize the client
client = MCPClient()

# Get email content
content = client.get_email_content("subject:RISK RANGE")

# Send an email
client.send_email(
    subject="Test Email",
    html_content="<p>This is a test email</p>",
    recipient="user@example.com"
)

# Write to Google Sheets
data = [
    {"Ticker": "AAPL", "Price": 175.50},
    {"Ticker": "MSFT", "Price": 420.25}
]
client.write_to_sheet("research", data, "sheet1")
```

## Benefits for the Stock Alert System

1. **Reduced API Rate Limiting**: Centralized caching reduces the number of API calls to Gmail and Google Sheets.
2. **Improved Error Handling**: Consistent error handling across all components.
3. **Simplified Maintenance**: Updates to API interactions only need to be made in one place.
4. **Better Monitoring**: Centralized logging of all API interactions.
5. **Enhanced Security**: Credentials are managed in a single location.

## Future Enhancements

1. **Authentication Layer**: Add authentication to the MCP server API.
2. **Additional Endpoints**: Support for more Gmail and Google Drive operations.
3. **Metrics Collection**: Track API usage and performance metrics.
4. **Distributed Deployment**: Support for running the MCP server on a separate machine.
5. **Load Balancing**: Support for multiple MCP server instances.
