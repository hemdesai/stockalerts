# HE Alerts - Quick Setup Guide

## 1. Neon Database Setup

1. Copy your Neon connection string from: https://console.neon.tech
2. Convert it for asyncpg:
   - Add `+asyncpg` after `postgresql`
   - Change `sslmode=require` to `ssl=require`

Example:
```
# Original from Neon:
postgresql://user:pass@ep-xxx.aws.neon.tech/neondb?sslmode=require

# Convert to:
postgresql+asyncpg://user:pass@ep-xxx.aws.neon.tech/neondb?ssl=require
```

## 2. Environment Variables (.env)

Edit your `.env` file with these values:

```bash
# Database - Your Neon connection string (converted)
DATABASE_URL=postgresql+asyncpg://[YOUR-NEON-CONNECTION-STRING]

# FastAPI
SECRET_KEY=your-secret-key-here-minimum-32-characters-long
DEBUG=true
LOG_LEVEL=INFO

# Gmail API
GMAIL_CREDENTIALS_PATH=credentials/gmail_credentials.json
GMAIL_TOKEN_PATH=credentials/gmail_token.json

# Mistral AI - Your existing key
MISTRAL_API_KEY=chboxhAEX2G0xYdUgklRZLSgunooJ0Tq

# Email Settings - Your existing settings
EMAIL_SENDER=hemdesai@gmail.com
EMAIL_PASSWORD=gizp vnlz nmgc lowo
EMAIL_RECIPIENT=hemdesai@gmail.com
```

## 3. Gmail API Credentials

1. Go to: https://console.cloud.google.com/apis/credentials
2. Create a new OAuth 2.0 Client ID
3. Application type: Desktop app
4. Download the JSON file
5. Save it as: `he_alerts/credentials/gmail_credentials.json`

## 4. Install Dependencies

```bash
cd he_alerts
pip install -r requirements.txt
```

## 5. Initialize Database

```bash
python scripts/init_db.py
```

## 6. Run the Application

```bash
python -m app.main
```

## 7. Test Email Processing

Open your browser to: http://localhost:8000/docs

Try these endpoints:
1. GET `/health/detailed` - Check system status
2. POST `/api/v1/email/process?hours=24` - Process last 24 hours of emails
3. GET `/api/v1/email/stats` - See processing statistics
4. GET `/api/v1/stocks/` - View extracted stocks