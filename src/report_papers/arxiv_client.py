"""ArXiv API client for paper search and retrieval."""

import feedparser
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import quote

from .logger import get_logger

logger = get_logger(__name__)


class ArxivPaper:
    """Represents a paper from ArXiv."""
    
    def __init__(self, entry: Dict[str, Any]):
        self.id = entry.get('id', '').split('/')[-1]
        self.title = entry.get('title', '').strip()
        self.summary = entry.get('summary', '').strip().replace('\n', ' ')
        self.authors = [author.get('name', '') for author in entry.get('authors', [])]
        self.published = entry.get('published', '')
        self.updated = entry.get('updated', '')
        self.link = entry.get('link', '')
        self.categories = [tag.get('term', '') for tag in entry.get('tags', [])]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert paper to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'summary': self.summary,
            'authors': self.authors,
            'published': self.published,
            'updated': self.updated,
            'link': self.link,
            'categories': self.categories
        }


class ArxivClient:
    """Client for interacting with ArXiv API."""
    
    BASE_URL = "http://export.arxiv.org/api/query"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'report-papers/1.0 (https://github.com/user/report-papers)'
        })
    
    def search_papers(
        self, 
        query: str, 
        max_results: int = 50,
        days_back: int = 7,
        categories: Optional[List[str]] = None
    ) -> List[ArxivPaper]:
        """
        Search for papers on ArXiv.
        
        Args:
            query: Search query terms
            max_results: Maximum number of results to return
            days_back: Number of days to look back from today
            categories: List of ArXiv categories to filter by
            
        Returns:
            List of ArxivPaper objects
        """
        # Build search query
        search_query = self._build_search_query(query, days_back, categories)
        
        params = {
            'search_query': search_query,
            'start': 0,
            'max_results': max_results,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending'
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
                    paper = ArxivPaper(entry)
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
        self, 
        query: str, 
        days_back: int, 
        categories: Optional[List[str]] = None
    ) -> str:
        """Build ArXiv search query string."""
        # Date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        date_range = f"[{start_date.strftime('%Y%m%d')}* TO {end_date.strftime('%Y%m%d')}*]"
        
        # Base query with date filter
        query_parts = [
            f"({query})",
            f"submittedDate:{date_range}"
        ]
        
        # Add category filter if specified
        if categories:
            category_query = " OR ".join([f"cat:{cat}" for cat in categories])
            query_parts.append(f"({category_query})")
        
        # Common categories for energy/electricity market research
        default_categories = ["econ.GN", "physics.soc-ph", "cs.CE", "math.OC"]
        if not categories:
            category_query = " OR ".join([f"cat:{cat}" for cat in default_categories])
            query_parts.append(f"({category_query})")
        
        return " AND ".join(query_parts)
    
    def search_multiple_topics(
        self, 
        topics: List[str], 
        max_results_per_topic: int = 20,
        days_back: int = 7
    ) -> List[ArxivPaper]:
        """
        Search for papers across multiple topics and deduplicate.
        
        Args:
            topics: List of search topics
            max_results_per_topic: Max results per topic
            days_back: Number of days to look back
            
        Returns:
            Deduplicated list of ArxivPaper objects
        """
        all_papers = []
        seen_ids = set()
        
        for topic in topics:
            try:
                papers = self.search_papers(
                    query=topic,
                    max_results=max_results_per_topic,
                    days_back=days_back
                )
                
                # Deduplicate based on paper ID
                for paper in papers:
                    if paper.id not in seen_ids:
                        all_papers.append(paper)
                        seen_ids.add(paper.id)
                        
            except Exception as e:
                logger.error(f"Error searching for topic '{topic}': {e}")
                continue
        
        # Sort by publication date (newest first)
        all_papers.sort(key=lambda p: p.published, reverse=True)
        
        logger.info(f"Found {len(all_papers)} unique papers across {len(topics)} topics")
        return all_papers