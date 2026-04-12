# BogoBots/crawlers/adapters/rss_adapter.py
import feedparser
import requests
from datetime import datetime, timezone
from typing import List, Optional
import time
from bs4 import BeautifulSoup

from BogoBots.crawlers.news_crawler import BaseNewsCrawler, RawNewsItem


class RSSAdapter(BaseNewsCrawler):
    """
    Adapter for RSS/Atom feeds.
    Used for blogs, news sites with RSS feeds.
    """
    
    source_type = 'RSS'
    
    def fetch_new_items(self, since: datetime) -> List[RawNewsItem]:
        """
        Fetch items from RSS feed published after 'since' timestamp.
        """
        items = []
        
        # Parse primary RSS feed, fallback to backup when needed
        feed = feedparser.parse(self.news_source.url)
        self._emit_progress(f"Parsed primary RSS '{self.news_source.name}', entries={len(feed.entries)}")
        if (not getattr(feed, "entries", None)) and getattr(self.news_source, "backup_url", None):
            self._emit_progress("Primary feed empty/unavailable, trying backup RSS...")
            feed = feedparser.parse(self.news_source.backup_url)
            self._emit_progress(f"Parsed backup RSS, entries={len(feed.entries)}")
        
        if feed.bozo and feed.bozo_exception:
            print(f"RSS parse warning for {self.news_source.name}: {feed.bozo_exception}")
        
        missing_pubdate_kept = 0
        missing_pubdate_limit = 10

        for entry in feed.entries:
            # Get external ID (guid/id/link priority)
            external_id = self._get_external_id(entry)

            # Parse published date
            published_at = self._parse_date(entry)
            if not published_at:
                if missing_pubdate_kept < missing_pubdate_limit:
                    published_at = datetime.now(timezone.utc)
                    missing_pubdate_kept += 1
                    self._emit_progress(
                        f"Missing pubDate -> keep as today ({missing_pubdate_kept}/{missing_pubdate_limit})"
                    )
                else:
                    self._emit_progress("Missing pubDate -> skipped (limit reached)")
                    continue
            
            # Fast duplicate check by guid/external id BEFORE fetching full content via jina
            if external_id and self.check_duplicate(external_id=external_id, title=None, published_at=None):
                self._emit_progress(f"Skip duplicate by guid: {external_id}")
                continue

            
            # Skip if older than 'since'
            if published_at < since:
                continue
            
            # Use only structured RSS fields and fetch markdown from r.jina.ai
            link = entry.get('link', '')
            if not link:
                continue

            content = self._extract_content_via_jina(link)
            
            # Get author
            author = self._extract_author(entry, feed)
            
            # Get images
            image_urls = self._extract_images(entry)
            
            # Create RawNewsItem
            item = RawNewsItem(
                external_id=external_id,
                title=entry.get('title', 'Untitled'),
                url=link,
                author=author,
                published_at=published_at,
                content_raw=content,
                image_urls=image_urls
            )
            items.append(item)
            self._emit_progress(f"Prepared item from feed: {item.title[:80]}")
        
        return items
    
    def parse_content(self, raw_data) -> str:
        """
        RSS content is already parsed, return as-is.
        For additional processing, this could convert HTML to markdown.
        """
        return str(raw_data)
    
    def _parse_date(self, entry) -> Optional[datetime]:
        """Extract and parse published date from entry (pubDate/published_parsed preferred)."""
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            parsed = entry.published_parsed
            if isinstance(parsed, tuple):
                return datetime(*parsed[:6])

        # fallback for feeds that expose pubDate as text
        for field in ['published', 'pubDate']:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    from dateutil import parser as date_parser
                    return date_parser.parse(getattr(entry, field))
                except:
                    pass
        
        return None
    
    def _get_external_id(self, entry) -> str:
        """Get unique ID from entry or generate one"""
        # Prefer guid/id/link exactly as user requested
        id_fields = ['guid', 'id', 'link']
        for field in id_fields:
            if hasattr(entry, field) and getattr(entry, field):
                return str(getattr(entry, field))
        
        # Generate from title + published
        title = entry.get('title', '')
        published = entry.get('published', '')
        return self.generate_external_id({'title': title, 'published': published})
    
    def _extract_content_via_jina(self, url: str) -> str:
        """
        Extract page content as markdown via r.jina.ai.
        Waits 3 seconds per item to respect rate limits.
        """
        if not url:
            return ''

        try:
            jina_url = f"https://r.jina.ai/{url}"
            headers = {}
            response = requests.get(jina_url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception:
            # graceful fallback: minimal markdown with URL only
            return f"# Source\n\nOriginal URL: {url}\n\nFailed to extract markdown from r.jina.ai."
        finally:
            # explicit wait requested for rate limit
            time.sleep(3)

    def get_full_content(self, url: str) -> str:
        """
        Adapter implementation of base get_full_content.
        """
        return self._extract_content_via_jina(url)
    
    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML to simple markdown"""
        if not html:
            return ''
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup(['script', 'style']):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
    
    def _extract_author(self, entry, feed) -> Optional[str]:
        """Extract author name from entry or feed"""
        # Try entry author
        if hasattr(entry, 'author'):
            return entry.author
        
        if hasattr(entry, 'authors') and entry.authors:
            return entry.authors[0].get('name', '')
        
        # Try feed author
        if hasattr(feed, 'author'):
            return feed.author
        
        if hasattr(feed, 'authors') and feed.authors:
            return feed.authors[0].get('name', '')
        
        return None
    
    def _extract_images(self, entry) -> List[str]:
        """Extract image URLs from entry"""
        images = []
        
        # Try enclosures
        if hasattr(entry, 'enclosures'):
            for enclosure in entry.enclosures:
                if enclosure.get('type', '').startswith('image/'):
                    url = enclosure.get('href', enclosure.get('url', ''))
                    if url:
                        images.append(url)
        
        # Try media content
        if hasattr(entry, 'media_content'):
            for media in entry.media_content:
                if media.get('type', '').startswith('image/'):
                    url = media.get('url', '')
                    if url:
                        images.append(url)
        
        # Try content for image URLs
        content = ''
        if hasattr(entry, 'content'):
            content = entry.content[0].get('value', '') if entry.content else ''
        elif hasattr(entry, 'summary'):
            content = entry.summary
        
        if content:
            soup = BeautifulSoup(content, 'html.parser')
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if src and src not in images:
                    images.append(src)
        
        return images[:5]  # Limit to 5 images
