# StockAlerts

A comprehensive stock alerting system with email extraction and Interactive Brokers integration.

## Projects

### 1. HE Alerts (`/he_alerts/`) - Production System
Automated stock alert system that:
- Fetches daily financial emails from Gmail
- Extracts trading signals using AI (OCR for images)
- Updates PostgreSQL database with latest data
- Fetches real-time prices from Interactive Brokers
- Generates and sends price-based alerts via email

**[Full documentation →](he_alerts/README.md)**

**Quick Start:**
```bash
cd he_alerts
pip install -r requirements.txt
cp .env.example .env
# Configure your .env file
python scripts/init_db.py
python alert_workflow.py
```

### 2. Original StockAlert Scripts (`/stockalert/`)
Legacy email extraction and alerting scripts:
- Email extractors for various newsletter types
- MCP (Model Context Protocol) server for Claude Desktop
- SQLite-based data storage
- IBKR price fetching scripts

## Repository Structure

```
stockalert/
├── he_alerts/              # Production system (PostgreSQL, async)
│   ├── app/                # FastAPI application
│   ├── scripts/            # Utility scripts
│   ├── docs/               # Documentation
│   ├── .env.example        # Environment template
│   ├── requirements.txt    # Dependencies
│   └── README.md           # Detailed documentation
│
├── stockalert/             # Original scripts (SQLite, sync)
│   ├── scripts/            
│   │   ├── 0_extractors/   # Email extractors
│   │   ├── 1_mcp_server.py # MCP server
│   │   ├── 4_prices_ibkr.py # IBKR price fetcher
│   │   └── 5_send_alerts.py # Alert sender
│   ├── data/               # SQLite DB and CSVs
│   └── utils/              # Shared utilities
│
└── logs/                   # Application logs
```

## Choosing Which System to Use

### Use HE Alerts if you need:
- Production-ready system with validation workflow
- PostgreSQL database (e.g., Neon.tech)
- Async processing for better performance
- Sentiment-based alert rules
- Delete-before-insert data strategy (no stale data)
- Replit deployment support

### Use Original Scripts if you need:
- Simple SQLite-based storage
- Direct CSV file manipulation
- MCP integration with Claude Desktop
- Legacy compatibility

## Environment Setup

Both systems use environment variables for configuration. See each project's documentation for specific requirements:
- HE Alerts: `he_alerts/.env.example`
- Original: `stockalert/env_template.txt`

## Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## License

Private and proprietary.