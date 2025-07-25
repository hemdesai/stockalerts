"""
Email processing services for HE Alerts.
"""
from app.services.email.gmail_client import GmailClient
from app.services.email.processors.mistral import MistralProcessor
from app.services.email.base import BaseEmailExtractor
from app.services.email.extractors import (
    DailyExtractor,
    CryptoExtractor, 
    IdeasExtractor,
    ETFExtractor,
    get_extractor
)

__all__ = [
    "GmailClient",
    "MistralProcessor",
    "BaseEmailExtractor",
    "DailyExtractor",
    "CryptoExtractor",
    "IdeasExtractor", 
    "ETFExtractor",
    "get_extractor",
]