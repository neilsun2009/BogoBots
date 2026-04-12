# BogoBots/crawlers/adapters/__init__.py
from BogoBots.crawlers.adapters.rss_adapter import RSSAdapter
from BogoBots.crawlers.adapters.arxiv_adapter import ArXivAdapter
from BogoBots.crawlers.adapters.twitter_adapter import TwitterAdapter
from BogoBots.crawlers.adapters.github_adapter import GitHubAdapter
from BogoBots.crawlers.adapters.api_adapter import APIAdapter

__all__ = [
    'RSSAdapter',
    'ArXivAdapter',
    'TwitterAdapter',
    'GitHubAdapter',
    'APIAdapter',
]
