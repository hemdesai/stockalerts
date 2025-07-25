# Automated Scheduler Documentation

## Overview

The HE Alerts system includes a sophisticated automated scheduler that handles:
- Email extraction with market holiday awareness
- Alert generation at specific trading times
- Automatic adjustment for US market holidays

## Schedule Summary

| Task | Schedule | Description |
|------|----------|-------------|
| **Email Extraction** | 9:00 AM EST | Fetches emails based on day type |
| **Morning Alerts** | 10:45 AM EST | Generates and sends morning alerts |
| **Afternoon Alerts** | 2:30 PM EST | Generates and sends afternoon alerts |

## Email Extraction Logic

### First Market Day of Week
- Extracts all 4 email types: `daily`, `crypto`, `etfs`, `ideas`
- Automatically adjusts when Monday is a holiday (runs on Tuesday)

### Other Market Days
- Extracts only 2 email types: `daily`, `crypto`
- Runs Monday-Friday when markets are open

## Market Holiday Awareness

The scheduler is aware of all US market holidays including:

### Fixed Holidays
- New Year's Day (January 1)
- Independence Day (July 4)
- Christmas Day (December 25)

### Floating Holidays
- Martin Luther King Jr. Day (3rd Monday in January)
- Presidents' Day (3rd Monday in February)
- Good Friday (Friday before Easter)
- Memorial Day (Last Monday in May)
- Juneteenth (June 19)
- Labor Day (1st Monday in September)
- Thanksgiving Day (4th Thursday in November)

### Special Rules
- If a holiday falls on Saturday, market closes on Friday
- If a holiday falls on Sunday, market closes on Monday
- Christmas Eve: Early close (treated as closed for scheduling)

## Running the Scheduler

### Production Mode
```bash
python he_alerts/automated_scheduler.py
```

### Testing Mode
```bash
# Test email extraction only
python he_alerts/fetch_latest_emails.py daily crypto etfs ideas

# Test alert generation
python he_alerts/alert_workflow.py --test-mode
```

## Configuration

### Environment Variables
```bash
# Timezone (automatically set to America/New_York)
TZ=America/New_York

# Email types for weekly extraction
WEEKLY_EMAIL_TYPES=["daily", "crypto", "etfs", "ideas"]

# Email types for daily extraction
DAILY_EMAIL_TYPES=["daily", "crypto"]
```

## Manual Override

You can manually trigger any scheduled task:

### Email Extraction
```bash
# All 4 types (weekly)
python he_alerts/fetch_latest_emails.py daily crypto etfs ideas

# Daily types only
python he_alerts/fetch_latest_emails.py daily crypto
```

### Alert Generation
```bash
# Morning session
python he_alerts/alert_workflow.py --session AM

# Afternoon session
python he_alerts/alert_workflow.py --session PM
```

## Monitoring

The scheduler provides detailed logging:

```
2025-07-25 09:00:00 - First market day of week - extracting all 4 email types
2025-07-25 09:05:32 - Successfully processed 4 email types
2025-07-25 10:45:00 - Running morning alert workflow
2025-07-25 10:47:15 - Morning alerts completed successfully
2025-07-25 14:30:00 - Running afternoon alert workflow
2025-07-25 14:32:08 - Afternoon alerts completed successfully
```

## Scheduler Status

View current scheduler status and next run times:

```python
scheduler.get_schedule_info()
```

Returns:
```json
[
  {
    "id": "email_extraction",
    "name": "Email Extraction (Market Days Only)",
    "next_run": "2025-07-26 09:00:00 EST",
    "trigger": "cron[day_of_week='mon-fri', hour='9', minute='0']"
  },
  {
    "id": "morning_alerts",
    "name": "Morning Alerts (10:45 AM)",
    "next_run": "2025-07-26 10:45:00 EST",
    "trigger": "cron[day_of_week='mon-fri', hour='10', minute='45']"
  },
  {
    "id": "afternoon_alerts",
    "name": "Afternoon Alerts (2:30 PM)",
    "next_run": "2025-07-26 14:30:00 EST",
    "trigger": "cron[day_of_week='mon-fri', hour='14', minute='30']"
  }
]
```

## Error Handling

The scheduler includes robust error handling:

1. **Email Extraction Failures**: Logs error and continues with next scheduled run
2. **Alert Generation Failures**: Logs error, attempts to notify via email
3. **Market Holiday Check**: Always performed before any task execution
4. **Database Connection Issues**: Retries with exponential backoff

## Integration with Replit

For Replit deployment, update `.replit` to use the automated scheduler:

```toml
run = "python he_alerts/automated_scheduler.py"
```

The scheduler will automatically:
- Start when the Repl runs
- Handle all scheduled tasks
- Adjust for market holidays
- Log all activities

## Troubleshooting

### Scheduler Not Running Tasks
1. Check if today is a market holiday
2. Verify timezone is set to America/New_York
3. Check scheduler logs for errors

### Wrong Email Types Extracted
1. Verify it's detecting first market day correctly
2. Check market calendar for holidays
3. Review extraction logs

### Alerts Not Generated
1. Ensure email extraction completed successfully
2. Check IBKR connection
3. Verify SMTP configuration
4. Review alert generation logs