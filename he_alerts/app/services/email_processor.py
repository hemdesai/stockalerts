"""
Main email processing orchestrator that coordinates extraction and database operations.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services.email import get_extractor
from app.services.database import StockService

logger = get_logger(__name__)


class EmailProcessor:
    """
    Main orchestrator for email processing workflow.
    """
    
    def __init__(self):
        self.extractors = {
            "daily": get_extractor("daily"),
            "crypto": get_extractor("crypto"),
            "ideas": get_extractor("ideas"),
            "etf": get_extractor("etf")
        }
    
    async def process_recent_emails(
        self, 
        db: AsyncSession,
        email_types: Optional[List[str]] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Process recent emails of specified types.
        
        Args:
            db: Database session
            email_types: List of email types to process (None = all)
            hours: Hours back to search
            
        Returns:
            Processing summary
        """
        if email_types is None:
            email_types = ["daily", "crypto", "ideas", "etf"]
        
        logger.info(f"Starting email processing for types: {email_types}")
        
        results = {
            'total_processed': 0,
            'total_extracted': 0,
            'total_errors': 0,
            'by_type': {},
            'processing_time': 0.0
        }
        
        start_time = datetime.now()
        
        for email_type in email_types:
            try:
                logger.info(f"Processing {email_type} emails")
                
                type_result = await self._process_email_type(db, email_type, hours)
                results['by_type'][email_type] = type_result
                
                results['total_processed'] += type_result['processed_count']
                results['total_extracted'] += type_result['extracted_count'] 
                results['total_errors'] += type_result['error_count']
                
            except Exception as e:
                logger.error(f"Error processing {email_type} emails: {e}")
                results['by_type'][email_type] = {
                    'processed_count': 0,
                    'extracted_count': 0,
                    'error_count': 1,
                    'error': str(e)
                }
                results['total_errors'] += 1
        
        results['processing_time'] = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Email processing complete: {results['total_processed']} processed, "
                   f"{results['total_extracted']} extracted, {results['total_errors']} errors")
        
        return results
    
    async def _process_email_type(
        self, 
        db: AsyncSession, 
        email_type: str, 
        hours: int
    ) -> Dict[str, Any]:
        """
        Process emails for a specific type.
        
        Args:
            db: Database session
            email_type: Type of email to process
            hours: Hours back to search
            
        Returns:
            Processing result for this type
        """
        extractor = self.extractors.get(email_type)
        if not extractor:
            logger.error(f"No extractor found for email type: {email_type}")
            return {'processed_count': 0, 'extracted_count': 0, 'error_count': 1}
        
        try:
            # Extract from recent emails
            extraction_results = await extractor.extract_from_recent_emails(hours)
            
            processed_count = 0
            extracted_count = 0
            error_count = 0
            
            for result in extraction_results:
                try:
                    # Process single extraction result
                    single_result = await self._process_extraction_result(db, result, extractor)
                    
                    processed_count += 1
                    extracted_count += single_result['extracted_count']
                    
                except Exception as e:
                    logger.error(f"Error processing extraction result: {e}")
                    error_count += 1
            
            return {
                'processed_count': processed_count,
                'extracted_count': extracted_count,
                'error_count': error_count,
                'extraction_results': len(extraction_results)
            }
            
        except Exception as e:
            logger.error(f"Error in {email_type} processing: {e}")
            return {'processed_count': 0, 'extracted_count': 0, 'error_count': 1}
    
    async def _process_extraction_result(
        self, 
        db: AsyncSession, 
        result: Dict[str, Any],
        extractor
    ) -> Dict[str, Any]:
        """
        Process a single extraction result and save to database.
        
        Args:
            db: Database session
            result: Extraction result
            extractor: Email extractor instance
            
        Returns:
            Processing summary
        """
        email_data = result['email_data']
        extracted_items = result['extracted_items']
        processing_metadata = result['processing_metadata']
        
        logger.info(f"Processing extraction result for email {email_data['message_id']}")
        
        try:
            # Skip email logging - we don't need it anymore
            
            # Prepare stock data for database
            if extracted_items:
                stock_data_list = extractor.prepare_stock_data(extracted_items, email_data)
                
                # Upsert stocks (create/update)
                upsert_result = await StockService.upsert_stocks_from_email(
                    db=db,
                    stocks_data=stock_data_list,
                    email_id=email_data['message_id'],
                    category=extractor.category
                )
                
                logger.info(f"Upserted stocks for {email_data['message_id']}: {upsert_result}")
                
                return {
                    'extracted_count': len(extracted_items),
                    'database_operations': {
                        'created': upsert_result.get('created', 0),
                        'updated': upsert_result.get('updated', 0),
                        'deactivated': upsert_result.get('deleted', 0)
                    },
                    'success': True
                }
            else:
                logger.warning(f"No items extracted from email {email_data['message_id']}")
                return {
                    'extracted_count': 0,
                    'database_operations': {'created': 0, 'updated': 0, 'deactivated': 0},
                    'success': True
                }
                
        except Exception as e:
            logger.error(f"Error processing extraction result: {e}")
            
            # Skip error logging
            
            raise
    
    async def process_specific_email(
        self, 
        db: AsyncSession,
        message_id: str,
        email_type: str
    ) -> Dict[str, Any]:
        """
        Process a specific email by message ID.
        
        Args:
            db: Database session
            message_id: Gmail message ID
            email_type: Type of email
            
        Returns:
            Processing result
        """
        extractor = self.extractors.get(email_type)
        if not extractor:
            raise ValueError(f"No extractor found for email type: {email_type}")
        
        logger.info(f"Processing specific email: {message_id} ({email_type})")
        
        try:
            # Extract from specific email
            result = await extractor.extract_from_email_id(message_id)
            if not result:
                return {
                    'success': False,
                    'message': f'Could not extract data from email {message_id}',
                    'extracted_count': 0
                }
            
            # Process the result
            processing_result = await self._process_extraction_result(db, result, extractor)
            
            return {
                'success': True,
                'message': f'Successfully processed email {message_id}',
                'extracted_count': processing_result['extracted_count'],
                'database_operations': processing_result['database_operations'],
                'result': result
            }
            
        except Exception as e:
            logger.error(f"Error processing specific email {message_id}: {e}")
            return {
                'success': False,
                'message': f'Error processing email: {str(e)}',
                'extracted_count': 0
            }
    
    async def get_processing_summary(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Get overall processing summary and statistics.
        
        Args:
            db: Database session
            
        Returns:
            Processing summary
        """
        try:
            # Get email processing stats
            email_stats = await EmailService.get_processing_stats(db, days_back=7)
            
            # Get stock counts by category
            stock_counts = {}
            for category in ["daily", "digitalassets", "ideas", "etfs"]:
                stocks = await StockService.get_stocks_by_category(db, category)
                stock_counts[category] = len(stocks)
            
            # Get stocks needing updates
            stocks_needing_updates = await StockService.get_stocks_needing_price_updates(db)
            
            # Get stocks ready for alerts
            alert_ready_stocks = await StockService.get_stocks_for_alerts(db)
            
            return {
                'email_processing': email_stats,
                'stock_counts': stock_counts,
                'stocks_needing_price_updates': len(stocks_needing_updates),
                'stocks_ready_for_alerts': len(alert_ready_stocks),
                'total_active_stocks': sum(stock_counts.values()),
                'last_updated': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating processing summary: {e}")
            return {'error': str(e)}
    
    async def process_daily_workflow(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Process daily workflow (morning email processing).
        
        Args:
            db: Database session
            
        Returns:
            Workflow result
        """
        logger.info("Starting daily workflow")
        
        try:
            # Process emails from last 2 hours (morning emails)
            results = await self.process_recent_emails(
                db=db,
                email_types=["daily", "crypto"],  # Daily emails
                hours=2
            )
            
            # Also check for weekly emails if it's Monday/Tuesday
            from datetime import datetime
            weekday = datetime.now().weekday()  # 0=Monday, 1=Tuesday
            
            if weekday in [0, 1]:  # Monday or Tuesday
                weekly_results = await self.process_recent_emails(
                    db=db,
                    email_types=["ideas", "etf"],
                    hours=24  # Check last 24 hours for weekly emails
                )
                
                # Merge results
                results['by_type'].update(weekly_results['by_type'])
                results['total_processed'] += weekly_results['total_processed']
                results['total_extracted'] += weekly_results['total_extracted']
                results['total_errors'] += weekly_results['total_errors']
            
            return {
                'success': True,
                'message': 'Daily workflow completed',
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error in daily workflow: {e}")
            return {
                'success': False,
                'message': f'Daily workflow failed: {str(e)}',
                'results': None
            }