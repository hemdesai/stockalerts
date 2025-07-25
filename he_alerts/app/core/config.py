"""
Application configuration settings using Pydantic Settings.
"""
from functools import lru_cache
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application
    APP_NAME: str = "HE Alerts"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = Field(..., min_length=32)
    LOG_LEVEL: str = "INFO"
    
    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL database URL")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 0
    
    # API
    API_V1_STR: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Gmail API
    GMAIL_CREDENTIALS_PATH: str = "credentials/gmail_credentials.json"
    GMAIL_TOKEN_PATH: str = "credentials/gmail_token.json" 
    GMAIL_SCOPES: List[str] = ["https://www.googleapis.com/auth/gmail.readonly"]
    
    # Email Settings
    EMAIL_SENDER: str = Field(..., description="Sender email address")
    EMAIL_PASSWORD: str = Field(..., description="App password for email")
    EMAIL_RECIPIENT: str = Field(..., description="Alert recipient email")
    EMAIL_SMTP_SERVER: str = "smtp.gmail.com"
    EMAIL_SMTP_PORT: int = 587
    
    # Alert Email Settings
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = Field(default=None, description="SMTP username (email)")
    SMTP_PASSWORD: Optional[str] = Field(default=None, description="SMTP password")
    ALERT_FROM_EMAIL: Optional[str] = Field(default=None, description="From email for alerts")
    ALERT_TO_EMAILS: List[str] = Field(default_factory=lambda: ["hemdesai@gmail.com"])
    ALERT_BCC_EMAILS: List[str] = Field(default_factory=list)
    
    # AI/ML
    MISTRAL_API_KEY: str = Field(..., description="Mistral AI API key")
    MISTRAL_MODEL: str = "mistral-large-latest"
    
    # IBKR Configuration
    IBKR_HOST: str = "127.0.0.1"
    IBKR_PORT: int = 7497
    IBKR_CLIENT_ID: int = 1
    IBKR_PAPER_TRADING: bool = True
    
    # Scheduler (Eastern Time)
    MORNING_PRICE_TIME: str = "10:45"
    AFTERNOON_PRICE_TIME: str = "14:30"
    EMAIL_PROCESSING_TIME: str = "08:50"
    TIMEZONE: str = "America/New_York"
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 8001
    
    # Development
    RELOAD: bool = False
    WORKERS: int = 1
    
    # Replit specific
    REPLIT_DB_URL: Optional[str] = None
    REPLIT_SECRET: Optional[str] = None
    
    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    @validator("ALERT_TO_EMAILS", "ALERT_BCC_EMAILS", pre=True)
    def assemble_email_list(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []
    
    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v, values):
        """Use Replit DB URL if available, otherwise use provided URL."""
        if values.get("REPLIT_DB_URL"):
            return values["REPLIT_DB_URL"]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()