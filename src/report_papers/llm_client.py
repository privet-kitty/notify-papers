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

        Raises:
            Exception: If Bedrock invocation or response parsing fails. Callers
                must treat this as "not yet evaluated" so the paper is retried
                on a later run rather than silently marked as not-relevant.
        """
        prompt = self._create_evaluation_prompt(paper, research_topics)

        result = self._evaluate_with_bedrock(prompt)
        relevance = self._parse_evaluation_result(result, threshold)
        logger.info(
            f"Evaluated paper {paper.id}: "
            f"score={relevance.relevance_score:.2f}, "
            f"relevant={relevance.is_relevant}"
        )

        return relevance

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

Respond only with the JSON object, no additional text.
"""
        return prompt.strip()

    def _evaluate_with_bedrock(self, prompt: str) -> str:
        """Evaluate using Amazon Bedrock."""
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "temperature": 0.1,
                "messages": [{"role": "user", "content": prompt}],
            }

            response = self.bedrock_runtime.invoke_model(
                modelId=self.model,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            return str(response_body["content"][0]["text"])

        except ClientError as e:
            logger.error(f"Bedrock ClientError: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling Bedrock: {e}")
            raise

    def _parse_evaluation_result(self, result: str, threshold: float) -> PaperRelevance:
        """Parse LLM evaluation result into PaperRelevance object.

        Raises on malformed responses so the caller can retry the paper on a
        later run instead of trusting a fabricated score.
        """
        # Clean up the result to extract JSON
        result = result.strip()
        if result.startswith("```json"):
            result = result[7:]
        if result.endswith("```"):
            result = result[:-3]

        data = json.loads(result)

        relevance_score = float(data["relevance_score"])
        is_relevant = data.get("is_highly_relevant", relevance_score >= threshold)

        return PaperRelevance(
            relevance_score=relevance_score,
            relevance_reason=data.get("relevance_reason", ""),
            key_topics=data.get("key_topics", []),
            is_relevant=is_relevant,
        )

    def evaluate_multiple_papers(
        self, papers: list[Paper], research_topics: list[str], threshold: float
    ) -> list[tuple[Paper, PaperRelevance]]:
        """
        Evaluate multiple papers for relevance.

        Papers whose evaluation fails (Bedrock error, malformed response, etc.)
        are skipped — they are NOT included in the returned list so the caller
        can avoid marking them as seen and retry them later.

        Args:
            papers: List of Paper objects
            research_topics: List of research topics
            threshold: Minimum relevance score

        Returns:
            List of (paper, relevance) tuples for successfully evaluated papers,
            sorted by relevance score
        """
        results = []

        for paper in papers:
            try:
                relevance = self.evaluate_paper_relevance(paper, research_topics, threshold)
                results.append((paper, relevance))
            except Exception as e:
                logger.error(
                    f"Skipping paper {paper.id} due to evaluation error (will retry later): {e}"
                )
                continue

        # Sort by relevance score (highest first)
        results.sort(key=lambda x: x[1].relevance_score, reverse=True)

        logger.info(
            f"Evaluated {len(results)}/{len(papers)} papers successfully, "
            f"{sum(1 for _, r in results if r.is_relevant)} relevant"
        )

        return results

    def filter_relevant_papers(
        self,
        papers: list[Paper],
        research_topics: list[str],
        threshold: float,
        max_papers: int,
    ) -> tuple[list[tuple[Paper, PaperRelevance]], list[str]]:
        """
        Filter and return only relevant papers, plus the IDs of all
        successfully evaluated papers (relevant or not).

        Args:
            papers: List of Paper objects
            research_topics: List of research topics
            threshold: Minimum relevance score
            max_papers: Maximum number of relevant papers to return

        Returns:
            Tuple of:
              - List of relevant (paper, relevance) tuples (capped at max_papers)
              - List of paper IDs that were successfully evaluated. Callers
                should only mark these as seen; papers whose evaluation failed
                are omitted so they get retried on the next run.
        """
        all_evaluations = self.evaluate_multiple_papers(papers, research_topics, threshold)

        evaluated_paper_ids = [paper.id for paper, _ in all_evaluations]

        relevant_papers = [
            (paper, relevance) for paper, relevance in all_evaluations if relevance.is_relevant
        ]

        return relevant_papers[:max_papers], evaluated_paper_ids
