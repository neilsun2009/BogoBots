# BogoBots/crawlers/news_crawler.py
import json
import hashlib
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from BogoBots.database.session import get_session
from BogoBots.models.news_source import NewsSource
from BogoBots.models.news_item import NewsItem
from BogoBots.models.news_hub_config import NewsHubConfig


@dataclass
class RawNewsItem:
    """Raw news item data from source before processing"""
    external_id: str
    title: str
    url: str
    author: Optional[str]
    published_at: datetime
    content_raw: str
    image_urls: List[str]


class BaseNewsCrawler(ABC):
    """
    Base class for all news crawlers.
    Each adapter extends this for a specific source type.
    """
    
    source_type: str = None  # Override in subclass: rss, twitter, api, etc.
    
    def __init__(self, news_source: NewsSource, progress_callback=None):
        self.news_source = news_source
        self.config = self._load_config()
        self.session = get_session()
        self.progress_callback = progress_callback
        if self.source_type and self.news_source.source_type != self.source_type:
            raise ValueError(
                f"Crawler source_type mismatch: adapter={self.source_type}, source={self.news_source.source_type}"
            )

    def _emit_progress(self, message: str):
        if self.progress_callback:
            try:
                self.progress_callback(message)
            except Exception:
                pass
        print(message)
    
    def _load_config(self) -> Dict[str, Any]:
        """Load JSON config from news_source.config_json"""
        if self.news_source.config_json:
            return json.loads(self.news_source.config_json)
        return {}
    
    @abstractmethod
    def fetch_new_items(self, since: datetime) -> List[RawNewsItem]:
        """
        Fetch items newer than 'since' timestamp.
        Must be implemented by each adapter.
        """
        pass
    
    @abstractmethod
    def parse_content(self, raw_data: Any) -> str:
        """
        Convert raw content to markdown format.
        Must be implemented by each adapter.
        """
        pass

    def get_full_content(self, url: str) -> str:
        """
        Base hook for fetching full content from source URL.
        Adapters can override this (e.g. RSS uses r.jina.ai).
        """
        return ""
    
    def check_duplicate(self, external_id: str, title: str, published_at: datetime) -> bool:
        """
        Check if a news item already exists.
        Uses external_id if available, or title + published_at combination.
        """
        # Check by external_id if available
        if external_id:
            existing = self.session.query(NewsItem).filter_by(
                source_id=self.news_source.id,
                external_id=external_id
            ).first()
            if existing:
                return True
        
        # Check by title + published_at combination (within same source)
        if title and published_at:
            existing = self.session.query(NewsItem).filter_by(
                source_id=self.news_source.id,
                title=title,
                published_at=published_at
            ).first()
            if existing:
                return True
        
        return False
    
    def generate_external_id(self, item_data: Dict) -> str:
        """
        Generate an external_id from item data using MD5 hash.
        Used when source doesn't provide a unique ID.
        """
        content_str = json.dumps(item_data, sort_keys=True, default=str)
        return hashlib.md5(content_str.encode()).hexdigest()[:16]
    
    def save_item(self, raw_item: RawNewsItem, skip_summary: bool = False) -> Optional[NewsItem]:
        """
        Save a raw news item to the database.
        Optionally generate summary with LLM.
        """
        # Check for duplicates
        is_duplicate = self.check_duplicate(
            raw_item.external_id,
            raw_item.title,
            raw_item.published_at
        )
        if is_duplicate:
            return None
        
        # Create NewsItem
        item = NewsItem(
            source_id=self.news_source.id,
            external_id=raw_item.external_id,
            title=raw_item.title,
            url=raw_item.url,
            author=raw_item.author,
            published_at=raw_item.published_at,
            content_raw=raw_item.content_raw,
            image_urls=raw_item.image_urls if raw_item.image_urls else [],
            status='new',
            relevance_score=0.5,
            crawled_at=datetime.now(timezone.utc)
        )
        
        self.session.add(item)
        self.session.commit()

        if not skip_summary:
            try:
                from BogoBots.models.news_hub_config import NewsHubConfig
                from BogoBots.utils.llm_utils import summarize_news_item, extract_metadata
                cfg = NewsHubConfig.get_or_create(self.session)
                summary_model = cfg.default_summary_model
                self._emit_progress(f"LLM summarizing item #{item.id} ...")
                summarize_news_item(item.id, item.title, item.content_raw or "", model_name=summary_model)
                # self._emit_progress(f"LLM extracting metadata for item #{item.id} ...")
                # extract_metadata(item.id, item.title, item.content_raw or "", model_name=summary_model)
            except Exception as e:
                self._emit_progress(f"LLM processing skipped for item #{item.id}: {e}")
        
        return item
    
    def update_source_status(self, success: bool, error_message: str = None):
        """Update the news source's crawl status"""
        self._emit_progress(
            f"Updating source status for '{self.news_source.name}' at "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
        )

        # NewsSource passed from UI/service can be detached from this session.
        # Always load a session-bound row by id before writing status fields.
        source_row = self.session.query(NewsSource).filter_by(id=self.news_source.id).first()
        if not source_row:
            self._emit_progress(f"Source status update skipped: source_id={self.news_source.id} not found")
            return

        if success:
            source_row.last_crawled_at = datetime.now(timezone.utc)
            source_row.last_error = None
            self._emit_progress(f"Source '{self.news_source.name}' updated successfully")
        else:
            source_row.last_error = error_message
        
        self.session.commit()
    
    def crawl(self, since: datetime = None, skip_summary: bool = False) -> Dict:
        """
        Main crawl method. Fetches new items and saves them.
        
        Returns:
            Dict with crawl statistics
        """
        if since is None:
            # Default: look back 24 hours
            from datetime import timedelta
            since = datetime.now(timezone.utc) - timedelta(days=1)
        
        stats = {
            'source_name': self.news_source.name,
            'source_type': self.source_type,
            'fetched': 0,
            'saved': 0,
            'duplicates': 0,
            'errors': 0
        }
        
        try:
            self._emit_progress(f"Starting crawl for source '{self.news_source.name}'")
            # Fetch items from source
            raw_items = self.fetch_new_items(since)
            stats['fetched'] = len(raw_items)
            self._emit_progress(f"Fetched {stats['fetched']} candidate items")
            
            # Save each item
            for idx, raw_item in enumerate(raw_items, start=1):
                try:
                    self._emit_progress(f"[{idx}/{len(raw_items)}] Processing: {raw_item.title[:80]}")
                    result = self.save_item(raw_item, skip_summary=skip_summary)
                    if result:
                        stats['saved'] += 1
                        self._emit_progress(f"Saved item #{result.id}")
                    else:
                        stats['duplicates'] += 1
                        self._emit_progress("Skipped duplicate item")
                except Exception as e:
                    self._emit_progress(f"Error saving item '{raw_item.title[:60]}': {e}")
                    stats['errors'] += 1
            
            # Update source status
            self.update_source_status(success=True)
            self._emit_progress(
                f"Finished source '{self.news_source.name}': saved={stats['saved']}, dupes={stats['duplicates']}, errors={stats['errors']}"
            )
            
        except Exception as e:
            error_msg = str(e)
            self._emit_progress(f"Crawl error for {self.news_source.name}: {error_msg}")
            self.update_source_status(success=False, error_message=error_msg)
        
        finally:
            self.session.close()
        
        return stats

    def crawl_with_retry(
        self,
        since: datetime = None,
        skip_summary: bool = False,
        max_attempts: int = 3,
        retry_interval_seconds: int = 3,
    ) -> Dict:
        """
        Retry crawling for a source up to max_attempts with fixed interval.
        """
        last_stats = None
        for attempt in range(1, max_attempts + 1):
            self._emit_progress(f"Attempt {attempt}/{max_attempts} for source '{self.news_source.name}'")
            try:
                # ensure session is fresh per attempt
                self.session = get_session()
                stats = self.crawl(since=since, skip_summary=skip_summary)
                last_stats = stats
                if stats.get("errors", 0) == 0:
                    return stats
                self._emit_progress(f"Attempt {attempt} ended with errors: {stats.get('errors')}")
            except Exception as e:
                self._emit_progress(f"Attempt {attempt} failed: {e}")
            if attempt < max_attempts:
                time.sleep(retry_interval_seconds)
        return last_stats or {
            "source_name": self.news_source.name,
            "source_type": self.source_type,
            "fetched": 0,
            "saved": 0,
            "duplicates": 0,
            "errors": 1,
        }


def get_crawler_for_source(news_source: NewsSource, progress_callback=None) -> Optional[BaseNewsCrawler]:
    """
    Factory for source -> crawler adapter.
    Keeps UI/scripts decoupled from adapter concrete classes.
    """
    source_type = (news_source.source_type or "").lower()
    if source_type == "rss":
        from BogoBots.crawlers.adapters.rss_adapter import RSSAdapter
        return RSSAdapter(news_source, progress_callback=progress_callback)
    return None
