"""SES-based email notification system for paper alerts."""

from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from .logger import get_logger

logger = get_logger(__name__)


class EmailNotifier:
    """SES-based email notification system with translation support."""

    def __init__(
        self,
        sender_email: str,
        recipient_email: str,
        region: str = "us-east-1",
        target_language: str = "ja",
    ):
        self.sender_email = sender_email
        self.recipient_email = recipient_email
        self.target_language = target_language
        self.ses_client = boto3.client("ses", region_name=region)
        self.translate_client = boto3.client("translate", region_name=region)

    def _translate_text(self, text: str) -> str:
        """
        Translate text to the target language using Amazon Translate.

        Args:
            text: Text to translate

        Returns:
            Translated text in target language, or original text if translation fails or target is 'en'
        """
        if not text or not text.strip():
            return text

        # Skip translation if target language is English
        if self.target_language == "en":
            return text

        try:
            response = self.translate_client.translate_text(
                Text=text, SourceLanguageCode="en", TargetLanguageCode=self.target_language
            )
            translated_text = response["TranslatedText"]
            logger.info(
                f"Successfully translated text to {self.target_language}: {len(text)} chars -> {len(translated_text)} chars"
            )
            return str(translated_text)

        except Exception as e:
            logger.warning(f"Failed to translate text to {self.target_language}: {e}")
            return text  # Return original text if translation fails

    def send_paper_notification(
        self, relevant_papers: list[tuple[dict[str, Any], Any]], research_topics: list[str]
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
            # Generate email content
            subject = self._generate_subject(len(relevant_papers), research_topics)
            html_body = self._generate_html_body(relevant_papers, research_topics)
            text_body = self._generate_text_body(relevant_papers, research_topics)

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

        return f"📚 {num_papers} New Relevant Papers - {topics_str}"

    def _generate_html_body(
        self, relevant_papers: list[tuple[dict[str, Any], Any]], research_topics: list[str]
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
                <p>Found {len(relevant_papers)} relevant papers from ArXiv:</p>
        """

        for paper, relevance in relevant_papers:
            # Determine score class
            score_class = "score-high" if relevance.relevance_score >= 0.8 else "score-medium"

            # Format authors
            authors_str = ", ".join(paper.get("authors", [])[:3])
            if len(paper.get("authors", [])) > 3:
                authors_str += f" (+{len(paper['authors']) - 3} more)"

            # Format categories
            categories_str = ", ".join(paper.get("categories", []))

            # Translate summary to target language
            translated_summary = self._translate_text(relevance.summary)

            html += f"""
                <div class="paper">
                    <div class="paper-title">
                        <a href="{paper.get("link", "#")}" style="color: #1976d2; text-decoration: none;">
                            {paper.get("title", "Untitled")}
                        </a>
                    </div>
                    <div class="paper-authors">{authors_str}</div>
                    <div class="paper-summary">{translated_summary}</div>
                    <div class="paper-meta">
                        <span class="relevance-score {score_class}">
                            Relevance: {relevance.relevance_score:.1f}/1.0
                        </span>
                        | Categories: {categories_str}
                        | Published: {paper.get("published", "Unknown")[:10]}
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
        self, relevant_papers: list[tuple[dict[str, Any], Any]], research_topics: list[str]
    ) -> str:
        """Generate plain text email body."""
        topics_str = ", ".join(research_topics)
        date_str = datetime.now().strftime("%Y-%m-%d")

        text = f"""
NEW RELEVANT PAPERS - {date_str}

Research Topics: {topics_str}
Found {len(relevant_papers)} relevant papers from ArXiv:

========================================
"""

        for i, (paper, relevance) in enumerate(relevant_papers, 1):
            authors_str = ", ".join(paper.get("authors", [])[:3])
            if len(paper.get("authors", [])) > 3:
                authors_str += f" (+{len(paper['authors']) - 3} more)"

            # Translate summary to target language
            translated_summary = self._translate_text(relevance.summary)

            text += f"""
{i}. {paper.get("title", "Untitled")}

Authors: {authors_str}
Relevance Score: {relevance.relevance_score:.1f}/1.0
Key Topics: {", ".join(relevance.key_topics[:3])}

Summary: {translated_summary}

ArXiv Link: {paper.get("link", "N/A")}
Published: {paper.get("published", "Unknown")[:10]}
Categories: {", ".join(paper.get("categories", []))}

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
