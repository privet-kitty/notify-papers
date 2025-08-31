"""ArXiv API client for paper search and retrieval."""

from datetime import datetime, timedelta, date
from typing import Any

import feedparser
import requests

from .interface import Paper
from .logger import get_logger

logger = get_logger(__name__)


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

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "report-papers/1.0 (https://github.com/user/report-papers)"}
        )

    def search_papers(
        self, query: str, max_results: int, days_back: int, categories: list[str], end_date: date | None = None
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
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
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

    def _build_search_query(self, query: str, days_back: int, categories: list[str], end_date: date | None = None) -> str:
        """Build ArXiv search query string."""
        # Date range
        if end_date is None:
            end_date_dt = datetime.now()
        else:
            end_date_dt = datetime.combine(end_date, datetime.min.time())
        start_date = end_date_dt - timedelta(days=days_back)

        date_range = f"[{start_date.strftime('%Y%m%d')}* TO {end_date_dt.strftime('%Y%m%d')}*]"

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

        for topic in topics:
            try:
                papers = self.search_papers(
                    query=topic,
                    max_results=max_results_per_topic,
                    days_back=days_back,
                    categories=categories,
                    end_date=end_date,
                )

                # Use dict for automatic deduplication by paper ID
                for paper in papers:
                    papers_dict[paper.id] = paper

            except Exception as e:
                logger.error(f"Error searching for topic '{topic}': {e}")
                continue

        # Sort by publication date (newest first)
        all_papers = sorted(papers_dict.values(), key=lambda p: p.published, reverse=True)

        logger.info(f"Found {len(all_papers)} unique papers across {len(topics)} topics")
        return all_papers
