import re
from datetime import datetime, timezone
from typing import List, Optional

import feedparser
import requests

from BogoBots.crawlers.adapters.rss_adapter import RSSAdapter
from BogoBots.crawlers.news_crawler import RawNewsItem


class PodcastAdapter(RSSAdapter):
    """
    Adapter for podcast RSS feeds.
    Episodes are discovered through RSS, but content comes from podcast
    metadata/transcripts rather than Jina page extraction.
    """

    source_type = 'Podcast'

    def fetch_new_items(self, since: datetime) -> List[RawNewsItem]:
        items = []
        since_utc = self._normalize_to_utc(since) or datetime.now(timezone.utc)

        feed = feedparser.parse(self.news_source.url)
        self._emit_progress(f"Parsed primary podcast RSS '{self.news_source.name}', entries={len(feed.entries)}")
        if (not getattr(feed, "entries", None)) and getattr(self.news_source, "backup_url", None):
            self._emit_progress("Primary feed empty/unavailable, trying backup podcast RSS...")
            feed = feedparser.parse(self.news_source.backup_url)
            self._emit_progress(f"Parsed backup podcast RSS, entries={len(feed.entries)}")

        if feed.bozo and feed.bozo_exception:
            self._emit_progress(f"Podcast RSS parse warning for {self.news_source.name}: {feed.bozo_exception}")

        missing_pubdate_kept = 0
        missing_pubdate_limit = 10

        for entry in feed.entries:
            external_id = self._get_external_id(entry)
            published_at = self._normalize_to_utc(self._parse_date(entry))
            self._emit_progress(f"Published at: {published_at}")
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

            if external_id and self.check_duplicate(external_id=external_id, title=None, published_at=None):
                self._emit_progress(f"Skip duplicate by guid: {external_id}")
                continue

            if published_at < since_utc:
                continue

            link = entry.get('link', '')
            if not link:
                continue

            audio_url = self._extract_audio_url(entry)
            episode_description = self._extract_episode_description(entry)
            episode_duration_seconds = self._extract_duration_seconds(entry)
            transcript_url = self._extract_transcript_url(entry)
            content_raw = self._download_transcript(transcript_url) if transcript_url else ''

            author = self._extract_author(entry, feed)
            image_urls = self._extract_images(entry)

            item = RawNewsItem(
                external_id=external_id,
                title=entry.get('title', 'Untitled'),
                url=link,
                author=author,
                published_at=published_at,
                content_raw=content_raw,
                image_urls=image_urls,
                episode_description=episode_description,
                episode_duration_seconds=episode_duration_seconds,
                audio_url=audio_url,
            )
            items.append(item)
            self._emit_progress(f"Prepared podcast episode from feed: {item.title[:80]}")

        return items

    def get_full_content(self, url: str) -> str:
        """Podcasts do not use Jina markdown extraction."""
        return ""

    def _extract_audio_url(self, entry) -> str:
        for link in entry.get('links', []):
            if (
                link.get('rel') == 'enclosure'
                and link.get('type', '').startswith('audio/')
                and link.get('href')
            ):
                return link.get('href')

        for enclosure in entry.get('enclosures', []):
            if enclosure.get('type', '').startswith('audio/'):
                return enclosure.get('href') or enclosure.get('url') or ''

        for media in entry.get('media_content', []):
            if media.get('type', '').startswith('audio/'):
                return media.get('url') or ''

        return ''

    def _extract_episode_description(self, entry) -> str:
        html = entry.get('summary') or entry.get('description') or ''
        if not html and entry.get('content'):
            html = entry.content[0].get('value', '') if entry.content else ''

        return self._html_to_markdown(html)

    def _extract_duration_seconds(self, entry) -> Optional[int]:
        duration = (
            entry.get('itunes_duration')
            or entry.get('duration')
            or entry.get('itunes_duration_seconds')
        )
        if duration is None:
            return None

        if isinstance(duration, (int, float)):
            return int(duration)

        duration_text = str(duration).strip()
        if not duration_text:
            return None
        if duration_text.isdigit():
            return int(duration_text)

        parts = duration_text.split(':')
        if not all(part.isdigit() for part in parts):
            return None

        total = 0
        for part in parts:
            total = total * 60 + int(part)
        return total

    def _extract_transcript_url(self, entry) -> str:
        transcript_data = entry.get('podcast_transcript')
        transcripts = transcript_data if isinstance(transcript_data, list) else [transcript_data]
        transcripts = [transcript for transcript in transcripts if isinstance(transcript, dict)]

        if not transcripts:
            return ''

        for transcript in transcripts:
            if transcript.get('type') == 'text/plain' and transcript.get('url'):
                return transcript.get('url')

        for transcript in transcripts:
            if transcript.get('url'):
                return transcript.get('url')

        return ''

    def _download_transcript(self, transcript_url: str) -> str:
        try:
            self._emit_progress(f"Downloading official podcast transcript: {transcript_url}")
            response = requests.get(transcript_url, timeout=30)
            response.raise_for_status()
            text = response.text.strip()
            if self._looks_like_subtitle(text):
                return self._subtitle_to_text(text)
            return text
        except Exception as exc:
            self._emit_progress(f"Official transcript download failed: {exc}")
            return ''

    def _looks_like_subtitle(self, text: str) -> bool:
        return bool(re.search(r"\d{2}:\d{2}:\d{2}[,.]\d{3}\s+-->\s+", text))

    def _subtitle_to_text(self, text: str) -> str:
        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.isdigit() or "-->" in stripped or stripped.upper() == "WEBVTT":
                continue
            lines.append(stripped)
        return "\n".join(lines)
