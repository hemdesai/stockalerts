"""
Mistral AI service for email content extraction and processing.
"""
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class MistralProcessor:
    """
    Mistral AI processor for extracting structured data from emails.
    """
    
    def __init__(self):
        self.client = MistralClient(api_key=settings.MISTRAL_API_KEY)
        self.model = settings.MISTRAL_MODEL
        
        # Extraction prompts for different email types
        self.extraction_prompts = {
            "daily": self._get_daily_extraction_prompt(),
            "crypto": self._get_crypto_extraction_prompt(),
            "ideas": self._get_ideas_extraction_prompt(), 
            "etf": self._get_etf_extraction_prompt()
        }
    
    def _get_daily_extraction_prompt(self) -> str:
        """Get prompt for daily RISK RANGE signals extraction."""
        return """
You are an expert financial data extractor. Extract trading signals from the RISK RANGE email.

Expected format in the email:
- Stock ticker symbols with trading ranges
- Buy/sell signals with specific price levels
- Sometimes sentiment indicators (bullish/bearish)

Extract ALL tickers mentioned with their buy_trade and sell_trade prices.

Return ONLY valid JSON in this exact format:
{
    "extracted_items": [
        {
            "ticker": "AAPL",
            "sentiment": "bullish",
            "buy_trade": 150.50,
            "sell_trade": 160.75,
            "category": "daily"
        }
    ],
    "confidence_score": 0.95,
    "extraction_method": "mistral_ai"
}

Rules:
- Extract ALL tickers found
- Use null for missing sentiment
- Prices must be numbers (floats)
- Category is always "daily"
- Return empty array if no valid data found
- Do not include any text outside the JSON
"""
    
    def _get_crypto_extraction_prompt(self) -> str:
        """Get prompt for crypto signals extraction."""
        return """
You are an expert cryptocurrency data extractor. Extract trading signals from the CRYPTO QUANT email.

Expected format:
- Cryptocurrency symbols/names with trading levels
- Buy/sell signals with price targets
- Market sentiment analysis

Extract ALL crypto assets mentioned with trading levels.

Return ONLY valid JSON in this exact format:
{
    "extracted_items": [
        {
            "ticker": "BTC",
            "sentiment": "bullish",
            "buy_trade": 45000.00,
            "sell_trade": 50000.00,
            "category": "digitalassets"
        }
    ],
    "confidence_score": 0.90,
    "extraction_method": "mistral_ai"
}

Rules:
- Use standard crypto symbols (BTC, ETH, SOL, etc.)
- Extract ALL crypto assets found
- Use null for missing sentiment
- Prices must be numbers (floats)
- Category is always "digitalassets"
- Return empty array if no valid data found
"""
    
    def _get_ideas_extraction_prompt(self) -> str:
        """Get prompt for investment ideas extraction."""
        return """
You are an expert investment research extractor. Extract stock recommendations from the Investing Ideas Newsletter.

Expected format:
- Stock recommendations with price targets
- Investment thesis and sentiment
- Buy/sell levels or target prices

Extract ALL stock recommendations mentioned.

Return ONLY valid JSON in this exact format:
{
    "extracted_items": [
        {
            "ticker": "TSLA",
            "sentiment": "bullish",
            "buy_trade": 200.00,
            "sell_trade": 250.00,
            "category": "ideas"
        }
    ],
    "confidence_score": 0.85,
    "extraction_method": "mistral_ai"
}

Rules:
- Extract ALL stock recommendations
- Infer buy/sell levels from price targets
- Use sentiment from investment thesis
- Category is always "ideas"
- Return empty array if no valid data found
"""
    
    def _get_etf_extraction_prompt(self) -> str:
        """Get prompt for ETF levels extraction."""
        return """
You are an expert ETF trading data extractor. Extract ETF trading levels from the ETF Pro Plus email.

Expected format:
- ETF ticker symbols with support/resistance levels
- Trading ranges and breakout levels
- Sector or thematic ETF analysis

Extract ALL ETF tickers mentioned with trading levels.

Return ONLY valid JSON in this exact format:
{
    "extracted_items": [
        {
            "ticker": "SPY",
            "sentiment": "neutral",
            "buy_trade": 420.00,
            "sell_trade": 430.00,
            "category": "etfs"
        }
    ],
    "confidence_score": 0.88,
    "extraction_method": "mistral_ai"
}

Rules:
- Extract ALL ETF tickers found
- Use trading levels as buy/sell points
- Infer sentiment from analysis
- Category is always "etfs"
- Return empty array if no valid data found
"""
    
    async def extract_data(self, email_content: str, email_type: str) -> Dict[str, Any]:
        """
        Extract structured data from email content using Mistral AI.
        
        Args:
            email_content: Raw email content (text or HTML)
            email_type: Type of email (daily, crypto, ideas, etf)
            
        Returns:
            Dictionary with extracted data and metadata
        """
        if email_type not in self.extraction_prompts:
            logger.error(f"Unknown email type: {email_type}")
            return self._empty_result()
        
        try:
            prompt = self.extraction_prompts[email_type]
            
            logger.info(f"Starting Mistral extraction for {email_type} email")
            start_time = datetime.now()
            
            # Create chat completion
            messages = [
                ChatMessage(role="system", content=prompt),
                ChatMessage(role="user", content=f"Extract data from this email:\n\n{email_content}")
            ]
            
            response = self.client.chat(
                model=self.model,
                messages=messages,
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=2000
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Parse response
            response_content = response.choices[0].message.content.strip()
            logger.debug(f"Mistral response: {response_content}")
            
            # Extract JSON from response
            extracted_data = self._parse_json_response(response_content)
            
            if extracted_data:
                extracted_data.update({
                    "processing_time": processing_time,
                    "ai_model_used": self.model,
                    "email_type": email_type
                })
                
                logger.info(f"Successfully extracted {len(extracted_data.get('extracted_items', []))} items "
                          f"from {email_type} email in {processing_time:.2f}s")
                
                return extracted_data
            else:
                logger.warning(f"Failed to parse Mistral response for {email_type}")
                return self._empty_result()
                
        except Exception as e:
            logger.error(f"Mistral extraction error for {email_type}: {e}")
            return self._empty_result(error=str(e))
    
    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Parse JSON response from Mistral AI.
        
        Args:
            response: Raw response string
            
        Returns:
            Parsed JSON dictionary or None
        """
        try:
            # Try to parse as direct JSON
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # Try to find JSON-like content
            json_match = re.search(r'{.*}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
            
            logger.error(f"Could not parse JSON from response: {response[:200]}...")
            return None
    
    def _empty_result(self, error: Optional[str] = None) -> Dict[str, Any]:
        """
        Return empty extraction result.
        
        Args:
            error: Optional error message
            
        Returns:
            Empty result dictionary
        """
        result = {
            "extracted_items": [],
            "confidence_score": 0.0,
            "extraction_method": "mistral_ai",
            "processing_time": 0.0,
            "ai_model_used": self.model
        }
        
        if error:
            result["error"] = error
        
        return result
    
    async def validate_extraction(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean extracted data.
        
        Args:
            extracted_data: Raw extraction result
            
        Returns:
            Validated and cleaned data
        """
        if not extracted_data.get("extracted_items"):
            return extracted_data
        
        validated_items = []
        
        for item in extracted_data["extracted_items"]:
            try:
                # Validate required fields
                if not item.get("ticker"):
                    logger.warning(f"Skipping item without ticker: {item}")
                    continue
                
                # Clean and validate ticker
                ticker = str(item["ticker"]).upper().strip()
                if len(ticker) < 1 or len(ticker) > 10:
                    logger.warning(f"Invalid ticker length: {ticker}")
                    continue
                
                # Validate prices
                buy_trade = self._validate_price(item.get("buy_trade"))
                sell_trade = self._validate_price(item.get("sell_trade"))
                
                if buy_trade is None and sell_trade is None:
                    logger.warning(f"No valid prices for {ticker}")
                    continue
                
                # Clean sentiment
                sentiment = item.get("sentiment")
                if sentiment:
                    sentiment = str(sentiment).lower().strip()
                    if sentiment not in ["bullish", "bearish", "neutral"]:
                        sentiment = None
                
                validated_items.append({
                    "ticker": ticker,
                    "sentiment": sentiment,
                    "buy_trade": buy_trade,
                    "sell_trade": sell_trade,
                    "category": item.get("category", "daily")
                })
                
            except Exception as e:
                logger.warning(f"Error validating item {item}: {e}")
                continue
        
        extracted_data["extracted_items"] = validated_items
        extracted_data["validated_count"] = len(validated_items)
        
        logger.info(f"Validated {len(validated_items)} items from extraction")
        
        return extracted_data
    
    def _validate_price(self, price: Any) -> Optional[float]:
        """
        Validate and convert price to float.
        
        Args:
            price: Price value to validate
            
        Returns:
            Valid float price or None
        """
        if price is None:
            return None
        
        try:
            price_float = float(price)
            if price_float <= 0 or price_float > 1000000:  # Reasonable bounds
                return None
            return price_float
        except (ValueError, TypeError):
            return None