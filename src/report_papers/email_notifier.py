"""SES-based email notification system for paper alerts."""

import os
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from .interface import Paper
from .logger import get_logger
from .translator import Translator

logger = get_logger(__name__)


class EmailNotifier:
    """SES-based email notification system with translation support."""

    def __init__(self, sender_email: str, recipient_email: str, region: str, translator: Translator):
        self.sender_email = sender_email
        self.recipient_email = recipient_email
        self.translator = translator

        ses_endpoint = os.getenv("SES_ENDPOINT")

        self.ses_client = boto3.client("ses", region_name=region, endpoint_url=ses_endpoint)

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

    def send_paper_notification(
        self, relevant_papers: list[tuple[Paper, Any]], research_topics: list[str]
    ) -> bool:
        """
        Send email notification with relevant papers.

        Args:
            relevant_papers: List of (paper, relevance) tuples
            research_topics: List of research topics

        Returns:
            True if email sent successfully, False otherwise
        """
        if not relevant_papers:
            logger.info("No relevant papers to send")
            return True

        try:
            # Translate all abstracts once before generating email content
            papers_with_translated_abstracts = self._prepare_translated_papers(relevant_papers)

            # Generate email content
            subject = self._generate_subject(len(relevant_papers), research_topics)
            html_body = self._generate_html_body(papers_with_translated_abstracts, research_topics)
            text_body = self._generate_text_body(papers_with_translated_abstracts, research_topics)

            # Send email via SES
            response = self.ses_client.send_email(
                Source=self.sender_email,
                Destination={"ToAddresses": [self.recipient_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": text_body, "Charset": "UTF-8"},
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                    },
                },
            )

            logger.info(f"Email sent successfully. MessageId: {response['MessageId']}")
            return True

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"SES ClientError: {error_code} - {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False

    def send_error_notification(self, error_message: str) -> bool:
        """
        Send error notification email.

        Args:
            error_message: Error message to include in email

        Returns:
            True if email sent successfully, False otherwise
        """
        subject = "Report Papers Agent - Error Notification"

        html_body = f"""
        <html>
        <head></head>
        <body>
            <h2>Report Papers Agent - Error</h2>
            <p>The paper collection agent encountered an error during its last run:</p>
            <div style="background-color: #f8f8f8; padding: 10px; border-left: 4px solid #d32f2f;">
                <pre>{error_message}</pre>
            </div>
            <p>Please check the CloudWatch logs for more details.</p>
            <p><em>Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}</em></p>
        </body>
        </html>
        """

        text_body = f"""
Report Papers Agent - Error

The paper collection agent encountered an error during its last run:

{error_message}

Please check the CloudWatch logs for more details.

Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}
        """

        try:
            response = self.ses_client.send_email(
                Source=self.sender_email,
                Destination={"ToAddresses": [self.recipient_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": text_body, "Charset": "UTF-8"},
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                    },
                },
            )

            logger.info(f"Error notification sent. MessageId: {response['MessageId']}")
            return True

        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")
            return False

    def _generate_subject(self, num_papers: int, research_topics: list[str]) -> str:
        """Generate email subject line."""
        topics_str = ", ".join(research_topics[:2])
        if len(research_topics) > 2:
            topics_str += f" (+{len(research_topics) - 2} more)"

        return f"Daily Paper News: {num_papers} New Papers - {topics_str}"

    def _generate_html_body(
        self,
        papers_with_translations: list[tuple[Paper, Any, str]],
        research_topics: list[str],
    ) -> str:
        """Generate HTML email body."""
        topics_str = ", ".join(research_topics)
        date_str = datetime.now().strftime("%Y-%m-%d")

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #1976d2; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .paper {{ margin-bottom: 30px; border-left: 4px solid #1976d2; padding-left: 15px; }}
                .paper-title {{ font-size: 18px; font-weight: bold; color: #1976d2; margin-bottom: 8px; }}
                .paper-authors {{ color: #666; margin-bottom: 8px; }}
                .paper-summary {{ margin-bottom: 10px; }}
                .paper-meta {{ font-size: 12px; color: #888; }}
                .relevance-score {{ 
                    display: inline-block; 
                    padding: 4px 8px; 
                    border-radius: 4px; 
                    font-weight: bold; 
                    font-size: 12px; 
                }}
                .score-high {{ background-color: #4caf50; color: white; }}
                .score-medium {{ background-color: #ff9800; color: white; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📚 New Relevant Papers</h1>
                <p>Research Topics: {topics_str}</p>
                <p>Date: {date_str}</p>
            </div>
            
            <div class="content">
                <p>Found {len(papers_with_translations)} relevant papers from ArXiv:</p>
        """

        for paper, relevance, translated_abstract in papers_with_translations:
            # Determine score class
            score_class = "score-high" if relevance.relevance_score >= 0.8 else "score-medium"

            # Format authors
            authors_str = ", ".join(paper.authors[:3])
            if len(paper.authors) > 3:
                authors_str += f" (+{len(paper.authors) - 3} more)"

            # Format categories
            categories_str = ", ".join(paper.categories)

            html += f"""
                <div class="paper">
                    <div class="paper-title">
                        <a href="{paper.link}" style="color: #1976d2; text-decoration: none;">
                            {paper.title}
                        </a>
                    </div>
                    <div class="paper-authors">{authors_str}</div>
                    <div class="paper-summary">{translated_abstract}</div>
                    <div class="paper-meta">
                        <span class="relevance-score {score_class}">
                            Relevance: {relevance.relevance_score:.1f}/1.0
                        </span>
                        | Categories: {categories_str}
                        | Published: {paper.published.strftime("%Y-%m-%d")}
                        | Topics: {", ".join(relevance.key_topics[:3])}
                    </div>
                </div>
            """

        html += f"""
            </div>
            
            <div class="footer">
                <p>Generated by Report Papers AI Agent</p>
                <p><em>{datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}</em></p>
            </div>
        </body>
        </html>
        """

        return html

    def _generate_text_body(
        self,
        papers_with_translations: list[tuple[Paper, Any, str]],
        research_topics: list[str],
    ) -> str:
        """Generate plain text email body."""
        topics_str = ", ".join(research_topics)
        date_str = datetime.now().strftime("%Y-%m-%d")

        text = f"""
NEW RELEVANT PAPERS - {date_str}

Research Topics: {topics_str}
Found {len(papers_with_translations)} relevant papers from ArXiv:

========================================
"""

        for i, (paper, relevance, translated_abstract) in enumerate(papers_with_translations, 1):
            authors_str = ", ".join(paper.authors[:3])
            if len(paper.authors) > 3:
                authors_str += f" (+{len(paper.authors) - 3} more)"

            text += f"""
{i}. {paper.title}

Authors: {authors_str}
Relevance Score: {relevance.relevance_score:.1f}/1.0
Key Topics: {", ".join(relevance.key_topics[:3])}

Summary: {translated_abstract}

ArXiv Link: {paper.link}
Published: {paper.published.strftime("%Y-%m-%d")}
Categories: {", ".join(paper.categories)}

----------------------------------------
"""

        text += f"""

Generated by Report Papers AI Agent
{datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}
        """

        return text.strip()

    def test_email_configuration(self) -> bool:
        """
        Test email configuration by sending a test email.

        Returns:
            True if test email sent successfully, False otherwise
        """
        subject = "Report Papers Agent - Test Email"

        html_body = """
        <html>
        <body>
            <h2>Test Email from Report Papers Agent</h2>
            <p>This is a test email to verify that the SES configuration is working correctly.</p>
            <p>If you received this email, the setup is successful! 🎉</p>
        </body>
        </html>
        """

        text_body = """
Test Email from Report Papers Agent

This is a test email to verify that the SES configuration is working correctly.

If you received this email, the setup is successful!
        """

        try:
            response = self.ses_client.send_email(
                Source=self.sender_email,
                Destination={"ToAddresses": [self.recipient_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": text_body, "Charset": "UTF-8"},
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                    },
                },
            )

            logger.info(f"Test email sent successfully. MessageId: {response['MessageId']}")
            return True

        except Exception as e:
            logger.error(f"Failed to send test email: {e}")
            return False
