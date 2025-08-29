"""S3-based storage for stateless duplicate detection and configuration management."""

import json
import boto3
import hashlib
from datetime import datetime, timedelta
from typing import Set, List, Dict, Any, Optional
from botocore.exceptions import ClientError, NoCredentialsError

from .logger import get_logger

logger = get_logger(__name__)


class S3Storage:
    """S3-based storage for configuration and duplicate detection."""
    
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3')
        
    def _get_paper_hash(self, paper_id: str) -> str:
        """Generate hash for paper ID."""
        return hashlib.sha256(paper_id.encode()).hexdigest()[:16]
    
    def load_seen_papers(self) -> Set[str]:
        """
        Load set of previously seen paper IDs from S3.
        
        Returns:
            Set of paper IDs that have been processed before
        """
        key = "seen_papers.json"
        
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            data = json.loads(response['Body'].read().decode('utf-8'))
            
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
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.info("No seen papers file found, starting fresh")
                return set()
            else:
                logger.error(f"Error loading seen papers from S3: {e}")
                return set()
        except Exception as e:
            logger.error(f"Unexpected error loading seen papers: {e}")
            return set()
    
    def save_seen_papers(self, paper_ids: Set[str]) -> bool:
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
                ContentType='application/json'
            )
            logger.info(f"Saved {len(paper_ids)} seen papers to S3")
            return True
            
        except ClientError as e:
            logger.error(f"Error saving seen papers to S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving seen papers: {e}")
            return False
    
    def update_seen_papers(self, new_paper_ids: List[str]) -> bool:
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
    
    def filter_new_papers(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out papers that have been seen before.
        
        Args:
            papers: List of paper dictionaries with 'id' field
            
        Returns:
            List of new (unseen) papers
        """
        seen_papers = self.load_seen_papers()
        new_papers = [paper for paper in papers if paper.get('id') not in seen_papers]
        
        logger.info(f"Filtered {len(papers)} papers -> {len(new_papers)} new papers")
        return new_papers
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from S3.
        
        Returns:
            Configuration dictionary
        """
        key = "config.json"
        
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            config = json.loads(response['Body'].read().decode('utf-8'))
            logger.info("Loaded configuration from S3")
            return config
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                # Return default configuration
                default_config = self._get_default_config()
                logger.info("No config file found, using default configuration")
                # Save default config to S3 for future use
                self.save_config(default_config)
                return default_config
            else:
                logger.error(f"Error loading config from S3: {e}")
                return self._get_default_config()
        except Exception as e:
            logger.error(f"Unexpected error loading config: {e}")
            return self._get_default_config()
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """
        Save configuration to S3.
        
        Args:
            config: Configuration dictionary to save
            
        Returns:
            True if successful, False otherwise
        """
        key = "config.json"
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(config, indent=2),
                ContentType='application/json'
            )
            logger.info("Saved configuration to S3")
            return True
            
        except ClientError as e:
            logger.error(f"Error saving config to S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving config: {e}")
            return False
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "research_topics": [
                "electricity market",
                "energy market",
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
                "eess.SY",
            ],
            "llm_model": "anthropic.claude-3-haiku-20240307-v1:0",
            "last_updated": datetime.now().isoformat()
        }
    
    def save_processing_log(self, log_data: Dict[str, Any]) -> bool:
        """
        Save processing log to S3 for debugging and monitoring.
        
        Args:
            log_data: Log data to save
            
        Returns:
            True if successful, False otherwise
        """
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        key = f"logs/processing-{timestamp}.json"
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(log_data, indent=2, default=str),
                ContentType='application/json'
            )
            logger.info(f"Saved processing log to S3: {key}")
            return True
            
        except ClientError as e:
            logger.error(f"Error saving processing log to S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving processing log: {e}")
            return False