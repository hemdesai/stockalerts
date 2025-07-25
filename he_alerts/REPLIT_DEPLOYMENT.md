# Replit Deployment Guide for HE Alerts

## Prerequisites

1. Replit account with Hacker plan or above (for Always On and Secrets)
2. PostgreSQL database (Neon.tech recommended)
3. Gmail API credentials
4. Mistral AI API key
5. IBKR TWS/Gateway running on accessible server
6. SMTP credentials for alert emails

## Step 1: Import from GitHub

1. Log into Replit
2. Click "Create Repl"
3. Select "Import from GitHub"
4. Enter your repository URL
5. Name your Repl (e.g., "he-alerts-production")
6. Click "Import from GitHub"

## Step 2: Configure Secrets

In the Replit Secrets tab, add all required environment variables:

```bash
# Database
DATABASE_URL = "postgresql+asyncpg://user:pass@host:5432/dbname"

# Gmail API
GMAIL_CREDENTIALS_JSON = '{"type": "service_account", ...}'  # Full JSON content

# Mistral AI
MISTRAL_API_KEY = "your-api-key"

# IBKR Connection
IBKR_HOST = "your-ibkr-host"  # Public IP or hostname
IBKR_PORT = "7497"
IBKR_CLIENT_ID = "1"

# SMTP Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = "587"
SMTP_USERNAME = "your-email@gmail.com"
SMTP_PASSWORD = "your-app-password"

# Alert Configuration
ALERT_FROM_EMAIL = "alerts@yourdomain.com"
ALERT_TO_EMAILS = '["recipient1@example.com", "recipient2@example.com"]'

# Timezone
TZ = "America/New_York"
```

## Step 3: Install Dependencies

The Repl should automatically install dependencies from `requirements.txt`. If not:

```bash
pip install -r requirements.txt
```

## Step 4: Initialize Database

In the Shell tab:

```bash
python he_alerts/scripts/init_db.py
```

## Step 5: Configure Always On

1. Go to the "Tools" section
2. Enable "Always On" 
3. This ensures your scheduled tasks run even when you're not actively viewing the Repl

## Step 6: Test the System

### Test Email Extraction
```bash
python he_alerts/validate_emails.py
```

### Test Alert Generation (without sending)
```bash
python he_alerts/alert_workflow.py --test-mode --no-email
```

### Test Complete Workflow
```bash
python he_alerts/alert_workflow.py --test-mode
```

## Step 7: Deploy

1. Click the "Run" button
2. The system will start with scheduled tasks:
   - AM Session: 9:00 AM EST
   - PM Session: 3:30 PM EST

## Monitoring

### View Logs
Logs are displayed in the Console tab. Key things to monitor:
- Successful email fetches
- Stock updates
- Price fetches from IBKR
- Alert generation and sending

### Health Check
Access the health endpoint:
```
https://your-repl-name.repl.co/health
```

### Manual Trigger
You can manually trigger the workflow:
```bash
python he_alerts/alert_workflow.py --session AM
```

## Troubleshooting

### IBKR Connection Issues

If IBKR connection fails:
1. Ensure IBKR Gateway/TWS is accessible from Replit's servers
2. Check firewall rules allow incoming connections
3. Verify API settings in TWS/Gateway

### Gmail API Issues

If Gmail authentication fails:
1. Verify the service account JSON is correctly pasted in Secrets
2. Ensure the service account has access to the Gmail account
3. Check Gmail API is enabled in Google Cloud Console

### Database Connection Issues

If database connection fails:
1. Verify DATABASE_URL is correct
2. Check database is accessible from Replit (whitelist IPs if needed)
3. Ensure SSL mode is configured correctly

### Scheduled Tasks Not Running

If scheduled tasks don't run:
1. Verify Always On is enabled
2. Check timezone settings (should be America/New_York)
3. Review logs for any startup errors

## Security Considerations

1. **Secrets Management**: Never commit credentials to Git
2. **Database Access**: Use connection pooling and SSL
3. **IBKR Security**: Use read-only API where possible
4. **Email Security**: Use app-specific passwords, not main account password

## Backup and Recovery

### Database Backups
Set up automated backups in your PostgreSQL provider (e.g., Neon.tech)

### Configuration Backup
Export your Secrets regularly:
1. Go to Secrets tab
2. Document all key-value pairs securely

### Code Backup
The code is already in GitHub, but ensure regular commits of any Replit-specific changes

## Performance Optimization

1. **Database Indexes**: Already configured in the schema
2. **Connection Pooling**: Handled by SQLAlchemy
3. **Batch Processing**: IBKR prices fetched in batches
4. **Async Operations**: All I/O operations are async

## Scaling Considerations

If you need to scale:
1. Consider separating the scheduler from the API
2. Use multiple IBKR connections for parallel price fetching
3. Implement caching for frequently accessed data
4. Consider message queuing for alert delivery

## Support

For Replit-specific issues:
- Check Replit documentation
- Visit Replit community forums

For HE Alerts issues:
- Review logs in the Console
- Check the troubleshooting section above
- Contact the development team