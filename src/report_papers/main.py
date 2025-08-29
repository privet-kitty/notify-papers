"""Main Lambda function for ArXiv paper collection agent."""

import os
from typing import Dict, Any
from datetime import datetime

from .arxiv_client import ArxivClient
from .llm_client import LLMClient
from .s3_storage import S3Storage
from .email_notifier import EmailNotifier
from .logger import get_logger

logger = get_logger(__name__)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for paper collection agent.
    
    Args:
        event: Lambda event (usually from CloudWatch Events)
        context: Lambda context
        
    Returns:
        Response dictionary
    """
    start_time = datetime.now()
    
    try:
        # Get environment variables
        config = _get_environment_config()
        
        logger.info("Starting paper collection agent")
        logger.info(f"Research topics: {config['research_topics']}")
        
        # Initialize clients
        s3_storage = S3Storage(config['s3_bucket'])
        arxiv_client = ArxivClient()
        llm_client = LLMClient(
            model=config['llm_model'],
            region=config.get('aws_bedrock_region', 'us-east-1')
        )
        email_notifier = EmailNotifier(
            config['email_recipient'],
            config['email_recipient'],
            region=config.get('aws_bedrock_region', 'us-east-1')
        )
        
        # Use hardcoded configuration
        hardcoded_config = {
            "research_topics": [
                "electricity market",
                "energy market",
                "renewable energy market",
                "power market"
            ],
            "max_results_per_topic": 20,
            "days_back": 7,
            "relevance_threshold": 0.7,
            "min_relevance_score": 0.5,
            "arxiv_categories": [
                "econ.EM",
                "econ.GN", 
                "cs.CE",
                "cs.LG",
                "cs.GT",
                "math.OC",
                "math.CO",
                "stat.AP",
                "eess.SY"
            ],
            "llm_model": config['llm_model'],
            "max_papers_per_email": 10
        }
        config.update(hardcoded_config)
        
        # Search for papers
        logger.info("Searching for papers on ArXiv")
        papers = arxiv_client.search_multiple_topics(
            topics=config['research_topics'],
            max_results_per_topic=config['max_results_per_topic'],
            days_back=config['days_back']
        )
        
        if not papers:
            logger.info("No papers found")
            return _create_response(200, "No papers found", {"papers_processed": 0})
        
        logger.info(f"Found {len(papers)} total papers")
        
        # Convert papers to dictionaries for processing
        paper_dicts = [paper.to_dict() for paper in papers]
        
        # Filter out already seen papers
        new_papers = s3_storage.filter_new_papers(paper_dicts)
        
        if not new_papers:
            logger.info("No new papers to process")
            return _create_response(200, "No new papers", {"papers_processed": 0})
        
        logger.info(f"Processing {len(new_papers)} new papers")
        
        # Evaluate paper relevance using LLM
        relevant_papers = llm_client.filter_relevant_papers(
            papers=new_papers,
            research_topics=config['research_topics'],
            threshold=config['relevance_threshold'],
            max_papers=config.get('max_papers_per_email', 10)
        )
        
        logger.info(f"Found {len(relevant_papers)} relevant papers")
        
        # Update seen papers list
        new_paper_ids = [paper['id'] for paper in new_papers]
        s3_storage.update_seen_papers(new_paper_ids)
        
        # Send email notification if there are relevant papers
        if relevant_papers:
            success = email_notifier.send_paper_notification(
                relevant_papers, 
                config['research_topics']
            )
            
            if success:
                logger.info("Email notification sent successfully")
            else:
                error_msg = "Failed to send email notification"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
        
        # Log processing results to CloudWatch
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"PROCESSING_SUMMARY: "
                   f"total_papers={len(papers)}, "
                   f"new_papers={len(new_papers)}, "
                   f"relevant_papers={len(relevant_papers)}, "
                   f"processing_time={processing_time:.2f}s, "
                   f"email_sent={len(relevant_papers) > 0}, "
                   f"topics={config['research_topics']}")
        
        return _create_response(200, "Processing completed successfully", {
            "papers_processed": len(new_papers),
            "relevant_papers": len(relevant_papers),
            "email_sent": len(relevant_papers) > 0  # True if we reach this point with relevant papers
        })
        
    except Exception as e:
        error_msg = f"Error in paper collection agent: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Try to send error notification
        try:
            config = _get_environment_config()
            email_notifier = EmailNotifier(
                config['email_recipient'],
                config['email_recipient'],
                region=config.get('aws_bedrock_region', 'us-east-1')
            )
            email_notifier.send_error_notification(error_msg)
        except Exception as email_error:
            logger.error(f"Failed to send error notification: {email_error}")
        
        return _create_response(500, error_msg, {"error": True})


def _get_environment_config() -> Dict[str, Any]:
    """Get configuration from environment variables."""
    research_topics = os.environ.get('RESEARCH_TOPICS', 'energy market,electricity market').split(',')
    research_topics = [topic.strip() for topic in research_topics]
    
    return {
        's3_bucket': os.environ.get('S3_CONFIG_BUCKET'),
        'email_recipient': os.environ.get('EMAIL_RECIPIENT'),
        'research_topics': research_topics,
        'llm_model': os.environ.get('LLM_MODEL', 'anthropic.claude-3-haiku-20240307-v1:0'),
        'aws_bedrock_region': os.environ.get('AWS_BEDROCK_REGION', 'us-east-1'),
        'max_results_per_topic': int(os.environ.get('MAX_RESULTS_PER_TOPIC', '20')),
        'days_back': int(os.environ.get('DAYS_BACK', '7')),
        'relevance_threshold': float(os.environ.get('RELEVANCE_THRESHOLD', '0.7')),
        'max_papers_per_email': int(os.environ.get('MAX_PAPERS_PER_EMAIL', '10'))
    }


def _create_response(status_code: int, message: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create standardized Lambda response."""
    response = {
        "statusCode": status_code,
        "body": {
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
    }
    
    if data:
        response["body"].update(data)
    
    return response


def test_configuration() -> None:
    """Test the configuration and all components."""
    logger.info("Testing configuration and components")
    
    try:
        config = _get_environment_config()
        
        # Test S3 storage (for duplicate detection only)
        if config['s3_bucket']:
            s3_storage = S3Storage(config['s3_bucket'])
            logger.info("S3 storage: OK")
        else:
            logger.warning("S3 bucket not configured")
        
        # Test ArXiv client
        arxiv_client = ArxivClient()
        papers = arxiv_client.search_papers("energy market", max_results=2, days_back=30)
        logger.info(f"ArXiv client: OK - found {len(papers)} papers")
        
        # Test LLM client (Bedrock)
        try:
            llm_client = LLMClient(model=config['llm_model'])
            if papers:
                paper_dict = papers[0].to_dict()
                relevance = llm_client.evaluate_paper_relevance(
                    paper_dict, 
                    config['research_topics']
                )
                logger.info(f"LLM client: OK - relevance score: {relevance.relevance_score}")
            else:
                logger.info("LLM client: OK - no papers to test")
        except Exception as e:
            logger.warning(f"LLM client: Failed - {e}")
        
        # Test email notifier
        email_notifier = EmailNotifier(
            config['email_recipient'],
            config['email_recipient']
        )
        success = email_notifier.test_email_configuration()
        logger.info(f"Email notifier: {'OK' if success else 'FAILED'}")
        
        logger.info("Configuration test completed")
        
    except Exception as e:
        logger.error(f"Configuration test failed: {e}", exc_info=True)


if __name__ == "__main__":
    # For local testing
    test_configuration()