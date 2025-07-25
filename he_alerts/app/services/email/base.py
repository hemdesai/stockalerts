"""
Base email extractor with common functionality.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
import hashlib

from app.core.logging import get_logger
from app.services.email.gmail_client import GmailClient
from app.services.email.processors.mistral import MistralProcessor

logger = get_logger(__name__)


class BaseEmailExtractor(ABC):
    """
    Base class for all email extractors with common functionality.
    """
    
    def __init__(self):
        self.gmail_client = GmailClient()
        self.mistral_processor = MistralProcessor()
        self.email_type = self.get_email_type()
        self.category = self.get_category()
    
    @abstractmethod
    def get_email_type(self) -> str:
        """Return the email type (daily, crypto, ideas, etf)."""
        pass
    
    @abstractmethod
    def get_category(self) -> str:
        """Return the database category (daily, digitalassets, ideas, etfs)."""
        pass
    
    def get_email_pattern(self) -> str:
        """Return the subject pattern to match for this email type."""
        patterns = {
            "daily": "FW: RISK RANGE™ SIGNALS:",
            "crypto": "FW: CRYPTO QUANT",
            "ideas": "FW: Investing Ideas Newsletter:",
            "etf": "FW: ETF Pro Plus - Levels"
        }
        return patterns.get(self.email_type, "")
    
    async def extract_from_recent_emails(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Extract data from recent emails of this type.
        
        Args:
            hours: Number of hours back to search
            
        Returns:
            List of extraction results
        """
        logger.info(f"Starting extraction for {self.email_type} emails from last {hours} hours")
        
        # Fetch recent emails
        emails = await self.gmail_client.fetch_recent_emails(hours=hours)
        
        # Filter for this email type
        relevant_emails = [
            email for email in emails 
            if email.get('email_type') == self.email_type
        ]
        
        logger.info(f"Found {len(relevant_emails)} {self.email_type} emails to process")
        
        results = []
        for email in relevant_emails:
            try:
                result = await self.extract_from_email(email)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error processing email {email.get('message_id')}: {e}")
                continue
        
        logger.info(f"Successfully processed {len(results)} {self.email_type} emails")
        return results
    
    async def extract_from_email(self, email_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract structured data from a single email.
        
        Args:
            email_data: Email data dictionary from Gmail client
            
        Returns:
            Extraction result dictionary or None
        """
        try:
            logger.info(f"Processing {self.email_type} email: {email_data.get('message_id')}")
            
            # Get email content (prefer HTML, fallback to text)
            content = email_data.get('body_html') or email_data.get('body_text')
            if not content:
                logger.warning(f"No content found in email {email_data.get('message_id')}")
                return None
            
            # For daily emails, try HTML parsing first
            if self.email_type == "daily":
                logger.info("Using HTML parser for daily email")
                from app.services.email.extractors.daily_parser import parse_daily_email, validate_daily_stocks
                
                start_time = datetime.now()
                parsed_items = parse_daily_email(content)
                validated_items = validate_daily_stocks(parsed_items)
                processing_time = (datetime.now() - start_time).total_seconds()
                
                validated_result = {
                    "extracted_items": validated_items,
                    "confidence_score": 0.95 if validated_items else 0.0,
                    "extraction_method": "html_parser",
                    "processing_time": processing_time,
                    "validated_count": len(validated_items)
                }
                
                # If HTML parsing failed, fall back to Mistral
                if not validated_items:
                    logger.info("HTML parsing returned no results, falling back to Mistral")
                    extraction_result = await self.mistral_processor.extract_data(
                        email_content=content,
                        email_type=self.email_type
                    )
                    validated_result = await self.mistral_processor.validate_extraction(extraction_result)
            
            # For ETF emails, try specialized ETF parser
            elif self.email_type == "etf":
                logger.info("Using ETF parser for ETF Pro Plus email")
                from app.services.email.extractors.etf_parser import extract_etf_stocks, validate_etf_stocks
                
                start_time = datetime.now()
                parsed_items = extract_etf_stocks(content)
                validated_items = validate_etf_stocks(parsed_items)
                processing_time = (datetime.now() - start_time).total_seconds()
                
                validated_result = {
                    "extracted_items": validated_items,
                    "confidence_score": 0.90 if validated_items else 0.0,
                    "extraction_method": "etf_parser",
                    "processing_time": processing_time,
                    "validated_count": len(validated_items)
                }
                
                # If ETF parsing failed, fall back to Mistral
                if not validated_items:
                    logger.info("ETF parsing returned no results, falling back to Mistral")
                    extraction_result = await self.mistral_processor.extract_data(
                        email_content=content,
                        email_type=self.email_type
                    )
                    validated_result = await self.mistral_processor.validate_extraction(extraction_result)
            
            # For IDEAS emails, try specialized IDEAS parser
            elif self.email_type == "ideas":
                logger.info("Using IDEAS parser for Investing Ideas Newsletter email")
                from app.services.email.extractors.ideas_parser import extract_ideas_stocks, validate_ideas_stocks
                
                start_time = datetime.now()
                # Pass empty attachments list for now - will need to get actual attachments
                parsed_items = extract_ideas_stocks(content, [])
                validated_items = validate_ideas_stocks(parsed_items)
                processing_time = (datetime.now() - start_time).total_seconds()
                
                validated_result = {
                    "extracted_items": validated_items,
                    "confidence_score": 0.85 if validated_items else 0.0,
                    "extraction_method": "ideas_parser",
                    "processing_time": processing_time,
                    "validated_count": len(validated_items)
                }
                
                # If IDEAS parsing failed, fall back to Mistral
                if not validated_items:
                    logger.info("IDEAS parsing returned no results, falling back to Mistral")
                    extraction_result = await self.mistral_processor.extract_data(
                        email_content=content,
                        email_type=self.email_type
                    )
                    validated_result = await self.mistral_processor.validate_extraction(extraction_result)
            
            # For CRYPTO emails, try specialized crypto parser
            elif self.email_type == "crypto":
                logger.info("Using crypto parser for CRYPTO QUANT email")
                from app.services.email.extractors.crypto_parser import extract_crypto_stocks, validate_crypto_stocks
                
                start_time = datetime.now()
                parsed_items = extract_crypto_stocks(content)
                validated_items = validate_crypto_stocks(parsed_items)
                processing_time = (datetime.now() - start_time).total_seconds()
                
                validated_result = {
                    "extracted_items": validated_items,
                    "confidence_score": 0.90 if validated_items else 0.0,
                    "extraction_method": "crypto_parser",
                    "processing_time": processing_time,
                    "validated_count": len(validated_items)
                }
                
                # If crypto parsing failed, fall back to Mistral
                if not validated_items:
                    logger.info("Crypto parsing returned no results, falling back to Mistral")
                    extraction_result = await self.mistral_processor.extract_data(
                        email_content=content,
                        email_type=self.email_type
                    )
                    validated_result = await self.mistral_processor.validate_extraction(extraction_result)
            
            else:
                # Use Mistral AI to extract data for other email types
                extraction_result = await self.mistral_processor.extract_data(
                    email_content=content,
                    email_type=self.email_type
                )
                
                # Validate extraction
                validated_result = await self.mistral_processor.validate_extraction(extraction_result)
            
            # Add email metadata
            result = {
                'email_data': email_data,
                'extraction_result': validated_result,
                'extracted_items': validated_result.get('extracted_items', []),
                'processing_metadata': {
                    'email_type': self.email_type,
                    'category': self.category,
                    'processed_at': datetime.utcnow().isoformat(),
                    'extraction_method': validated_result.get('extraction_method', 'mistral_ai'),
                    'confidence_score': validated_result.get('confidence_score', 0.0),
                    'processing_time': validated_result.get('processing_time', 0.0),
                    'ai_model_used': validated_result.get('ai_model_used'),
                    'validated_count': validated_result.get('validated_count', 0)
                }
            }
            
            # Log extraction summary
            item_count = len(result['extracted_items'])
            confidence = result['processing_metadata']['confidence_score']
            logger.info(f"Extracted {item_count} items from {self.email_type} email "
                       f"(confidence: {confidence:.2f})")
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting from {self.email_type} email: {e}")
            return None
    
    async def extract_from_email_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Extract data from a specific email by message ID.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Extraction result or None
        """
        # Fetch email by ID
        email_data = await self.gmail_client.get_email_by_id(message_id)
        if not email_data:
            logger.error(f"Could not fetch email {message_id}")
            return None
        
        # Check if it's the right type
        if email_data.get('email_type') != self.email_type:
            logger.warning(f"Email {message_id} is not {self.email_type} type")
            return None
        
        return await self.extract_from_email(email_data)
    
    def prepare_stock_data(self, extracted_items: List[Dict[str, Any]], 
                          email_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Prepare extracted items for database insertion.
        
        Args:
            extracted_items: List of extracted stock data
            email_data: Original email data
            
        Returns:
            List of stock data ready for database
        """
        stock_data = []
        
        for item in extracted_items:
            try:
                stock_item = {
                    'ticker': item['ticker'],
                    'name': None,  # Will be populated later via yfinance/IBKR
                    'category': self.category,
                    'sentiment': item.get('sentiment'),
                    'buy_trade': item.get('buy_trade'),
                    'sell_trade': item.get('sell_trade'),
                    'source_email_id': email_data.get('message_id'),
                    'extraction_metadata': {
                        'email_type': self.email_type,
                        'subject': email_data.get('subject'),
                        'received_date': email_data.get('received_date').isoformat() if email_data.get('received_date') else None,
                        'extraction_confidence': item.get('confidence_score', 0.0),
                        'ai_model_used': email_data.get('ai_model_used')
                    },
                    'is_active': True
                }
                
                stock_data.append(stock_item)
                
            except Exception as e:
                logger.warning(f"Error preparing stock data for {item}: {e}")
                continue
        
        return stock_data
    
    def create_email_log_entry(self, email_data: Dict[str, Any], 
                              extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create email log entry for database.
        
        Args:
            email_data: Original email data
            extraction_result: Processing result
            
        Returns:
            Email log data dictionary
        """
        processing_metadata = extraction_result.get('processing_metadata', {})
        extracted_items = extraction_result.get('extracted_items', [])
        
        return {
            'message_id': email_data.get('message_id'),
            'thread_id': email_data.get('thread_id'),
            'subject': email_data.get('subject'),
            'sender': email_data.get('sender'),
            'received_date': email_data.get('received_date'),
            'email_type': self.email_type,
            'category': self.category,
            'processed': True,
            'processed_at': datetime.utcnow(),
            'processing_duration': int(processing_metadata.get('processing_time', 0)),
            'extraction_successful': len(extracted_items) > 0,
            'extracted_count': len(extracted_items),
            'extraction_method': 'mistral_ai',
            'raw_content_hash': email_data.get('raw_content_hash'),
            'extraction_metadata': processing_metadata,
            'ai_model_used': processing_metadata.get('ai_model_used'),
            'error_occurred': 'error' in extraction_result.get('extraction_result', {}),
            'error_message': extraction_result.get('extraction_result', {}).get('error')
        }
    
    def calculate_content_hash(self, content: str) -> str:
        """
        Calculate SHA256 hash of content.
        
        Args:
            content: Content to hash
            
        Returns:
            SHA256 hash as hex string
        """
        if not content:
            return ""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()