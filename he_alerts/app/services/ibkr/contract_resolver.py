"""
IBKR contract resolution service.
Handles classification and resolution of different asset types.
"""
import json
from typing import Dict, Optional, Any
from ib_async import Stock, Index, Forex, Crypto, Future, Bond, Contract
import structlog

logger = structlog.get_logger(__name__)

# Crypto symbol mappings
CRYPTO_SYMBOL_MAP = {
    "BITCOIN": "BTC",
    "ETHEREUM": "ETH", 
    "SOLANA": "SOL",
    "AVALANCHE": "AVAX",
    "AAVE": "AAVE",
    # Add more mappings as needed
}

# Crypto stock symbols that should be treated as regular stocks
CRYPTO_STOCKS = {"IBIT", "MSTR", "MARA", "RIOT", "ETHA", "BLOK", "COIN", "BITO"}


class ContractResolver:
    """Resolves IBKR contracts for different asset types."""
    
    @staticmethod
    def classify_asset(symbol: str, name_hint: str = "", category: str = "") -> str:
        """
        Classify asset type based on symbol and hints.
        
        Args:
            symbol: The ticker symbol
            name_hint: Optional name hint for classification
            category: Category from database (daily, etfs, ideas, digitalassets)
            
        Returns:
            Asset type: 'stock', 'future', 'index', 'crypto', 'forex', 'etf'
        """
        symbol = symbol.upper()
        
        # Check category first
        if category == "digitalassets":
            # Pure crypto vs crypto stocks
            if symbol in CRYPTO_STOCKS:
                return "stock"
            elif symbol in CRYPTO_SYMBOL_MAP.values() or symbol in CRYPTO_SYMBOL_MAP:
                return "crypto"
        elif category == "etfs":
            return "etf"
        
        # Futures detection
        if symbol.endswith('=F') or symbol in {'CL=F', 'BZ=F', 'NG=F', 'GC=F', 'HG=F', 'SI=F'}:
            return 'future'
        
        # Index detection
        if symbol.startswith('^') or 'INDEX' in name_hint.upper():
            return 'index'
        
        # Forex detection
        if len(symbol) == 6 and symbol.endswith('USD'):
            return 'forex'
        
        # Crypto detection
        if symbol.endswith('USD') or 'CRYPTO' in name_hint.upper() or symbol in CRYPTO_SYMBOL_MAP:
            return 'crypto'
        
        # Default to stock
        return 'stock'
    
    @staticmethod
    def get_crypto_symbol(symbol: str) -> str:
        """Map user-friendly crypto names to IBKR symbols."""
        return CRYPTO_SYMBOL_MAP.get(symbol.upper(), symbol)
    
    @staticmethod
    def create_contract(symbol: str, asset_type: str) -> Optional[Contract]:
        """
        Create an IBKR contract based on symbol and asset type.
        
        Args:
            symbol: The ticker symbol
            asset_type: Type of asset (stock, etf, crypto, etc.)
            
        Returns:
            IBKR Contract object or None
        """
        try:
            if asset_type in ('stock', 'etf'):
                return Stock(symbol, 'SMART', 'USD')
            
            elif asset_type == 'future':
                # Remove =F suffix if present
                clean_symbol = symbol.replace('=F', '')
                return Future(clean_symbol, 'CME', 'USD')
            
            elif asset_type == 'index':
                # Remove ^ prefix if present
                clean_symbol = symbol.lstrip('^')
                return Index(clean_symbol, 'CBOE', 'USD')
            
            elif asset_type == 'forex':
                return Forex(symbol, 'IDEALPRO')
            
            elif asset_type == 'crypto':
                # Map user-friendly names to IBKR symbols
                base = ContractResolver.get_crypto_symbol(symbol.replace('USD', ''))
                return Crypto(base, 'PAXOS', 'USD')
            
            else:
                # Default to stock
                return Stock(symbol, 'SMART', 'USD')
                
        except Exception as e:
            logger.error(f"Error creating contract for {symbol} ({asset_type}): {e}")
            return None
    
    @staticmethod
    def contract_to_json(contract: Contract) -> Dict[str, Any]:
        """
        Convert IBKR contract to JSON-serializable dict.
        
        Args:
            contract: IBKR Contract object
            
        Returns:
            Dictionary with contract details
        """
        return {
            'conId': getattr(contract, 'conId', None),
            'symbol': getattr(contract, 'symbol', ''),
            'secType': getattr(contract, 'secType', 'STK'),
            'exchange': getattr(contract, 'exchange', 'SMART'),
            'currency': getattr(contract, 'currency', 'USD'),
            'primaryExchange': getattr(contract, 'primaryExchange', ''),
            'lastTradeDateOrContractMonth': getattr(contract, 'lastTradeDateOrContractMonth', '')
        }
    
    @staticmethod
    def json_to_contract(contract_json: Dict[str, Any]) -> Optional[Contract]:
        """
        Reconstruct IBKR contract from JSON data.
        
        Args:
            contract_json: Dictionary with contract details
            
        Returns:
            IBKR Contract object or None
        """
        if not contract_json:
            return None
        
        try:
            sec_type = contract_json.get('secType', 'STK')
            symbol = contract_json.get('symbol', '')
            exchange = contract_json.get('exchange', 'SMART')
            currency = contract_json.get('currency', 'USD')
            
            if sec_type == 'STK':
                return Stock(symbol, exchange, currency)
            elif sec_type == 'FUT':
                contract = Future(symbol, exchange, currency)
                if 'lastTradeDateOrContractMonth' in contract_json:
                    contract.lastTradeDateOrContractMonth = contract_json['lastTradeDateOrContractMonth']
                return contract
            elif sec_type == 'IND':
                return Index(symbol, exchange, currency)
            elif sec_type == 'CASH':
                return Forex(symbol, exchange)
            elif sec_type == 'CRYPTO':
                return Crypto(symbol, exchange, currency)
            else:
                return Stock(symbol, exchange, currency)
                
        except Exception as e:
            logger.error(f"Error reconstructing contract from JSON: {e}")
            return None