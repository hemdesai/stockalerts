# HE Alerts Workflow Guide

## Overview

The HE Alerts system is a complete workflow that:
1. Fetches prices from Interactive Brokers (IBKR)
2. Compares prices against Hedgeye thresholds
3. Generates alerts when thresholds are crossed
4. Sends email notifications

## Components

### 1. Alert Workflow (`alert_workflow.py`)
Main orchestrator that coordinates:
- IBKR price fetching
- Alert generation based on sentiment rules
- Email sending

### 2. Production Runner (`run_alert_workflow.py`)
Production-ready script for scheduling with:
- Auto-detection of AM/PM sessions
- Dry-run mode for testing
- Comprehensive logging

### 3. Scheduled Runner (`scheduled_alerts.py`)
Simple script for cron/scheduler integration with:
- Session window validation (10-12 AM, 2-4 PM ET)
- Production defaults

## Alert Logic

### Bullish Sentiment
- **BUY Alert**: When price <= buy_trade threshold
- **SELL Alert**: When price >= sell_trade threshold

### Bearish Sentiment
- **SHORT Alert**: When price >= sell_trade threshold
- **COVER Alert**: When price <= buy_trade threshold

## Usage

### Manual Testing

```bash
# Test with existing prices (no IBKR connection)
python he_alerts/alert_workflow.py --test --skip-prices

# Check current prices and potential alerts
python he_alerts/alert_workflow.py --check-prices

# Full test without sending emails
python he_alerts/run_alert_workflow.py --dry-run
```

### Production Usage

```bash
# Run for current session (auto-detect AM/PM)
python he_alerts/run_alert_workflow.py

# Force specific session
python he_alerts/run_alert_workflow.py --session AM
```

### Scheduling

#### Windows Task Scheduler
```powershell
# AM Session (10:45 AM ET)
schtasks /create /tn "HE_Alerts_AM" /tr "python C:\code\stockalert\he_alerts\run_alert_workflow.py" /sc daily /st 10:45

# PM Session (2:30 PM ET)
schtasks /create /tn "HE_Alerts_PM" /tr "python C:\code\stockalert\he_alerts\run_alert_workflow.py" /sc daily /st 14:30
```

#### Linux/Mac Cron
```bash
# Edit crontab
crontab -e

# Add these lines
45 10 * * * cd /path/to/stockalert/he_alerts && python run_alert_workflow.py
30 14 * * * cd /path/to/stockalert/he_alerts && python run_alert_workflow.py
```

## Configuration

### Environment Variables (.env)
```env
# IBKR Connection
IBKR_HOST=127.0.0.1
IBKR_PORT=4001  # 7497 for paper trading
IBKR_CLIENT_ID=1

# Email Settings
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_TO_EMAILS=["recipient1@example.com", "recipient2@example.com"]
```

### Prerequisites
1. IBKR Gateway or TWS running
2. Market data subscriptions for tracked symbols
3. Gmail app password configured
4. PostgreSQL database with stock data

## Workflow Sequence

1. **Price Fetch**: Connect to IBKR and fetch latest prices
2. **Alert Check**: Compare prices against thresholds
3. **Alert Storage**: Save alerts to database
4. **Email Send**: Format and send HTML email with alerts

## Monitoring

### Logs
- Location: `he_alerts/logs/`
- Format: Structured JSON logs
- Levels: INFO, WARNING, ERROR

### Database Tables
- `stocks`: Current stock data and thresholds
- `alert_logs`: Historical alert records
- `price_history`: Price snapshots

## Troubleshooting

### No Prices Fetched
- Check IBKR Gateway/TWS is running
- Verify port settings (4001 for live, 7497 for paper)
- Ensure market data subscriptions are active

### No Alerts Generated
- Verify stocks have AM/PM prices
- Check sentiment and threshold values
- Review logs for calculation details

### Email Not Sent
- Verify SMTP credentials
- Check recipient email addresses
- Review email logs for errors

## Example Alert Email

```
Subject: HE Alerts - AM Session (7 alerts) - 2025-07-25 10:00 ET

SELL Alerts (4):
- CPER @ $36.17 (threshold: $35.20)
- QQQ @ $565.25 (threshold: $565.00)
- TSLA @ $306.61 (threshold: $250.00)
- ULTA @ $506.25 (threshold: $504.00)

BUY Alerts (1):
- TTE @ $60.05 (threshold: $60.43)

SHORT Alerts (1):
- EWJ @ $75.58 (threshold: $73.65)

COVER Alerts (1):
- UNG @ $13.98 (threshold: $14.04)
```

## Testing Alert Logic

Current test results show 7 alerts:
- 4 SELL alerts (bullish stocks above sell threshold)
- 1 BUY alert (bullish stock below buy threshold)
- 1 SHORT alert (bearish stock above sell threshold)
- 1 COVER alert (bearish stock below buy threshold)

This demonstrates the system correctly implements Hedgeye's sentiment-based trading logic.