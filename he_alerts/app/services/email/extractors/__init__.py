"""
Email extractors for different types of financial newsletters.
"""
from app.services.email.extractors.daily import DailyExtractor
from app.services.email.extractors.crypto import CryptoExtractor
from app.services.email.extractors.ideas import IdeasExtractor
from app.services.email.extractors.etf import ETFExtractor

__all__ = [
    "DailyExtractor",
    "CryptoExtractor", 
    "IdeasExtractor",
    "ETFExtractor",
]


def get_extractor(email_type: str):
    """
    Get the appropriate extractor for an email type.
    
    Args:
        email_type: Type of email (daily, crypto, ideas, etf)
        
    Returns:
        Extractor instance or None if not found
    """
    extractors = {
        "daily": DailyExtractor,
        "crypto": CryptoExtractor,
        "ideas": IdeasExtractor,
        "etf": ETFExtractor
    }
    
    extractor_class = extractors.get(email_type)
    if extractor_class:
        return extractor_class()
    
    return None