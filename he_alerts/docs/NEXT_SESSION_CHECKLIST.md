# Next Session Checklist - HE Alerts System

## Current Status (as of 2025-07-25)

### ✅ Completed
1. **Full HE Alerts system implementation**
2. **Repository cleanup** - removed 75+ unnecessary files
3. **Automated scheduler with market holiday awareness**
4. **Complete documentation and flow diagrams**
5. **Replit deployment preparation**

### 📍 Repository Location
- **GitHub**: https://github.com/hemdesai/stockalerts
- **Main System**: `/he_alerts/` directory

## Quick Start for Next Session

### 1. Environment Setup
```bash
cd C:\code\stockalert\he_alerts
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
```

### 2. Required Credentials
Ensure you have:
- [ ] PostgreSQL database URL (Neon.tech)
- [ ] Gmail API credentials
- [ ] Mistral AI API key
- [ ] IBKR connection details (host, port)
- [ ] SMTP credentials for alerts

### 3. Test Basic Functionality
```bash
# Test database connection
python scripts/init_db.py

# Test email extraction (dry run)
python validate_emails.py

# Test alert generation
python alert_workflow.py --test-mode --no-email
```

### 4. Production Deployment Options

#### Option A: Automated Scheduler (Recommended)
```bash
python automated_scheduler.py
```
This runs:
- 9:00 AM: Email extraction (all 4 types on first market day, 2 types other days)
- 10:45 AM: Morning alerts
- 2:30 PM: Afternoon alerts

#### Option B: Manual Runs
```bash
# Fetch emails and update DB
python fetch_latest_emails.py

# Generate and send alerts
python alert_workflow.py
```

## Key Features to Remember

### Email Types
1. **Daily**: HTML table extraction
2. **Crypto**: OCR from images at indices 6 & 14
3. **ETFs**: Weekly extraction (first market day)
4. **Ideas**: Weekly extraction (first market day)

### Alert Rules
- **BULLISH**: BUY ≤ buy_trade, SELL ≥ sell_trade
- **BEARISH**: BUY ≥ buy_trade, SELL ≤ sell_trade
- **NEUTRAL**: Same as BULLISH

### Database Strategy
- **Delete-before-insert**: Prevents stale data
- **Single table design**: Just `stocks` table
- **Categories**: daily, digitalassets, etfs, ideas

## Replit Deployment

1. Import from GitHub: https://github.com/hemdesai/stockalerts
2. Configure Secrets (environment variables)
3. Run will automatically use `automated_scheduler.py`
4. Enable "Always On" for production

## Common Commands

### Diagnostics
```bash
python scripts/diagnostics/check_database_contents.py
python scripts/diagnostics/check_all_stocks.py
python scripts/diagnostics/check_alerts.py
```

### Manual Email Extraction
```bash
# All 4 types
python fetch_latest_emails.py daily crypto etfs ideas

# Just daily updates
python fetch_latest_emails.py daily crypto
```

### CSV Export
```bash
python export_stocks_db.py
```

## Troubleshooting

### If emails aren't extracting:
1. Check Gmail authentication
2. Verify Mistral API key
3. For crypto: Ensure images 6 & 14 are being processed

### If alerts aren't generating:
1. Ensure IBKR Gateway/TWS is running
2. Check SMTP credentials
3. Verify stocks have current prices

### If scheduler isn't running:
1. Check if today is a market holiday
2. Verify timezone (America/New_York)
3. Review logs for errors

## Recent Changes Log
- Added automated scheduler with holiday awareness
- Cleaned up 75+ temporary files
- Simplified to single stocks table
- Added validation workflow
- Prepared for Replit deployment

## Contact/Issues
- GitHub Issues: https://github.com/hemdesai/stockalerts/issues
- Main documentation: `/he_alerts/README.md`

---
Last updated: 2025-07-25
System is production-ready and fully documented.