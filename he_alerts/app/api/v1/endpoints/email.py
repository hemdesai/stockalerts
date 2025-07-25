"""
Email processing endpoints.
"""
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_database, get_email_processor
from app.core.logging import get_logger
from app.services.email_processor import EmailProcessor

logger = get_logger(__name__)
router = APIRouter()


@router.post("/process")
async def process_recent_emails(
    email_types: Optional[List[str]] = Query(None, description="Email types to process"),
    hours: int = Query(24, description="Hours back to search", ge=1, le=168),
    db: AsyncSession = Depends(get_database),
    processor: EmailProcessor = Depends(get_email_processor)
) -> EmailProcessingResult:
    """
    Process recent emails and extract data.
    
    Args:
        email_types: List of email types (daily, crypto, ideas, etf)
        hours: Hours back to search for emails
        db: Database session
        processor: Email processor instance
        
    Returns:
        Processing results
    """
    try:
        logger.info(f"Processing recent emails: types={email_types}, hours={hours}")
        
        # Validate email types
        valid_types = ["daily", "crypto", "ideas", "etf"]
        if email_types:
            invalid_types = [t for t in email_types if t not in valid_types]
            if invalid_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid email types: {invalid_types}. Valid types: {valid_types}"
                )
        
        # Process emails
        results = await processor.process_recent_emails(
            db=db,
            email_types=email_types,
            hours=hours
        )
        
        return {
            "processed_count": results['total_processed'],
            "successful_count": results['total_processed'] - results['total_errors'],
            "failed_count": results['total_errors'],
            "skipped_count": 0,
            "total_extracted_items": results['total_extracted'],
            "processing_time": results['processing_time'],
            "errors": []
        }
        
    except Exception as e:
        logger.error(f"Error processing recent emails: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process/{message_id}")
async def process_specific_email(
    message_id: str,
    email_type: str = Query(..., description="Email type"),
    db: AsyncSession = Depends(get_database),
    processor: EmailProcessor = Depends(get_email_processor)
) -> Dict[str, Any]:
    """
    Process a specific email by message ID.
    
    Args:
        message_id: Gmail message ID
        email_type: Type of email (daily, crypto, ideas, etf)
        db: Database session
        processor: Email processor instance
        
    Returns:
        Processing result
    """
    try:
        # Validate email type
        valid_types = ["daily", "crypto", "ideas", "etf"]
        if email_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid email type: {email_type}. Valid types: {valid_types}"
            )
        
        result = await processor.process_specific_email(
            db=db,
            message_id=message_id,
            email_type=email_type
        )
        
        if not result['success']:
            raise HTTPException(status_code=404, detail=result['message'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing specific email {message_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/workflow/daily")
async def run_daily_workflow(
    db: AsyncSession = Depends(get_database),
    processor: EmailProcessor = Depends(get_email_processor)
) -> Dict[str, Any]:
    """
    Run the daily email processing workflow.
    
    This processes daily/crypto emails (morning workflow) and checks for
    weekly emails on Mondays/Tuesdays.
    
    Args:
        db: Database session
        processor: Email processor instance
        
    Returns:
        Workflow results
    """
    try:
        logger.info("Starting daily workflow via API")
        
        result = await processor.process_daily_workflow(db)
        
        return result
        
    except Exception as e:
        logger.error(f"Error running daily workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_processing_summary(
    db: AsyncSession = Depends(get_database),
    processor: EmailProcessor = Depends(get_email_processor)
) -> Dict[str, Any]:
    """
    Get overall processing summary and system status.
    
    Args:
        db: Database session
        processor: Email processor instance
        
    Returns:
        Processing summary
    """
    try:
        summary = await processor.get_processing_summary(db)
        return summary
        
    except Exception as e:
        logger.error(f"Error getting processing summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))