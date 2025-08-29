"""Configuration management for paper collection agent."""

import os
from typing import TypedDict


class AgentConfig(TypedDict, total=True):
    """Configuration for the paper collection agent.

    This TypedDict defines the structure of the configuration dictionary
    used throughout the application. All fields are required.
    """

    # Required fields from environment
    email_recipient: str
    s3_bucket: str

    # Required fields with defaults
    research_topics: list[str]
    llm_model: str
    aws_bedrock_region: str
    max_results_per_topic: int
    days_back: int
    relevance_threshold: float
    min_relevance_score: float
    max_papers_per_email: int
    translate_target_language: str
    arxiv_categories: list[str]


def get_environment_config() -> AgentConfig:
    """
    Get configuration from environment variables with required validation.

    Returns:
        AgentConfig: Configuration dictionary with all required fields populated

    Raises:
        ValueError: If required environment variables are not set
    """
    # Validate required environment variables
    email_recipient = os.environ.get("EMAIL_RECIPIENT")
    if not email_recipient:
        raise ValueError("EMAIL_RECIPIENT environment variable is required")

    s3_bucket = os.environ.get("S3_PAPERS_BUCKET")
    if not s3_bucket:
        raise ValueError("S3_PAPERS_BUCKET environment variable is required")

    # Build config with defaults and environment overrides
    config: AgentConfig = {
        # Required fields from environment
        "email_recipient": email_recipient,
        "s3_bucket": s3_bucket,
        # Fields with defaults that can be overridden
        "research_topics": [
            "electricity market",
            "energy market",
        ],
        "llm_model": "anthropic.claude-3-haiku-20240307-v1:0",
        "aws_bedrock_region": "us-east-1",
        "max_results_per_topic": 40,
        "days_back": 3,
        "relevance_threshold": 0.7,
        "min_relevance_score": 0.5,
        "max_papers_per_email": 15,
        "translate_target_language": "en",
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
    }

    # Override with environment variables if they exist
    if research_topics_env := os.environ.get("RESEARCH_TOPICS"):
        research_topics = [topic.strip() for topic in research_topics_env.split(",")]
        config["research_topics"] = research_topics

    if llm_model := os.environ.get("LLM_MODEL"):
        config["llm_model"] = llm_model

    if aws_region := os.environ.get("AWS_BEDROCK_REGION"):
        config["aws_bedrock_region"] = aws_region

    if max_results := os.environ.get("MAX_RESULTS_PER_TOPIC"):
        config["max_results_per_topic"] = int(max_results)

    if days_back := os.environ.get("DAYS_BACK"):
        config["days_back"] = int(days_back)

    if relevance_threshold := os.environ.get("RELEVANCE_THRESHOLD"):
        config["relevance_threshold"] = float(relevance_threshold)

    if max_papers := os.environ.get("MAX_PAPERS_PER_EMAIL"):
        config["max_papers_per_email"] = int(max_papers)

    if translate_lang := os.environ.get("TRANSLATE_TARGET_LANGUAGE"):
        config["translate_target_language"] = translate_lang

    if arxiv_categories_env := os.environ.get("ARXIV_CATEGORIES"):
        arxiv_categories = [category.strip() for category in arxiv_categories_env.split(",")]
        config["arxiv_categories"] = arxiv_categories

    return config
