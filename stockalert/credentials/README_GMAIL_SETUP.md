# Gmail API Setup Instructions

To use the email extractors, you need to set up Gmail API credentials:

## Steps to Create credentials.json:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API:
   - Go to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click on it and press "Enable"

4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - If prompted, configure the OAuth consent screen first
   - Select "Desktop app" as the application type
   - Give it a name (e.g., "StockAlert Gmail Access")
   - Click "Create"

5. Download the credentials:
   - Click the download button next to your newly created OAuth client
   - Save the file in this directory (keep the original filename)

## First Run:

When you first run the extractors, a browser window will open asking you to:
1. Log in to your Google account
2. Grant permission to access Gmail
3. The script will save a `token.json` file for future use

## Files in this directory:

- `service_account.json` - Used for Google Sheets access
- `client_secret_*.json` - Gmail API OAuth2 credentials (you need to create this)
- `token.json` - Created automatically after first successful authentication