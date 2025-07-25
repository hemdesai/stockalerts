"""
Email extraction validator - Review and approve stocks before database update.
"""
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
# from tabulate import tabulate  # Optional for prettier tables

from app.core.database import AsyncSessionLocal
from app.services.database.stock_service import StockService
from app.services.email.gmail_client import GmailClient
from app.services.email_processor import EmailProcessor
from app.core.logging import get_logger

logger = get_logger(__name__)


class ExtractionValidator:
    """Validates extracted stock data before database updates."""
    
    def __init__(self):
        self.gmail_client = GmailClient()
        self.email_processor = EmailProcessor()
        self.validation_history = []
    
    async def fetch_and_validate_emails(
        self, 
        hours: int = 48,
        save_validation_file: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch recent emails, extract stocks, and present for validation.
        
        Args:
            hours: How many hours back to fetch emails
            save_validation_file: Save validation results to file
            
        Returns:
            Validation results
        """
        # Authenticate with Gmail
        if not await self.gmail_client.authenticate():
            logger.error("Failed to authenticate with Gmail")
            return {"success": False, "message": "Gmail authentication failed"}
        
        logger.info("[OK] Authenticated with Gmail")
        
        # Fetch recent emails
        recent_emails = await self.gmail_client.fetch_recent_emails(hours=hours)
        logger.info(f"Found {len(recent_emails)} emails in the last {hours} hours")
        
        # Group by email type
        email_groups = {}
        for email in recent_emails:
            email_type = email.get('email_type', 'unknown')
            if email_type not in email_groups:
                email_groups[email_type] = []
            email_groups[email_type].append(email)
        
        # Process each email type
        all_extracted_stocks = []
        extraction_results = {}
        
        for email_type, emails in email_groups.items():
            if email_type == 'unknown':
                continue
                
            # Get latest email for this type
            latest_email = emails[0]  # Already sorted by date
            logger.info(f"\nProcessing {email_type} email: {latest_email['subject']}")
            
            # Extract stocks
            extracted_stocks = await self._extract_stocks_from_email(latest_email)
            
            if extracted_stocks:
                extraction_results[email_type] = {
                    'email_id': latest_email['message_id'],
                    'subject': latest_email['subject'],
                    'date': latest_email['date'],
                    'stocks': extracted_stocks,
                    'count': len(extracted_stocks)
                }
                all_extracted_stocks.extend(extracted_stocks)
        
        # Display extraction summary
        self._display_extraction_summary(extraction_results)
        
        # Get current database state for comparison
        db_comparison = await self._compare_with_database(all_extracted_stocks)
        
        # Display validation report
        validation_report = self._create_validation_report(
            extraction_results, 
            db_comparison
        )
        
        # Save validation file
        if save_validation_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'validation_report_{timestamp}.json'
            
            with open(filename, 'w') as f:
                json.dump(validation_report, f, indent=2, default=str)
            
            logger.info(f"\nValidation report saved to: {filename}")
        
        # Create CSV for review
        csv_filename = self._export_validation_csv(all_extracted_stocks)
        logger.info(f"Review CSV exported to: {csv_filename}")
        
        return {
            "success": True,
            "extraction_results": extraction_results,
            "total_stocks": len(all_extracted_stocks),
            "validation_file": filename if save_validation_file else None,
            "csv_file": csv_filename
        }
    
    async def _extract_stocks_from_email(self, email: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract stocks from a single email."""
        try:
            # Get full email content
            email_data = await self.gmail_client.get_email_by_id(email['message_id'])
            
            # Map email types to extractor types
            type_mapping = {
                'daily': 'daily',
                'crypto': 'crypto',
                'digitalassets': 'crypto',
                'ideas': 'ideas',
                'etfs': 'etf',
                'etf': 'etf'
            }
            
            extractor_type = type_mapping.get(email['email_type'])
            if not extractor_type:
                logger.warning(f"Unknown email type: {email['email_type']}")
                return []
            
            # Get the extractor
            from app.services.email import get_extractor
            extractor = get_extractor(extractor_type)
            
            if not extractor:
                logger.error(f"No extractor found for type: {extractor_type}")
                return []
            
            # Extract stocks
            result = await extractor.extract_from_email(email_data)
            
            if result and result.get('extracted_items'):
                # Convert extracted_items to stocks format
                stocks = []
                for item in result['extracted_items']:
                    stock = {
                        'ticker': item.get('ticker'),
                        'name': item.get('name', ''),
                        'category': extractor.category,
                        'sentiment': item.get('sentiment', 'neutral'),
                        'buy_trade': item.get('buy_trade'),
                        'sell_trade': item.get('sell_trade'),
                        'source_email_id': email['message_id']
                    }
                    stocks.append(stock)
                return stocks
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error extracting from email: {e}")
            return []
    
    async def _compare_with_database(self, extracted_stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare extracted stocks with current database values."""
        async with AsyncSessionLocal() as db:
            stock_service = StockService()
            
            comparison = {
                'new_stocks': [],
                'updated_stocks': [],
                'unchanged_stocks': [],
                'suspicious_changes': []
            }
            
            for stock_data in extracted_stocks:
                # Check if stock exists
                existing = await stock_service.get_stock_by_ticker_and_category(
                    db, 
                    stock_data['ticker'],
                    stock_data['category']
                )
                
                if not existing:
                    comparison['new_stocks'].append(stock_data)
                else:
                    # Compare values
                    changes = self._detect_changes(existing, stock_data)
                    
                    if changes:
                        stock_data['changes'] = changes
                        stock_data['old_values'] = {
                            'buy_trade': existing.buy_trade,
                            'sell_trade': existing.sell_trade,
                            'sentiment': existing.sentiment
                        }
                        
                        # Check for suspicious changes
                        if self._is_suspicious_change(changes):
                            comparison['suspicious_changes'].append(stock_data)
                        else:
                            comparison['updated_stocks'].append(stock_data)
                    else:
                        comparison['unchanged_stocks'].append(stock_data)
            
            return comparison
    
    def _detect_changes(self, existing, new_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect what changed between existing and new data."""
        changes = {}
        
        # Check buy price
        if existing.buy_trade != new_data.get('buy_trade'):
            changes['buy_trade'] = {
                'old': existing.buy_trade,
                'new': new_data.get('buy_trade'),
                'diff': new_data.get('buy_trade', 0) - existing.buy_trade if existing.buy_trade else None,
                'diff_pct': ((new_data.get('buy_trade', 0) - existing.buy_trade) / existing.buy_trade * 100) if existing.buy_trade else None
            }
        
        # Check sell price
        if existing.sell_trade != new_data.get('sell_trade'):
            changes['sell_trade'] = {
                'old': existing.sell_trade,
                'new': new_data.get('sell_trade'),
                'diff': new_data.get('sell_trade', 0) - existing.sell_trade if existing.sell_trade else None,
                'diff_pct': ((new_data.get('sell_trade', 0) - existing.sell_trade) / existing.sell_trade * 100) if existing.sell_trade else None
            }
        
        # Check sentiment
        if existing.sentiment != new_data.get('sentiment'):
            changes['sentiment'] = {
                'old': existing.sentiment,
                'new': new_data.get('sentiment')
            }
        
        return changes
    
    def _is_suspicious_change(self, changes: Dict[str, Any]) -> bool:
        """Check if changes are suspicious (large percentage changes)."""
        threshold = 20  # 20% change threshold
        
        for field in ['buy_trade', 'sell_trade']:
            if field in changes:
                diff_pct = changes[field].get('diff_pct')
                if diff_pct and abs(diff_pct) > threshold:
                    return True
        
        # Sentiment flip is always suspicious
        if 'sentiment' in changes:
            old_sent = changes['sentiment']['old']
            new_sent = changes['sentiment']['new']
            if (old_sent == 'bullish' and new_sent == 'bearish') or \
               (old_sent == 'bearish' and new_sent == 'bullish'):
                return True
        
        return False
    
    def _display_extraction_summary(self, extraction_results: Dict[str, Any]):
        """Display a summary of extracted data."""
        print("\n" + "="*80)
        print("EXTRACTION SUMMARY")
        print("="*80)
        
        for email_type, data in extraction_results.items():
            print(f"\n{email_type.upper()} EMAIL:")
            print(f"  Subject: {data['subject']}")
            print(f"  Date: {data['date']}")
            print(f"  Stocks extracted: {data['count']}")
            
            if data['count'] > 0:
                # Show first few stocks
                print("  Sample stocks:")
                for stock in data['stocks'][:5]:
                    print(f"    - {stock['ticker']}: Buy=${stock.get('buy_trade', 'N/A')}, "
                          f"Sell=${stock.get('sell_trade', 'N/A')}, {stock.get('sentiment', 'N/A')}")
                if data['count'] > 5:
                    print(f"    ... and {data['count'] - 5} more")
    
    def _create_validation_report(
        self, 
        extraction_results: Dict[str, Any],
        db_comparison: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a detailed validation report."""
        print("\n" + "="*80)
        print("VALIDATION REPORT")
        print("="*80)
        
        # Summary statistics
        total_extracted = sum(data['count'] for data in extraction_results.values())
        
        print(f"\nTotal stocks extracted: {total_extracted}")
        print(f"New stocks: {len(db_comparison['new_stocks'])}")
        print(f"Updated stocks: {len(db_comparison['updated_stocks'])}")
        print(f"Unchanged stocks: {len(db_comparison['unchanged_stocks'])}")
        print(f"Suspicious changes: {len(db_comparison['suspicious_changes'])}")
        
        # Show suspicious changes
        if db_comparison['suspicious_changes']:
            print("\n⚠️  SUSPICIOUS CHANGES DETECTED:")
            print("-" * 80)
            
            for stock in db_comparison['suspicious_changes']:
                print(f"\n{stock['ticker']} ({stock['category']}):")
                for field, change in stock['changes'].items():
                    if field == 'sentiment':
                        print(f"  Sentiment: {change['old']} → {change['new']}")
                    else:
                        print(f"  {field}: ${change['old']:.2f} → ${change['new']:.2f} "
                              f"({change['diff_pct']:+.1f}%)")
        
        # Show new stocks
        if db_comparison['new_stocks']:
            print("\n✨ NEW STOCKS:")
            print("-" * 80)
            
            new_stocks_table = []
            for stock in db_comparison['new_stocks'][:10]:
                new_stocks_table.append([
                    stock['ticker'],
                    stock['category'],
                    stock.get('sentiment', 'N/A'),
                    f"${stock.get('buy_trade', 0):.2f}",
                    f"${stock.get('sell_trade', 0):.2f}"
                ])
            
            # Print table header
            print(f"{'Ticker':8} {'Category':15} {'Sentiment':10} {'Buy':>10} {'Sell':>10}")
            print("-" * 60)
            
            # Print rows
            for row in new_stocks_table:
                print(f"{row[0]:8} {row[1]:15} {row[2]:10} {row[3]:>10} {row[4]:>10}")
            
            if len(db_comparison['new_stocks']) > 10:
                print(f"\n... and {len(db_comparison['new_stocks']) - 10} more new stocks")
        
        # Create report dictionary
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_extracted': total_extracted,
                'new_stocks': len(db_comparison['new_stocks']),
                'updated_stocks': len(db_comparison['updated_stocks']),
                'unchanged_stocks': len(db_comparison['unchanged_stocks']),
                'suspicious_changes': len(db_comparison['suspicious_changes'])
            },
            'extraction_results': extraction_results,
            'database_comparison': db_comparison
        }
        
        return report
    
    def _export_validation_csv(self, stocks: List[Dict[str, Any]]) -> str:
        """Export stocks to CSV for review."""
        if not stocks:
            logger.warning("No stocks to export to CSV")
            return "no_stocks_to_export.csv"
            
        # Convert to DataFrame
        df = pd.DataFrame(stocks)
        
        # Check which columns exist
        columns = ['ticker', 'name', 'category', 'sentiment', 'buy_trade', 'sell_trade']
        available_columns = [col for col in columns if col in df.columns]
        
        if available_columns:
            df = df[available_columns]
        else:
            logger.warning("No expected columns found in extracted data")
        
        # Sort by category and ticker
        df = df.sort_values(['category', 'ticker'])
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'stocks_for_validation_{timestamp}.csv'
        
        # Export
        df.to_csv(filename, index=False)
        
        return filename
    
    async def apply_validated_updates(
        self, 
        validation_file: str,
        approved_categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Apply validated updates to the database.
        
        Args:
            validation_file: Path to validation JSON file
            approved_categories: List of categories to update (None = all)
            
        Returns:
            Update results
        """
        # Load validation data
        with open(validation_file, 'r') as f:
            validation_data = json.load(f)
        
        extraction_results = validation_data['extraction_results']
        
        # Filter by approved categories
        if approved_categories:
            extraction_results = {
                k: v for k, v in extraction_results.items() 
                if k in approved_categories
            }
        
        # Apply updates
        async with AsyncSessionLocal() as db:
            stock_service = StockService()
            update_summary = {
                'created': 0,
                'updated': 0,
                'errors': 0
            }
            
            for email_type, data in extraction_results.items():
                logger.info(f"\nUpdating {email_type} stocks...")
                
                for stock_data in data['stocks']:
                    try:
                        # Check if exists
                        existing = await stock_service.get_stock_by_ticker_and_category(
                            db,
                            stock_data['ticker'],
                            stock_data['category']
                        )
                        
                        if existing:
                            # Update existing
                            await stock_service.update_stock(
                                db,
                                existing.id,
                                stock_data
                            )
                            update_summary['updated'] += 1
                        else:
                            # Create new
                            await stock_service.create_stock(db, stock_data)
                            update_summary['created'] += 1
                            
                    except Exception as e:
                        logger.error(f"Error updating {stock_data['ticker']}: {e}")
                        update_summary['errors'] += 1
            
            await db.commit()
            
        logger.info(f"\nUpdate complete: Created {update_summary['created']}, "
                   f"Updated {update_summary['updated']}, Errors {update_summary['errors']}")
        
        return update_summary


async def main():
    """Main validation workflow."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Email Extraction Validator')
    parser.add_argument(
        '--hours',
        type=int,
        default=48,
        help='How many hours back to fetch emails (default: 48)'
    )
    parser.add_argument(
        '--apply',
        help='Apply updates from validation file'
    )
    parser.add_argument(
        '--categories',
        nargs='+',
        choices=['daily', 'crypto', 'digitalassets', 'etfs', 'ideas'],
        help='Categories to update (default: all)'
    )
    
    args = parser.parse_args()
    
    validator = ExtractionValidator()
    
    if args.apply:
        # Apply validated updates
        result = await validator.apply_validated_updates(
            args.apply,
            args.categories
        )
        print(f"\nDatabase updated: {result}")
    else:
        # Fetch and validate
        result = await validator.fetch_and_validate_emails(hours=args.hours)
        
        if result['success']:
            print(f"\n{'='*80}")
            print("NEXT STEPS:")
            print("="*80)
            print(f"1. Review the CSV file: {result['csv_file']}")
            print(f"2. Check the validation report: {result['validation_file']}")
            print("\n3. To apply updates after review:")
            print(f"   python email_extraction_validator.py --apply {result['validation_file']}")
            print("\n   Or update only specific categories:")
            print(f"   python email_extraction_validator.py --apply {result['validation_file']} --categories daily crypto")


if __name__ == "__main__":
    asyncio.run(main())