"""S3-based storage for duplicate detection only."""

import json
import os
import boto3
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

from .interface import Paper
from .logger import get_logger

logger = get_logger(__name__)


class S3Storage:
    """S3-based storage for duplicate detection."""

    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        s3_endpoint = os.getenv("S3_ENDPOINT")
        self.s3_client = boto3.client("s3", endpoint_url=s3_endpoint)

    def load_seen_papers(self) -> set[str]:
        """
        Load set of previously seen paper IDs from S3.

        Returns:
            Set of paper IDs that have been processed before
        """
        key = "seen_papers.json"

        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            data = json.loads(response["Body"].read().decode("utf-8"))

            # Filter out papers older than 30 days to prevent infinite growth
            cutoff_date = datetime.now() - timedelta(days=30)
            current_papers = {}

            for paper_id, timestamp_str in data.items():
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    if timestamp > cutoff_date:
                        current_papers[paper_id] = timestamp_str
                except (ValueError, TypeError):
                    # Skip invalid timestamps
                    continue

            # Save cleaned up data back to S3
            if len(current_papers) != len(data):
                self.save_seen_papers(set(current_papers.keys()))
                logger.info(f"Cleaned up seen papers: {len(data)} -> {len(current_papers)}")

            return set(current_papers.keys())

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                logger.info("No seen papers file found, starting fresh")
                return set()
            else:
                logger.error(f"Error loading seen papers from S3: {e}")
                return set()
        except Exception as e:
            logger.error(f"Unexpected error loading seen papers: {e}")
            return set()

    def save_seen_papers(self, paper_ids: set[str]) -> bool:
        """
        Save set of seen paper IDs to S3 with timestamps.

        Args:
            paper_ids: Set of paper IDs to save

        Returns:
            True if successful, False otherwise
        """
        key = "seen_papers.json"
        current_time = datetime.now().isoformat()

        # Create data structure with timestamps
        data = {paper_id: current_time for paper_id in paper_ids}

        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(data, indent=2),
                ContentType="application/json",
            )
            logger.info(f"Saved {len(paper_ids)} seen papers to S3")
            return True

        except ClientError as e:
            logger.error(f"Error saving seen papers to S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving seen papers: {e}")
            return False

    def update_seen_papers(self, new_paper_ids: list[str]) -> bool:
        """
        Update the seen papers list with new paper IDs.

        Args:
            new_paper_ids: List of new paper IDs to add

        Returns:
            True if successful, False otherwise
        """
        # Load existing seen papers
        existing_papers = self.load_seen_papers()

        # Add new paper IDs
        updated_papers = existing_papers.union(set(new_paper_ids))

        # Save updated list
        return self.save_seen_papers(updated_papers)

    def filter_new_papers(self, papers: list[Paper]) -> list[Paper]:
        """
        Filter out papers that have been seen before.

        Args:
            papers: List of Paper objects

        Returns:
            List of new (unseen) papers
        """
        seen_papers = self.load_seen_papers()
        new_papers = [paper for paper in papers if paper.id not in seen_papers]

        logger.info(f"Filtered {len(papers)} papers -> {len(new_papers)} new papers")
        return new_papers
