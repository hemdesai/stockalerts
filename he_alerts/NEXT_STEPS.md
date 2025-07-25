# Next Steps: Alert Generation Module

## Quick Start Commands

```bash
# 1. Test current system status
cd he_alerts
python check_price_results.py

# 2. Run price update if needed
python test_price_update.py AM

# 3. Check for alerts
python -c "import asyncio; from app.core.database import AsyncSessionLocal; from app.services.database.alert_service import AlertService; async def check(): async with AsyncSessionLocal() as db: alerts = await AlertService().get_recent_alerts(db); print(f'Recent alerts: {len(alerts)}'); asyncio.run(check())"
```

## Alert Module Requirements

### 1. Email Templates
- Buy alert template
- Sell alert template
- Daily summary template
- Include stock details, prices, thresholds, sentiment

### 2. Alert Service Features
- Aggregate alerts by session (AM/PM)
- Format alerts with market context
- Track sent alerts to prevent duplicates
- Support immediate and batched sending

### 3. SMTP Configuration
Already configured in .env:
- EMAIL_SENDER=hemdesai@gmail.com
- EMAIL_PASSWORD=[app password]
- EMAIL_RECIPIENT=hemdesai@gmail.com

### 4. Reference Code Structure
From `5_send_alerts.py`:
- Uses email.mime for HTML emails
- Tracks sent alerts in database
- Groups alerts by type (BUY/SELL)
- Includes price movement percentages

## Database Query for Pending Alerts

```sql
-- Stocks that crossed thresholds
SELECT s.ticker, s.category, s.sentiment,
       s.am_price, s.buy_trade, s.sell_trade,
       CASE 
         WHEN s.am_price <= s.buy_trade THEN 'BUY'
         WHEN s.am_price >= s.sell_trade THEN 'SELL'
       END as alert_type
FROM stocks s
WHERE s.is_active = true
  AND s.am_price IS NOT NULL
  AND (s.am_price <= s.buy_trade OR s.am_price >= s.sell_trade)
ORDER BY s.category, s.ticker;
```

## Testing Alert Generation

1. AMZN already triggered a SELL alert (233.00 >= 231.00)
2. Can manually adjust thresholds to trigger more test alerts
3. Use test email endpoint before enabling automated sending

## Implementation Order

1. Create email templates (HTML)
2. Build alert formatter service
3. Implement alert aggregation logic
4. Add email sending service
5. Create alert scheduler
6. Add API endpoints
7. Test end-to-end flow