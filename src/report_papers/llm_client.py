"""LLM client for paper relevance evaluation and summarization using Amazon Bedrock."""

import json

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel

from .interface import Paper
from .logger import get_logger

logger = get_logger(__name__)


class PaperRelevance(BaseModel):
    """Paper relevance evaluation result."""

    relevance_score: float  # 0.0 to 1.0
    relevance_reason: str
    key_topics: list[str]
    is_relevant: bool


class LLMClient:
    """Client for LLM-based paper evaluation using Amazon Bedrock."""

    def __init__(self, model: str, region: str):
        self.model = model
        self.bedrock_runtime = boto3.client("bedrock-runtime", region_name=region)

        # Supported Bedrock models
        self.supported_models = {
            "anthropic.claude-3-haiku-20240307-v1:0",
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-3-opus-20240229-v1:0",
            "anthropic.claude-v2:1",
            "anthropic.claude-v2",
            "anthropic.claude-instant-v1",
        }

        if model not in self.supported_models:
            logger.warning(
                f"Model {model} may not be supported. Supported models: {self.supported_models}"
            )

    def _is_claude_v3_model(self) -> bool:
        """Check if the model is Claude v3 (uses different API format)."""
        return "claude-3" in self.model

    def evaluate_paper_relevance(
        self, paper: Paper, research_topics: list[str], threshold: float
    ) -> PaperRelevance:
        """
        Evaluate how relevant a paper is to the research topics.

        Args:
            paper: Paper object with title, summary, categories
            research_topics: List of research topics of interest
            threshold: Minimum relevance score to consider relevant

        Returns:
            PaperRelevance object with evaluation results
        """
        prompt = self._create_evaluation_prompt(paper, research_topics)

        try:
            result = self._evaluate_with_bedrock(prompt)

            # Parse the result
            relevance = self._parse_evaluation_result(result, threshold)
            logger.info(
                f"Evaluated paper {paper.id}: "
                f"score={relevance.relevance_score:.2f}, "
                f"relevant={relevance.is_relevant}"
            )

            return relevance

        except Exception as e:
            logger.error(f"Error evaluating paper relevance: {e}")
            # Return low relevance score on error
            return PaperRelevance(
                relevance_score=0.1,
                relevance_reason="Error during evaluation",
                key_topics=[],
                is_relevant=False,
            )

    def _create_evaluation_prompt(self, paper: Paper, research_topics: list[str]) -> str:
        """Create prompt for paper relevance evaluation."""
        topics_str = ", ".join(research_topics)

        prompt = f"""
You are a research assistant evaluating academic papers for relevance to specific research topics.

Research Topics of Interest: {topics_str}

Paper Details:
Title: {paper.title}
Abstract: {paper.summary}
Categories: {", ".join(paper.categories)}

Please evaluate this paper's relevance to the research topics and provide your assessment in the following JSON format:

{{
    "relevance_score": <float between 0.0 and 1.0>,
    "relevance_reason": "<explanation of why this score was assigned>",
    "key_topics": ["<topic1>", "<topic2>", ...],
    "is_highly_relevant": <true/false for scores >= 0.7>
}}

Scoring Guidelines:
- 0.9-1.0: Directly addresses the research topics as primary focus
- 0.7-0.8: Strong relevance, covers important aspects of the topics
- 0.5-0.6: Moderate relevance, some connection to the topics
- 0.3-0.4: Weak relevance, tangential connection
- 0.0-0.2: Little to no relevance

Focus on: energy markets, electricity markets, power systems economics, renewable energy integration, market design, pricing mechanisms, grid economics.

Respond only with the JSON object, no additional text.
"""
        return prompt.strip()

    def _evaluate_with_bedrock(self, prompt: str) -> str:
        """Evaluate using Amazon Bedrock."""
        try:
            if self._is_claude_v3_model():
                # Claude v3 uses the Messages API format
                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 500,
                    "temperature": 0.1,
                    "messages": [{"role": "user", "content": prompt}],
                }
            else:
                # Claude v2 and older use the Text Completions format
                body = {
                    "prompt": f"\n\nHuman: You are a helpful research assistant specialized in energy and electricity market research.\n\n{prompt}\n\nAssistant:",
                    "max_tokens_to_sample": 500,
                    "temperature": 0.1,
                    "top_p": 1,
                    "stop_sequences": ["\n\nHuman:"],
                }

            response = self.bedrock_runtime.invoke_model(
                modelId=self.model,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())

            if self._is_claude_v3_model():
                # Claude v3 response format
                return str(response_body["content"][0]["text"])
            else:
                # Claude v2 response format
                return str(response_body["completion"])

        except ClientError as e:
            logger.error(f"Bedrock ClientError: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling Bedrock: {e}")
            raise

    def _parse_evaluation_result(self, result: str, threshold: float) -> PaperRelevance:
        """Parse LLM evaluation result into PaperRelevance object."""
        try:
            # Clean up the result to extract JSON
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]
            if result.endswith("```"):
                result = result[:-3]

            data = json.loads(result)

            relevance_score = float(data.get("relevance_score", 0.0))
            is_relevant = data.get("is_highly_relevant", relevance_score >= threshold)

            return PaperRelevance(
                relevance_score=relevance_score,
                relevance_reason=data.get("relevance_reason", ""),
                key_topics=data.get("key_topics", []),
                is_relevant=is_relevant,
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Error parsing evaluation result: {e}")
            logger.debug(f"Raw result: {result}")

            # Fallback: try to extract score from text
            score = 0.1
            if "high" in result.lower() or "relevant" in result.lower():
                score = 0.7
            elif "moderate" in result.lower():
                score = 0.5

            return PaperRelevance(
                relevance_score=score,
                relevance_reason="Parsing error - fallback evaluation",
                key_topics=[],
                is_relevant=score >= threshold,
            )

    def evaluate_multiple_papers(
        self, papers: list[Paper], research_topics: list[str], threshold: float
    ) -> list[tuple[Paper, PaperRelevance]]:
        """
        Evaluate multiple papers for relevance.

        Args:
            papers: List of Paper objects
            research_topics: List of research topics
            threshold: Minimum relevance score

        Returns:
            List of (paper, relevance) tuples, sorted by relevance score
        """
        results = []

        for paper in papers:
            try:
                relevance = self.evaluate_paper_relevance(paper, research_topics, threshold)
                results.append((paper, relevance))
            except Exception as e:
                logger.error(f"Error evaluating paper {paper.id}: {e}")
                continue

        # Sort by relevance score (highest first)
        results.sort(key=lambda x: x[1].relevance_score, reverse=True)

        logger.info(
            f"Evaluated {len(results)} papers, "
            f"{sum(1 for _, r in results if r.is_relevant)} relevant"
        )

        return results

    def filter_relevant_papers(
        self,
        papers: list[Paper],
        research_topics: list[str],
        threshold: float,
        max_papers: int,
    ) -> list[tuple[Paper, PaperRelevance]]:
        """
        Filter and return only relevant papers.

        Args:
            papers: List of Paper objects
            research_topics: List of research topics
            threshold: Minimum relevance score
            max_papers: Maximum number of papers to return

        Returns:
            List of relevant (paper, relevance) tuples
        """
        all_evaluations = self.evaluate_multiple_papers(papers, research_topics, threshold)

        # Filter for relevant papers only
        relevant_papers = [
            (paper, relevance) for paper, relevance in all_evaluations if relevance.is_relevant
        ]

        # Return top N papers
        return relevant_papers[:max_papers]
