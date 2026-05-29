"""ArXiv API client for paper search and retrieval."""

import time
from datetime import datetime, timedelta, date
from typing import Any

import feedparser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .interface import Paper
from .logger import get_logger

logger = get_logger(__name__)

# ArXiv API Terms of Use require no more than one request every 3 seconds.
# https://info.arxiv.org/help/api/tou.html
# We sleep longer than the minimum to stay friendly with ArXiv after observing
# bursts of 429/503/timeout responses against AWS egress IPs.
ARXIV_REQUEST_INTERVAL_SECONDS = 15.0

# After a topic exhausts the inner urllib3 retries we wait this long before
# trying that topic one more time, giving ArXiv room to recover from a
# transient 429/503/timeout.
ARXIV_TOPIC_FAILURE_COOLDOWN_SECONDS = 60.0


def parse_arxiv_entry(entry: dict[str, Any]) -> Paper:
    """Parse ArXiv API entry into Paper instance."""
    return Paper(
        id=entry.get("id", "").split("/")[-1],
        title=entry.get("title", "").strip(),
        summary=entry.get("summary", "").strip().replace("\n", " "),
        authors=[author.get("name", "") for author in entry.get("authors", [])],
        published=entry.get("published", ""),
        updated=entry.get("updated", ""),
        link=entry.get("link", ""),
        categories=[tag.get("term", "") for tag in entry.get("tags", [])],
    )


class ArxivClient:
    """Client for interacting with ArXiv API."""

    BASE_URL = "http://export.arxiv.org/api/query"
    REQUEST_TIMEOUT_SECONDS = 60

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "notify-papers/1.0 (+https://github.com/privet-kitty/notify-papers)"}
        )
        # Retry transient failures (read timeouts, 5xx, 429). backoff_factor=3
        # yields waits of 3s, 6s, 12s — keeping per-request spacing above ArXiv's
        # 3s rate limit even under retry. urllib3 honors the Retry-After header
        # for 429/503 automatically.
        retry = Retry(
            total=3,
            backoff_factor=3,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def search_papers(
        self,
        query: str,
        max_results: int,
        days_back: int,
        categories: list[str],
        end_date: date | None = None,
    ) -> list[Paper]:
        """
        Search for papers on ArXiv.

        Args:
            query: Search query terms
            max_results: Maximum number of results to return
            days_back: Number of days to look back from end_date
            categories: List of ArXiv categories to filter by
            end_date: End date for search period (defaults to today)

        Returns:
            list of ArxivPaper objects
        """
        # Build search query
        search_query = self._build_search_query(query, days_back, categories, end_date)

        params = {
            "search_query": search_query,
            "start": str(0),
            "max_results": str(max_results),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        logger.info(f"Searching ArXiv with query: {search_query}")

        try:
            response = self.session.get(
                self.BASE_URL, params=params, timeout=self.REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()

            # Parse the Atom feed
            feed = feedparser.parse(response.text)

            if feed.bozo:
                logger.warning("Feed parsing had issues, but continuing...")

            papers = []
            for entry in feed.entries:
                try:
                    paper = parse_arxiv_entry(entry)
                    papers.append(paper)
                except Exception as e:
                    logger.error(f"Error parsing paper entry: {e}")
                    continue

            logger.info(f"Found {len(papers)} papers")
            return papers

        except requests.RequestException as e:
            logger.error(f"Error fetching from ArXiv API: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in ArXiv search: {e}")
            raise

    def _build_search_query(
        self, query: str, days_back: int, categories: list[str], end_date: date | None = None
    ) -> str:
        """Build ArXiv search query string."""
        # Date range
        if end_date is None:
            end_date_dt = datetime.now()
        else:
            end_date_dt = datetime.combine(end_date, datetime.min.time())
        start_date = end_date_dt - timedelta(days=days_back)

        date_range = (
            f"[{start_date.strftime('%Y%m%d0000')} TO {end_date_dt.strftime('%Y%m%d2359')}]"
        )

        # Base query with date filter
        query_parts = [f"({query})", f"submittedDate:{date_range}"]

        # Add category filter if specified
        category_query = " OR ".join([f"cat:{cat}" for cat in categories])
        query_parts.append(f"({category_query})")

        return " AND ".join(query_parts)

    def search_multiple_topics(
        self,
        topics: list[str],
        max_results_per_topic: int,
        days_back: int,
        categories: list[str],
        end_date: date | None = None,
    ) -> list[Paper]:
        """
        Search for papers across multiple topics and deduplicate.

        Args:
            topics: List of search topics
            max_results_per_topic: Max results per topic
            days_back: Number of days to look back from end_date
            categories: List of ArXiv categories to filter by
            end_date: End date for search period (defaults to today)

        Returns:
            Deduplicated list of Paper objects
        """
        papers_dict: dict[str, Paper] = {}
        failed_topics: list[str] = []

        for index, topic in enumerate(topics):
            if index > 0:
                # ArXiv Terms of Use: at most one request every 3 seconds.
                time.sleep(ARXIV_REQUEST_INTERVAL_SECONDS)

            try:
                papers = self.search_papers(
                    query=topic,
                    max_results=max_results_per_topic,
                    days_back=days_back,
                    categories=categories,
                    end_date=end_date,
                )
            except requests.RequestException as e:
                # Inner urllib3 Retry already burned its 3 attempts (3s/6s/12s
                # backoff). Wait longer and try this topic once more before
                # giving up, since ArXiv 429/503/timeout bursts often clear
                # within a minute.
                logger.warning(
                    f"Topic '{topic}' failed after inner retries: {e}. "
                    f"Sleeping {ARXIV_TOPIC_FAILURE_COOLDOWN_SECONDS}s and retrying once."
                )
                time.sleep(ARXIV_TOPIC_FAILURE_COOLDOWN_SECONDS)
                try:
                    papers = self.search_papers(
                        query=topic,
                        max_results=max_results_per_topic,
                        days_back=days_back,
                        categories=categories,
                        end_date=end_date,
                    )
                except requests.RequestException as retry_err:
                    logger.error(
                        f"Topic '{topic}' failed again after cooldown: {retry_err}. "
                        "Skipping this topic; remaining topics will still be processed."
                    )
                    failed_topics.append(topic)
                    continue

            # Use dict for automatic deduplication by paper ID
            for paper in papers:
                papers_dict[paper.id] = paper

        if failed_topics and len(failed_topics) == len(topics):
            raise RuntimeError(f"All ArXiv topic searches failed: {failed_topics}")
        if failed_topics:
            logger.warning(
                f"Partial ArXiv failure: {len(failed_topics)}/{len(topics)} "
                f"topic(s) failed and were skipped: {failed_topics}"
            )

        # Sort by publication date (newest first)
        all_papers = sorted(papers_dict.values(), key=lambda p: p.published, reverse=True)

        succeeded = len(topics) - len(failed_topics)
        logger.info(
            f"Found {len(all_papers)} unique papers across {succeeded}/{len(topics)} topics"
        )
        return all_papers
