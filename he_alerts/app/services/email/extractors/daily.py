"""
Daily RISK RANGE signals email extractor.
"""
from typing import Dict, List, Any
import yfinance as yf

from app.core.logging import get_logger
from app.services.email.base import BaseEmailExtractor

logger = get_logger(__name__)


class DailyExtractor(BaseEmailExtractor):
    """
    Extractor for daily RISK RANGE signals emails.
    """
    
    def get_email_type(self) -> str:
        return "daily"
    
    def get_category(self) -> str:
        return "daily"
    
    async def extract_and_enrich(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Extract daily signals and enrich with company names.
        
        Args:
            hours: Hours back to search for emails
            
        Returns:
            List of enriched extraction results
        """
        results = await self.extract_from_recent_emails(hours)
        
        for result in results:
            if result.get('extracted_items'):
                await self._enrich_with_company_names(result['extracted_items'])
        
        return results
    
    async def _enrich_with_company_names(self, items: List[Dict[str, Any]]) -> None:
        """
        Enrich stock items with company names from yfinance.
        
        Args:
            items: List of extracted stock items to enrich
        """
        for item in items:
            try:
                ticker = item.get('ticker')
                if not ticker:
                    continue
                
                logger.debug(f"Fetching company name for {ticker}")
                
                # Get company info from yfinance
                stock = yf.Ticker(ticker)
                info = stock.info
                
                # Extract company name
                company_name = (
                    info.get('shortName') or 
                    info.get('longName') or 
                    info.get('displayName') or
                    ""
                )
                
                if company_name:
                    item['name'] = company_name
                    logger.debug(f"Found name for {ticker}: {company_name}")
                else:
                    logger.debug(f"No name found for {ticker}")
                    
            except Exception as e:
                logger.warning(f"Error fetching name for {item.get('ticker')}: {e}")
                continue
    
    def validate_daily_data(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Additional validation specific to daily signals.
        
        Args:
            items: List of extracted items
            
        Returns:
            List of validated items
        """
        validated = []
        
        for item in items:
            try:
                ticker = item.get('ticker', '').upper()
                
                # Skip common invalid patterns
                if not ticker or len(ticker) < 1 or len(ticker) > 6:
                    continue
                
                # Skip if no trading levels
                if not item.get('buy_trade') and not item.get('sell_trade'):
                    continue
                
                # Validate price ranges are reasonable
                buy_price = item.get('buy_trade')
                sell_price = item.get('sell_trade')
                
                if buy_price and sell_price:
                    # Sell should be higher than buy for normal signals
                    if sell_price <= buy_price:
                        logger.warning(f"Invalid price range for {ticker}: "
                                     f"buy={buy_price}, sell={sell_price}")
                        # Don't skip, might be a short signal
                
                validated.append(item)
                
            except Exception as e:
                logger.warning(f"Error validating daily item {item}: {e}")
                continue
        
        return validated
    
    async def process_latest_daily_email(self) -> Dict[str, Any]:
        """
        Process the most recent daily email and return summary.
        
        Returns:
            Processing summary
        """
        logger.info("Processing latest daily RISK RANGE email")
        
        results = await self.extract_and_enrich(hours=2)  # Last 2 hours
        
        if not results:
            return {
                'success': False,
                'message': 'No daily emails found in the last 2 hours',
                'processed_count': 0,
                'extracted_count': 0
            }
        
        # Process the most recent email
        latest_result = results[0]
        items = latest_result.get('extracted_items', [])
        
        # Additional validation
        validated_items = self.validate_daily_data(items)
        latest_result['extracted_items'] = validated_items
        
        return {
            'success': True,
            'message': f'Successfully processed daily email',
            'processed_count': 1,
            'extracted_count': len(validated_items),
            'email_id': latest_result.get('email_data', {}).get('message_id'),
            'processing_time': latest_result.get('processing_metadata', {}).get('processing_time'),
            'confidence_score': latest_result.get('processing_metadata', {}).get('confidence_score'),
            'result': latest_result
        }