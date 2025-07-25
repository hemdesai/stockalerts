# HE Alerts - Project Structure

## New Architecture Design

### Tech Stack
- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Email**: Gmail API with async processing
- **Price Data**: IBKR (ib_async)
- **Scheduling**: APScheduler
- **Deployment**: Docker + Replit
- **Monitoring**: Structured logging

### Directory Structure
```
he_alerts/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py            # Dependencies
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── endpoints/
│   │       │   ├── __init__.py
│   │       │   ├── health.py
│   │       │   ├── stocks.py
│   │       │   ├── alerts.py
│   │       │   └── admin.py
│   │       └── api.py         # API router
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # Settings and configuration
│   │   ├── database.py        # Database connection
│   │   ├── logging.py         # Logging configuration
│   │   └── scheduler.py       # APScheduler setup
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py           # Base model
│   │   ├── stock.py          # Stock model
│   │   ├── alert.py          # Alert model
│   │   └── email_log.py      # Email processing log
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── stock.py          # Stock Pydantic schemas
│   │   ├── alert.py          # Alert schemas
│   │   └── email.py          # Email schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── email/
│   │   │   ├── __init__.py
│   │   │   ├── base.py       # Base email extractor
│   │   │   ├── gmail_client.py
│   │   │   ├── extractors/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── daily.py
│   │   │   │   ├── crypto.py
│   │   │   │   ├── ideas.py
│   │   │   │   └── etf.py
│   │   │   └── processors/
│   │   │       ├── __init__.py
│   │   │       └── mistral.py # AI processing
│   │   ├── ibkr/
│   │   │   ├── __init__.py
│   │   │   ├── client.py     # IBKR async client
│   │   │   ├── contracts.py  # Contract resolution
│   │   │   └── price_fetcher.py
│   │   ├── alerts/
│   │   │   ├── __init__.py
│   │   │   ├── generator.py  # Alert logic
│   │   │   └── sender.py     # Email sender
│   │   └── scheduler/
│   │       ├── __init__.py
│   │       ├── jobs.py       # Scheduled job definitions
│   │       └── tasks.py      # Individual tasks
│   └── utils/
│       ├── __init__.py
│       ├── datetime.py       # Timezone utilities
│       └── validators.py     # Custom validators
├── alembic/
│   ├── versions/
│   ├── env.py
│   ├── script.py.mako
│   └── alembic.ini
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_api/
│   ├── test_services/
│   └── test_utils/
├── scripts/
│   ├── __init__.py
│   ├── init_db.py           # Database initialization
│   └── migrate_from_sqlite.py # Migration script
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── .dockerignore
├── docs/
│   ├── api.md
│   ├── deployment.md
│   └── development.md
├── .env.example
├── .gitignore
├── requirements.txt
├── pyproject.toml
├── README.md
└── replit.nix             # Replit configuration
```

### Key Features
1. **Email Processing Pipeline**: Async Gmail → AI extraction → Database
2. **Price Updates**: Scheduled IBKR price fetching (10:45 AM & 2:30 PM)
3. **Alert System**: Rule-based alerts with email notifications
4. **REST API**: Monitor system, manual triggers, health checks
5. **Database**: PostgreSQL with proper relationships and indexing
6. **Deployment**: Docker-ready for Replit or any cloud platform

### Daily Workflow (Automated)
```
8:50 AM  → Email processing starts
9:15 AM  → Data extraction complete
10:45 AM → Morning price update + alerts
2:30 PM  → Afternoon price update + alerts
```