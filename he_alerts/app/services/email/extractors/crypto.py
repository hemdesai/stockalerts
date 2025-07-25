"""
Crypto QUANT signals email extractor.
"""
from typing import Dict, List, Any

from app.core.logging import get_logger
from app.services.email.base import BaseEmailExtractor
from app.services.email.extractors.crypto_parser import extract_crypto_stocks, validate_crypto_stocks

logger = get_logger(__name__)


class CryptoExtractor(BaseEmailExtractor):
    """
    Extractor for crypto QUANT signals emails.
    """
    
    def get_email_type(self) -> str:
        return "crypto"
    
    def get_category(self) -> str:
        return "digitalassets"
    
    def __init__(self):
        super().__init__()
        # Crypto symbol mappings for normalization
        self.crypto_mappings = {
            "BITCOIN": "BTC",
            "ETHEREUM": "ETH", 
            "SOLANA": "SOL",
            "CARDANO": "ADA",
            "AVALANCHE": "AVAX",
            "CHAINLINK": "LINK",
            "POLYGON": "MATIC",
            "DOGECOIN": "DOGE",
            "SHIBA": "SHIB",
            "LITECOIN": "LTC",
            "XRP": "XRP",
            "BNB": "BNB",
            "POLKADOT": "DOT",
            "UNISWAP": "UNI",
            "MAKER": "MKR"
        }
    
    def normalize_crypto_ticker(self, ticker: str) -> str:
        """
        Normalize crypto ticker to standard format.
        
        Args:
            ticker: Raw ticker from extraction
            
        Returns:
            Normalized ticker symbol
        """
        if not ticker:
            return ticker
        
        ticker_upper = ticker.upper().strip()
        
        # Direct mapping
        if ticker_upper in self.crypto_mappings:
            return self.crypto_mappings[ticker_upper]
        
        # Check if it's already a standard symbol
        standard_symbols = set(self.crypto_mappings.values())
        if ticker_upper in standard_symbols:
            return ticker_upper
        
        # Handle common patterns
        if "BTC" in ticker_upper or "BITCOIN" in ticker_upper:
            return "BTC"
        elif "ETH" in ticker_upper or "ETHEREUM" in ticker_upper:
            return "ETH"
        elif "SOL" in ticker_upper or "SOLANA" in ticker_upper:
            return "SOL"
        
        # Return as-is if no mapping found
        return ticker_upper
    
    def validate_crypto_data(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Additional validation specific to crypto signals.
        
        Args:
            items: List of extracted items
            
        Returns:
            List of validated items
        """
        validated = []
        
        for item in items:
            try:
                # Normalize ticker
                raw_ticker = item.get('ticker', '')
                normalized_ticker = self.normalize_crypto_ticker(raw_ticker)
                
                if not normalized_ticker or len(normalized_ticker) < 2:
                    logger.warning(f"Invalid crypto ticker: {raw_ticker}")
                    continue
                
                item['ticker'] = normalized_ticker
                
                # Validate prices are reasonable for crypto
                buy_price = item.get('buy_trade')
                sell_price = item.get('sell_trade')
                
                if buy_price:
                    if buy_price < 0 or buy_price > 10000000:  # Reasonable crypto price range
                        logger.warning(f"Unusual buy price for {normalized_ticker}: {buy_price}")
                
                if sell_price:
                    if sell_price < 0 or sell_price > 10000000:
                        logger.warning(f"Unusual sell price for {normalized_ticker}: {sell_price}")
                
                # Skip if no trading levels
                if not buy_price and not sell_price:
                    logger.warning(f"No trading levels for {normalized_ticker}")
                    continue
                
                # Set default sentiment for crypto if missing
                if not item.get('sentiment'):
                    item['sentiment'] = 'neutral'
                
                validated.append(item)
                
            except Exception as e:
                logger.warning(f"Error validating crypto item {item}: {e}")
                continue
        
        return validated
    
    async def extract_and_enrich(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Extract crypto signals and enrich with metadata.
        
        Args:
            hours: Hours back to search for emails
            
        Returns:
            List of enriched extraction results
        """
        results = await self.extract_from_recent_emails(hours)
        
        for result in results:
            if result.get('extracted_items'):
                # Validate and normalize crypto data
                validated_items = self.validate_crypto_data(result['extracted_items'])
                result['extracted_items'] = validated_items
                
                # Add crypto-specific metadata
                result['processing_metadata']['crypto_symbols_mapped'] = len(validated_items)
        
        return results
    
    async def process_latest_crypto_email(self) -> Dict[str, Any]:
        """
        Process the most recent crypto email and return summary.
        
        Returns:
            Processing summary
        """
        logger.info("Processing latest crypto QUANT email")
        
        results = await self.extract_and_enrich(hours=2)  # Last 2 hours
        
        if not results:
            return {
                'success': False,
                'message': 'No crypto emails found in the last 2 hours',
                'processed_count': 0,
                'extracted_count': 0
            }
        
        # Process the most recent email
        latest_result = results[0]
        items = latest_result.get('extracted_items', [])
        
        return {
            'success': True,
            'message': f'Successfully processed crypto email',
            'processed_count': 1,
            'extracted_count': len(items),
            'email_id': latest_result.get('email_data', {}).get('message_id'),
            'processing_time': latest_result.get('processing_metadata', {}).get('processing_time'),
            'confidence_score': latest_result.get('processing_metadata', {}).get('confidence_score'),
            'crypto_symbols': [item['ticker'] for item in items],
            'result': latest_result
        }