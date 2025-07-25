"""
Investment Ideas Newsletter email extractor.
"""
from typing import Dict, List, Any
import yfinance as yf

from app.core.logging import get_logger
from app.services.email.base import BaseEmailExtractor

logger = get_logger(__name__)


class IdeasExtractor(BaseEmailExtractor):
    """
    Extractor for Investment Ideas Newsletter emails.
    """
    
    def get_email_type(self) -> str:
        return "ideas"
    
    def get_category(self) -> str:
        return "ideas"
    
    def validate_ideas_data(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Additional validation specific to investment ideas.
        
        Args:
            items: List of extracted items
            
        Returns:
            List of validated items
        """
        validated = []
        
        for item in items:
            try:
                ticker = item.get('ticker', '').upper().strip()
                
                # Basic ticker validation
                if not ticker or len(ticker) < 1 or len(ticker) > 6:
                    continue
                
                # Ideas emails might have target prices instead of buy/sell levels
                # Try to infer buy/sell from available data
                buy_price = item.get('buy_trade')
                sell_price = item.get('sell_trade')
                
                # If we have investment thesis but no clear levels, 
                # we might need to set reasonable defaults or skip
                if not buy_price and not sell_price:
                    logger.info(f"No clear trading levels for idea {ticker}, skipping")
                    continue
                
                # Investment ideas often have higher confidence in direction
                sentiment = item.get('sentiment')
                if sentiment and sentiment in ['bullish', 'bearish']:
                    # Ideas with clear sentiment are valuable even without exact levels
                    pass
                
                validated.append(item)
                
            except Exception as e:
                logger.warning(f"Error validating ideas item {item}: {e}")
                continue
        
        return validated
    
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
                    
                    # Add sector information if available
                    sector = info.get('sector')
                    if sector:
                        if 'extraction_metadata' not in item:
                            item['extraction_metadata'] = {}
                        item['extraction_metadata']['sector'] = sector
                        
                else:
                    logger.debug(f"No name found for {ticker}")
                    
            except Exception as e:
                logger.warning(f"Error fetching info for {item.get('ticker')}: {e}")
                continue
    
    async def extract_and_enrich(self, hours: int = 168) -> List[Dict[str, Any]]:  # 7 days default
        """
        Extract investment ideas and enrich with company information.
        
        Args:
            hours: Hours back to search for emails (default 7 days for weekly ideas)
            
        Returns:
            List of enriched extraction results
        """
        results = await self.extract_from_recent_emails(hours)
        
        for result in results:
            if result.get('extracted_items'):
                # Validate ideas-specific data
                validated_items = self.validate_ideas_data(result['extracted_items'])
                
                # Enrich with company names and sector info
                await self._enrich_with_company_names(validated_items)
                
                result['extracted_items'] = validated_items
                result['processing_metadata']['ideas_validated'] = len(validated_items)
        
        return results
    
    async def process_latest_ideas_email(self) -> Dict[str, Any]:
        """
        Process the most recent ideas email and return summary.
        
        Returns:
            Processing summary
        """
        logger.info("Processing latest Investment Ideas Newsletter email")
        
        # Ideas emails come weekly, so search last 7 days
        results = await self.extract_and_enrich(hours=168)
        
        if not results:
            return {
                'success': False,
                'message': 'No ideas emails found in the last 7 days',
                'processed_count': 0,
                'extracted_count': 0
            }
        
        # Process the most recent email
        latest_result = results[0]
        items = latest_result.get('extracted_items', [])
        
        # Extract sectors for summary
        sectors = []
        for item in items:
            sector = item.get('extraction_metadata', {}).get('sector')
            if sector and sector not in sectors:
                sectors.append(sector)
        
        return {
            'success': True,
            'message': f'Successfully processed investment ideas email',
            'processed_count': 1,
            'extracted_count': len(items),
            'email_id': latest_result.get('email_data', {}).get('message_id'),
            'processing_time': latest_result.get('processing_metadata', {}).get('processing_time'),
            'confidence_score': latest_result.get('processing_metadata', {}).get('confidence_score'),
            'sectors_covered': sectors,
            'tickers': [item['ticker'] for item in items],
            'result': latest_result
        }
    
    def analyze_investment_themes(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze investment themes from extracted ideas.
        
        Args:
            items: List of extracted investment ideas
            
        Returns:
            Theme analysis summary
        """
        themes = {
            'bullish_count': 0,
            'bearish_count': 0,
            'sectors': {},
            'avg_buy_price': 0,
            'avg_sell_price': 0,
            'price_ranges': []
        }
        
        buy_prices = []
        sell_prices = []
        
        for item in items:
            # Count sentiment
            sentiment = item.get('sentiment', '').lower()
            if sentiment == 'bullish':
                themes['bullish_count'] += 1
            elif sentiment == 'bearish':
                themes['bearish_count'] += 1
            
            # Track sectors
            sector = item.get('extraction_metadata', {}).get('sector')
            if sector:
                themes['sectors'][sector] = themes['sectors'].get(sector, 0) + 1
            
            # Collect prices
            if item.get('buy_trade'):
                buy_prices.append(item['buy_trade'])
            if item.get('sell_trade'):
                sell_prices.append(item['sell_trade'])
            
            # Calculate price range
            if item.get('buy_trade') and item.get('sell_trade'):
                price_range = ((item['sell_trade'] - item['buy_trade']) / item['buy_trade']) * 100
                themes['price_ranges'].append(price_range)
        
        # Calculate averages
        if buy_prices:
            themes['avg_buy_price'] = sum(buy_prices) / len(buy_prices)
        if sell_prices:
            themes['avg_sell_price'] = sum(sell_prices) / len(sell_prices)
        if themes['price_ranges']:
            themes['avg_price_range_percent'] = sum(themes['price_ranges']) / len(themes['price_ranges'])
        
        return themes