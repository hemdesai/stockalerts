"""
ETF Pro Plus - Levels email extractor.
"""
from typing import Dict, List, Any
import yfinance as yf

from app.core.logging import get_logger
from app.services.email.base import BaseEmailExtractor

logger = get_logger(__name__)


class ETFExtractor(BaseEmailExtractor):
    """
    Extractor for ETF Pro Plus - Levels emails.
    """
    
    def get_email_type(self) -> str:
        return "etf"
    
    def get_category(self) -> str:
        return "etfs"
    
    def __init__(self):
        super().__init__()
        # Common ETF ticker patterns for validation
        self.common_etfs = {
            # Broad Market
            'SPY', 'QQQ', 'IWM', 'VTI', 'VOO', 'VEA', 'VWO',
            # Sector ETFs
            'XLF', 'XLK', 'XLE', 'XLV', 'XLI', 'XLP', 'XLU', 'XLB', 'XLY', 'XLRE',
            # Technology
            'TQQQ', 'SQQQ', 'SMH', 'SOXX', 'IGV', 'WCLD', 'ARKK', 'ARKW',
            # Financial
            'XLF', 'KRE', 'KBE', 'IAT',
            # Energy
            'XLE', 'XOP', 'USO', 'UNG',
            # Healthcare
            'XLV', 'IBB', 'XBI', 'IHI',
            # Real Estate
            'XLRE', 'IYR', 'VNQ', 'REZ',
            # International
            'EFA', 'EEM', 'FXI', 'ASHR', 'INDA', 'EWJ', 'EWZ',
            # Bonds
            'TLT', 'IEF', 'SHY', 'LQD', 'HYG', 'JNK', 'TIP',
            # Commodities
            'GLD', 'SLV', 'GDX', 'USO', 'DBA', 'DBC',
            # Volatility
            'VIX', 'UVXY', 'SVXY', 'VXX'
        }
    
    def validate_etf_ticker(self, ticker: str) -> bool:
        """
        Validate if ticker looks like a legitimate ETF.
        
        Args:
            ticker: Ticker symbol to validate
            
        Returns:
            True if ticker appears to be valid ETF
        """
        if not ticker:
            return False
        
        ticker_upper = ticker.upper().strip()
        
        # Check against known ETFs
        if ticker_upper in self.common_etfs:
            return True
        
        # ETF ticker patterns
        if len(ticker_upper) >= 2 and len(ticker_upper) <= 5:
            # Many ETFs start with specific patterns
            etf_patterns = ['XL', 'I', 'V', 'SP', 'QQ', 'TL', 'US', 'AR', 'SH', 'UL']
            for pattern in etf_patterns:
                if ticker_upper.startswith(pattern):
                    return True
        
        return len(ticker_upper) >= 2 and len(ticker_upper) <= 5
    
    def validate_etf_data(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Additional validation specific to ETF signals.
        
        Args:
            items: List of extracted items
            
        Returns:
            List of validated items
        """
        validated = []
        
        for item in items:
            try:
                ticker = item.get('ticker', '').upper().strip()
                
                # Validate ETF ticker
                if not self.validate_etf_ticker(ticker):
                    logger.warning(f"Invalid ETF ticker: {ticker}")
                    continue
                
                item['ticker'] = ticker
                
                # ETFs usually have more conservative price ranges
                buy_price = item.get('buy_trade')
                sell_price = item.get('sell_trade')
                
                if not buy_price and not sell_price:
                    logger.warning(f"No trading levels for ETF {ticker}")
                    continue
                
                # Validate reasonable ETF prices (most ETFs $10-$500)
                for price_type, price in [('buy', buy_price), ('sell', sell_price)]:
                    if price and (price < 1 or price > 1000):
                        logger.warning(f"Unusual {price_type} price for ETF {ticker}: {price}")
                
                # ETF sentiment is often more neutral/technical
                if not item.get('sentiment'):
                    item['sentiment'] = 'neutral'
                
                validated.append(item)
                
            except Exception as e:
                logger.warning(f"Error validating ETF item {item}: {e}")
                continue
        
        return validated
    
    async def _enrich_with_etf_info(self, items: List[Dict[str, Any]]) -> None:
        """
        Enrich ETF items with fund information from yfinance.
        
        Args:
            items: List of extracted ETF items to enrich
        """
        for item in items:
            try:
                ticker = item.get('ticker')
                if not ticker:
                    continue
                
                logger.debug(f"Fetching ETF info for {ticker}")
                
                # Get ETF info from yfinance
                etf = yf.Ticker(ticker)
                info = etf.info
                
                # Extract ETF name
                fund_name = (
                    info.get('shortName') or 
                    info.get('longName') or 
                    info.get('fundFamily', '') + ' ' + info.get('fundName', '')
                ).strip()
                
                if fund_name:
                    item['name'] = fund_name
                    logger.debug(f"Found name for {ticker}: {fund_name}")
                
                # Add ETF-specific metadata
                etf_metadata = {}
                
                # Fund information
                if info.get('fundFamily'):
                    etf_metadata['fund_family'] = info['fundFamily']
                if info.get('category'):
                    etf_metadata['category'] = info['category']
                if info.get('totalAssets'):
                    etf_metadata['total_assets'] = info['totalAssets']
                if info.get('yield'):
                    etf_metadata['yield'] = info['yield']
                if info.get('expenseRatio'):
                    etf_metadata['expense_ratio'] = info['expenseRatio']
                
                # Technical data
                if info.get('fiftyTwoWeekHigh'):
                    etf_metadata['52_week_high'] = info['fiftyTwoWeekHigh']
                if info.get('fiftyTwoWeekLow'):
                    etf_metadata['52_week_low'] = info['fiftyTwoWeekLow']
                
                if etf_metadata:
                    if 'extraction_metadata' not in item:
                        item['extraction_metadata'] = {}
                    item['extraction_metadata']['etf_info'] = etf_metadata
                    
            except Exception as e:
                logger.warning(f"Error fetching ETF info for {item.get('ticker')}: {e}")
                continue
    
    async def extract_and_enrich(self, hours: int = 168) -> List[Dict[str, Any]]:  # 7 days default
        """
        Extract ETF signals and enrich with fund information.
        
        Args:
            hours: Hours back to search for emails (default 7 days for weekly ETFs)
            
        Returns:
            List of enriched extraction results
        """
        results = await self.extract_from_recent_emails(hours)
        
        for result in results:
            if result.get('extracted_items'):
                # Validate ETF-specific data
                validated_items = self.validate_etf_data(result['extracted_items'])
                
                # Enrich with ETF information
                await self._enrich_with_etf_info(validated_items)
                
                result['extracted_items'] = validated_items
                result['processing_metadata']['etfs_validated'] = len(validated_items)
        
        return results
    
    async def process_latest_etf_email(self) -> Dict[str, Any]:
        """
        Process the most recent ETF email and return summary.
        
        Returns:
            Processing summary
        """
        logger.info("Processing latest ETF Pro Plus email")
        
        # ETF emails come weekly, so search last 7 days
        results = await self.extract_and_enrich(hours=168)
        
        if not results:
            return {
                'success': False,
                'message': 'No ETF emails found in the last 7 days',
                'processed_count': 0,
                'extracted_count': 0
            }
        
        # Process the most recent email
        latest_result = results[0]
        items = latest_result.get('extracted_items', [])
        
        # Analyze ETF categories
        categories = {}
        fund_families = {}
        
        for item in items:
            etf_info = item.get('extraction_metadata', {}).get('etf_info', {})
            
            category = etf_info.get('category')
            if category:
                categories[category] = categories.get(category, 0) + 1
            
            fund_family = etf_info.get('fund_family')
            if fund_family:
                fund_families[fund_family] = fund_families.get(fund_family, 0) + 1
        
        return {
            'success': True,
            'message': f'Successfully processed ETF email',
            'processed_count': 1,
            'extracted_count': len(items),
            'email_id': latest_result.get('email_data', {}).get('message_id'),
            'processing_time': latest_result.get('processing_metadata', {}).get('processing_time'),
            'confidence_score': latest_result.get('processing_metadata', {}).get('confidence_score'),
            'etf_categories': categories,
            'fund_families': fund_families,
            'tickers': [item['ticker'] for item in items],
            'result': latest_result
        }
    
    def analyze_etf_themes(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze ETF investment themes and sectors.
        
        Args:
            items: List of extracted ETF items
            
        Returns:
            Theme analysis summary
        """
        themes = {
            'sector_etfs': 0,
            'broad_market': 0,
            'international': 0,
            'fixed_income': 0,
            'commodity': 0,
            'thematic': 0,
            'categories': {},
            'avg_expense_ratio': 0,
            'total_aum': 0
        }
        
        expense_ratios = []
        total_assets = []
        
        for item in items:
            ticker = item.get('ticker', '')
            etf_info = item.get('extraction_metadata', {}).get('etf_info', {})
            
            # Categorize ETF type
            if ticker.startswith('XL'):
                themes['sector_etfs'] += 1
            elif ticker in ['SPY', 'QQQ', 'IWM', 'VTI', 'VOO']:
                themes['broad_market'] += 1
            elif ticker in ['EFA', 'EEM', 'VEA', 'VWO', 'FXI']:
                themes['international'] += 1
            elif ticker in ['TLT', 'IEF', 'LQD', 'HYG']:
                themes['fixed_income'] += 1
            elif ticker in ['GLD', 'SLV', 'USO', 'DBC']:
                themes['commodity'] += 1
            else:
                themes['thematic'] += 1
            
            # Track categories
            category = etf_info.get('category')
            if category:
                themes['categories'][category] = themes['categories'].get(category, 0) + 1
            
            # Collect financial metrics
            if etf_info.get('expense_ratio'):
                expense_ratios.append(etf_info['expense_ratio'])
            if etf_info.get('total_assets'):
                total_assets.append(etf_info['total_assets'])
        
        # Calculate averages
        if expense_ratios:
            themes['avg_expense_ratio'] = sum(expense_ratios) / len(expense_ratios)
        if total_assets:
            themes['total_aum'] = sum(total_assets)
        
        return themes