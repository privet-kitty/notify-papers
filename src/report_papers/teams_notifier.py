"""Microsoft Teams notification system for paper alerts."""

import json
from datetime import datetime
from typing import Any

import requests

from .interface import Paper
from .logger import get_logger
from .translator import Translator

logger = get_logger(__name__)

# Teams webhook payload size limit (28KB), use 27KB for safety margin
MAX_PAYLOAD_SIZE_BYTES = 27 * 1024


class TeamsNotifier:
    """Microsoft Teams notification system using Adaptive Cards."""

    def __init__(self, webhook_url: str, translator: Translator):
        self.webhook_url = webhook_url
        self.translator = translator

    def _send_adaptive_card(self, card_content: dict[str, Any]) -> bool:
        """
        Send Adaptive Card to Teams webhook.

        Args:
            card_content: Adaptive Card JSON content

        Returns:
            True if message sent successfully, False otherwise
        """
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card_content,
                }
            ],
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()

            logger.info("Teams notification sent successfully")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to send Teams notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Teams notification: {e}")
            return False

    def send_paper_notification(
        self, relevant_papers: list[tuple[Paper, Any]], research_topics: list[str]
    ) -> bool:
        """
        Send Teams notification with relevant papers.

        Args:
            relevant_papers: List of (paper, relevance) tuples
            research_topics: List of research topics

        Returns:
            True if notification sent successfully, False otherwise
        """
        if not relevant_papers:
            logger.info("No relevant papers to send")
            return True

        try:
            # Translate paper summaries
            translated_papers = self._prepare_translated_papers(relevant_papers)

            # Find optimal number of papers that fit within size limit
            optimal_count = self._find_optimal_paper_count(translated_papers, research_topics)

            if optimal_count < len(translated_papers):
                logger.warning(
                    f"Payload size limit: showing {optimal_count} of {len(translated_papers)} papers"
                )

            # Generate card with optimal number of papers
            card_content = self._generate_papers_card(
                translated_papers[:optimal_count], research_topics, len(translated_papers)
            )
            return self._send_adaptive_card(card_content)

        except Exception as e:
            logger.error(f"Error generating Teams notification: {e}")
            return False

    def _prepare_translated_papers(
        self, relevant_papers: list[tuple[Paper, Any]]
    ) -> list[tuple[Paper, Any, str]]:
        """
        Translate all abstracts once to avoid duplicate translation calls.

        Args:
            relevant_papers: List of (paper, relevance) tuples

        Returns:
            List of (paper, relevance, translated_abstract) tuples
        """
        translated_papers = []

        for paper, relevance in relevant_papers:
            abstract = paper.summary
            translated_abstract = self.translator.translate_text(abstract)
            translated_papers.append((paper, relevance, translated_abstract))

        return translated_papers

    def _find_optimal_paper_count(
        self,
        translated_papers: list[tuple[Paper, Any, str]],
        research_topics: list[str],
    ) -> int:
        """
        Find optimal number of papers that fit within payload size limit using binary search.

        Args:
            translated_papers: List of (paper, relevance, translated_abstract) tuples
            research_topics: List of research topics

        Returns:
            Optimal number of papers that fit within size limit
        """
        if not translated_papers:
            return 0

        # Binary search for optimal count
        # ok: number of papers that fit within size limit
        # ng: number of papers that exceed size limit
        ok, ng = 0, len(translated_papers) + 1

        while abs(ok - ng) > 1:
            mid = (ok + ng) // 2
            card_content = self._generate_papers_card(
                translated_papers[:mid], research_topics, len(translated_papers)
            )

            # Convert to JSON and check size
            payload = {
                "type": "message",
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": card_content,
                    }
                ],
            }
            payload_size = len(json.dumps(payload).encode("utf-8"))

            if payload_size <= MAX_PAYLOAD_SIZE_BYTES:
                # This count fits
                ok = mid
                logger.debug(f"Paper count {mid} fits ({payload_size} bytes)")
            else:
                # Too large
                ng = mid
                logger.debug(f"Paper count {mid} too large ({payload_size} bytes)")

        logger.info(
            f"Optimal paper count: {ok} of {len(translated_papers)} "
            f"papers fit within {MAX_PAYLOAD_SIZE_BYTES} bytes limit"
        )
        return ok

    def send_error_notification(self, error_message: str) -> bool:
        """
        Send error notification to Teams.

        Args:
            error_message: Error message to include in notification

        Returns:
            True if notification sent successfully, False otherwise
        """
        card_content = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2",
            "body": [
                {
                    "type": "Container",
                    "style": "attention",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "⚠️ Report Papers Agent - Error",
                            "weight": "bolder",
                            "size": "large",
                            "wrap": True,
                        }
                    ],
                },
                {
                    "type": "TextBlock",
                    "text": "The paper collection agent encountered an error during its last run:",
                    "wrap": True,
                    "spacing": "medium",
                },
                {
                    "type": "TextBlock",
                    "text": error_message,
                    "wrap": True,
                    "fontType": "monospace",
                    "spacing": "small",
                },
                {
                    "type": "TextBlock",
                    "text": f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    "size": "small",
                    "color": "accent",
                    "spacing": "medium",
                },
            ],
        }

        try:
            return self._send_adaptive_card(card_content)
        except Exception as e:
            logger.error(f"Failed to send error notification to Teams: {e}")
            return False

    def _generate_papers_card(
        self,
        papers_with_translations: list[tuple[Paper, Any, str]],
        research_topics: list[str],
        total_papers: int | None = None,
    ) -> dict[str, Any]:
        """
        Generate Adaptive Card for paper notifications.

        Args:
            papers_with_translations: List of (paper, relevance, translated_abstract) tuples
            research_topics: List of research topics
            total_papers: Total number of papers (if different from shown count)

        Returns:
            Adaptive Card JSON structure
        """
        topics_str = ", ".join(research_topics)
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Determine header text
        if total_papers and total_papers > len(papers_with_translations):
            header_text = (
                f"{len(papers_with_translations)} of {total_papers} New Relevant Papers "
                f"(size limit reached)"
            )
        else:
            header_text = f"{len(papers_with_translations)} New Relevant Papers"

        # Build card body
        body: list[dict[str, Any]] = [
            {
                "type": "Container",
                "style": "emphasis",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": header_text,
                        "weight": "bolder",
                        "size": "large",
                        "wrap": True,
                    },
                    {
                        "type": "TextBlock",
                        "text": f"Research Topics: {topics_str}",
                        "wrap": True,
                        "spacing": "small",
                    },
                    {
                        "type": "TextBlock",
                        "text": f"Date: {date_str}",
                        "size": "small",
                        "color": "accent",
                        "spacing": "none",
                    },
                ],
            }
        ]

        # Add each paper as a container
        for paper, relevance, translated_abstract in papers_with_translations:
            # Format authors
            authors_str = ", ".join(paper.authors)

            # Determine relevance indicator
            score_emoji = "🟢" if relevance.relevance_score >= 0.8 else "🟡"

            paper_items: list[dict[str, Any]] = [
                {
                    "type": "TextBlock",
                    "text": f"{score_emoji} [{paper.title}]({paper.link})",
                    "weight": "bolder",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": f"**Authors:** {authors_str}",
                    "wrap": True,
                    "size": "small",
                    "spacing": "small",
                },
                {
                    "type": "TextBlock",
                    "text": translated_abstract,
                    "wrap": True,
                    "spacing": "small",
                },
                {
                    "type": "FactSet",
                    "facts": [
                        {
                            "title": "Relevance",
                            "value": f"{relevance.relevance_score:.1f}/1.0",
                        },
                        {
                            "title": "Published",
                            "value": paper.published.strftime("%Y-%m-%d"),
                        },
                        {
                            "title": "Topics",
                            "value": ", ".join(relevance.key_topics[:3]),
                        },
                    ],
                    "spacing": "small",
                },
            ]

            body.append(
                {
                    "type": "Container",
                    "separator": True,
                    "spacing": "medium",
                    "items": paper_items,
                }
            )

        # Add footer
        body.append(
            {
                "type": "TextBlock",
                "text": f"Generated by Report Papers AI Agent • {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                "size": "small",
                "color": "accent",
                "horizontalAlignment": "center",
                "spacing": "medium",
                "separator": True,
            }
        )

        return {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2",
            "body": body,
        }
