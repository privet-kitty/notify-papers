"""Main Lambda function for ArXiv paper collection agent."""

from datetime import datetime
from typing import Any

from .arxiv_client import ArxivClient
from .config import get_environment_config
from .email_notifier import EmailNotifier
from .llm_client import LLMClient
from .logger import get_logger
from .s3_storage import S3Storage

logger = get_logger(__name__)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
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
        # Get configuration
        config = get_environment_config()

        logger.info("Starting paper collection agent")
        logger.info(f"Research topics: {config['research_topics']}")

        # Initialize clients
        if not config["s3_bucket"]:
            raise ValueError("S3_PAPERS_BUCKET environment variable is required")
        s3_storage = S3Storage(config["s3_bucket"])
        arxiv_client = ArxivClient()
        llm_client = LLMClient(
            model=config["llm_model"], region=config.get("aws_bedrock_region", "us-east-1")
        )
        email_notifier = EmailNotifier(
            config["email_recipient"],
            config["email_recipient"],
            region=config.get("aws_bedrock_region", "us-east-1"),
            target_language=config["translate_target_language"],
        )

        # Configuration is already merged with hardcoded overrides

        # Search for papers
        logger.info("Searching for papers on ArXiv")
        papers = arxiv_client.search_multiple_topics(
            topics=config["research_topics"],
            max_results_per_topic=config["max_results_per_topic"],
            days_back=config["days_back"],
            categories=config["arxiv_categories"],
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
            research_topics=config["research_topics"],
            threshold=config["relevance_threshold"],
            max_papers=config.get("max_papers_per_email", 10),
        )

        logger.info(f"Found {len(relevant_papers)} relevant papers")

        # Update seen papers list
        new_paper_ids = [paper["id"] for paper in new_papers]
        s3_storage.update_seen_papers(new_paper_ids)

        # Send email notification if there are relevant papers
        if relevant_papers:
            success = email_notifier.send_paper_notification(
                relevant_papers, config["research_topics"]
            )

            if success:
                logger.info("Email notification sent successfully")
            else:
                error_msg = "Failed to send email notification"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

        # Log processing results to CloudWatch
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"PROCESSING_SUMMARY: "
            f"total_papers={len(papers)}, "
            f"new_papers={len(new_papers)}, "
            f"relevant_papers={len(relevant_papers)}, "
            f"processing_time={processing_time:.2f}s, "
            f"email_sent={len(relevant_papers) > 0}, "
            f"topics={config['research_topics']}"
        )

        return _create_response(
            200,
            "Processing completed successfully",
            {
                "papers_processed": len(new_papers),
                "relevant_papers": len(relevant_papers),
                "email_sent": len(relevant_papers)
                > 0,  # True if we reach this point with relevant papers
            },
        )

    except Exception as e:
        error_msg = f"Error in paper collection agent: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # Try to send error notification
        try:
            config = get_environment_config()
            email_notifier = EmailNotifier(
                config["email_recipient"],
                config["email_recipient"],
                region=config.get("aws_bedrock_region", "us-east-1"),
                target_language=config.get("translate_target_language", "ja"),
            )
            email_notifier.send_error_notification(error_msg)
        except Exception as email_error:
            logger.error(f"Failed to send error notification: {email_error}")

        return _create_response(500, error_msg, {"error": True})


def _create_response(
    status_code: int, message: str, data: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Create standardized Lambda response."""
    body: dict[str, Any] = {"message": message, "timestamp": datetime.now().isoformat()}

    if data:
        body.update(data)

    response = {
        "statusCode": status_code,
        "body": body,
    }

    return response
