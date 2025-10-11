"""Main Lambda function for ArXiv paper collection agent."""

import argparse
from datetime import datetime
from typing import Any

from .arxiv_client import ArxivClient
from .config import get_environment_config
from .email_notifier import EmailNotifier
from .interface import LambdaEvent
from .llm_client import LLMClient
from .logger import get_logger
from .s3_storage import S3Storage
from .teams_notifier import TeamsNotifier
from .translator import Translator

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
    # Parse Lambda event
    lambda_event = LambdaEvent.model_validate(event)
    start_time = datetime.now()

    try:
        # Get configuration
        config = get_environment_config()

        logger.info("Starting paper collection agent")
        logger.info(f"Research topics: {config['research_topics']}")

        # Initialize clients
        s3_storage = S3Storage(config["s3_bucket"])
        arxiv_client = ArxivClient()
        llm_client = LLMClient(model=config["llm_model"], region=config["aws_bedrock_region"])

        # Initialize translator (shared by all notifiers)
        translator = Translator(
            region=config["aws_bedrock_region"],
            target_language=config["translate_target_language"],
        )

        # Initialize notifiers based on configuration
        email_notifier = None
        if config["email_recipient"]:
            email_notifier = EmailNotifier(
                config["email_recipient"],
                config["email_recipient"],
                region=config["aws_bedrock_region"],
                translator=translator,
            )

        teams_notifier = None
        if config["teams_webhook_url"]:
            teams_notifier = TeamsNotifier(
                config["teams_webhook_url"],
                translator=translator,
            )

        # Configuration is already merged with hardcoded overrides

        # Search for papers
        logger.info("Searching for papers on ArXiv")
        papers = arxiv_client.search_multiple_topics(
            topics=config["research_topics"],
            max_results_per_topic=config["max_results_per_topic"],
            days_back=config["days_back"],
            categories=config["arxiv_categories"],
            end_date=lambda_event.inclusive_end_date,
        )

        if not papers:
            logger.info("No papers found")
            return _create_response(200, "No papers found", {"papers_processed": 0})

        logger.info(f"Found {len(papers)} total papers")

        # Filter out already seen papers
        new_papers = s3_storage.filter_new_papers(papers)

        if not new_papers:
            logger.info("No new papers to process")
            return _create_response(200, "No new papers", {"papers_processed": 0})

        logger.info(f"Processing {len(new_papers)} new papers")

        # Evaluate paper relevance using LLM
        relevant_papers = llm_client.filter_relevant_papers(
            papers=new_papers,
            research_topics=config["research_topics"],
            threshold=config["relevance_threshold"],
            max_papers=config["max_papers_per_email"],
        )

        logger.info(f"Found {len(relevant_papers)} relevant papers")

        # Update seen papers list
        new_paper_ids = [paper.id for paper in new_papers]
        s3_storage.update_seen_papers(new_paper_ids)

        # Send notifications if there are relevant papers
        if relevant_papers:
            notification_results = []

            # Send email notification
            if email_notifier:
                email_success = email_notifier.send_paper_notification(
                    relevant_papers, config["research_topics"]
                )
                notification_results.append(("Email", email_success))

                if email_success:
                    logger.info("Email notification sent successfully")
                else:
                    logger.error("Failed to send email notification")

            # Send Teams notification
            if teams_notifier:
                teams_success = teams_notifier.send_paper_notification(
                    relevant_papers, config["research_topics"]
                )
                notification_results.append(("Teams", teams_success))

                if teams_success:
                    logger.info("Teams notification sent successfully")
                else:
                    logger.error("Failed to send Teams notification")

            # Check if all notifications failed
            if notification_results and not any(success for _, success in notification_results):
                error_msg = "All notification methods failed"
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
            f"notification_sent={len(relevant_papers) > 0}, "
            f"topics={config['research_topics']}"
        )

        return _create_response(
            200,
            "Processing completed successfully",
            {
                "papers_processed": len(new_papers),
                "relevant_papers": len(relevant_papers),
                "notification_sent": len(relevant_papers)
                > 0,  # True if we reach this point with relevant papers
            },
        )

    except Exception as e:
        error_msg = f"Error in paper collection agent: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # Try to send error notifications
        try:
            config = get_environment_config()

            # Initialize translator for error notifications
            translator = Translator(
                region=config["aws_bedrock_region"],
                target_language=config["translate_target_language"],
            )

            # Send email error notification
            if config["email_recipient"]:
                try:
                    email_notifier = EmailNotifier(
                        config["email_recipient"],
                        config["email_recipient"],
                        region=config["aws_bedrock_region"],
                        translator=translator,
                    )
                    email_notifier.send_error_notification(error_msg)
                except Exception as email_error:
                    logger.error(f"Failed to send email error notification: {email_error}")

            # Send Teams error notification
            if config["teams_webhook_url"]:
                try:
                    teams_notifier = TeamsNotifier(
                        config["teams_webhook_url"],
                        translator=translator,
                    )
                    teams_notifier.send_error_notification(error_msg)
                except Exception as teams_error:
                    logger.error(f"Failed to send Teams error notification: {teams_error}")

        except Exception as notification_error:
            logger.error(f"Failed to send error notifications: {notification_error}")

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


if __name__ == "__main__":
    """Local development execution."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run paper collection agent locally")
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date for paper search (YYYY-MM-DD format). Defaults to current date.",
    )
    args = parser.parse_args()

    # Parse end date if provided
    end_date = None
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()

    # Create test event
    test_event = {"inclusive_end_date": end_date.isoformat() if end_date else None}

    # Mock Lambda context
    class MockContext:
        function_name = "local-test"
        aws_request_id = "test-request-id"

    try:
        # Execute lambda handler
        result = lambda_handler(test_event, MockContext())

        print("✅ Execution completed!")
        print(f"Status: {result['statusCode']}")
        print(f"Message: {result['body']['message']}")

        if result["body"].get("papers_processed"):
            print(f"📄 Papers processed: {result['body']['papers_processed']}")
        if result["body"].get("relevant_papers"):
            print(f"🎯 Relevant papers found: {result['body']['relevant_papers']}")
        if result["body"].get("notification_sent"):
            print("📧 Notification sent successfully")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
