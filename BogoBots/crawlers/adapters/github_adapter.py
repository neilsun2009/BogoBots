# BogoBots/crawlers/adapters/github_adapter.py
import requests
from datetime import datetime
from typing import List, Optional

from BogoBots.crawlers.news_crawler import BaseNewsCrawler, RawNewsItem


class GitHubAdapter(BaseNewsCrawler):
    """
    Adapter for GitHub API.
    Tracks trending repositories and framework updates (NOT model releases).
    
    Config options:
    - api_token: GitHub personal access token (increases rate limit)
    - languages: List of languages to track (e.g., ['python', 'javascript'])
    - topics: List of topics to filter (e.g., ['machine-learning', 'nlp'])
    - min_stars: Minimum star count to include
    - excluded_topics: Topics to exclude (e.g., ['model', 'checkpoint'])
    """
    
    source_type = 'github'
    
    GITHUB_API_BASE = 'https://api.github.com'
    
    def _get_headers(self) -> dict:
        """Get request headers with auth if available"""
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'BogoBots-AIHub'
        }
        
        token = self.config.get('api_token')
        if token:
            headers['Authorization'] = f'token {token}'
        
        return headers
    
    def fetch_new_items(self, since: datetime) -> List[RawNewsItem]:
        """
        Fetch trending/updated repos from GitHub.
        """
        items = []
        
        languages = self.config.get('languages', ['python'])
        topics = self.config.get('topics', ['machine-learning', 'ai', 'nlp'])
        min_stars = self.config.get('min_stars', 100)
        excluded_topics = self.config.get('excluded_topics', ['model', 'checkpoint', 'weights'])
        max_results = self.config.get('max_results', 30)
        
        headers = self._get_headers()
        
        # Build search query
        # Look for repos created/updated recently with relevant topics
        date_filter = since.strftime('%Y-%m-%d')
        
        # Query for recently created repos with ML topics
        query_parts = [
            f'created:>{date_filter}',
            f'stars:>{min_stars}'
        ]
        
        if topics:
            topic_query = ' '.join([f'topic:{t}' for t in topics[:3]])
            query_parts.append(topic_query)
        
        query = ' '.join(query_parts)
        
        try:
            # Search repositories
            search_url = f'{self.GITHUB_API_BASE}/search/repositories'
            params = {
                'q': query,
                'sort': 'stars',
                'order': 'desc',
                'per_page': max_results
            }
            
            response = requests.get(search_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            for repo in data.get('items', []):
                # Check for excluded topics
                repo_topics = repo.get('topics', [])
                if any(t in repo_topics for t in excluded_topics):
                    continue
                
                # Check language filter
                language = repo.get('language', '')
                if languages and language and language.lower() not in [l.lower() for l in languages]:
                    continue
                
                # Build content
                repo_name = repo.get('full_name', '')
                description = repo.get('description', '')
                stars = repo.get('stargazers_count', 0)
                forks = repo.get('forks_count', 0)
                url = repo.get('html_url', '')
                created_at = repo.get('created_at', '')
                owner = repo.get('owner', {}).get('login', '')
                
                # Parse date
                try:
                    published_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except:
                    published_at = since
                
                # Skip if too old
                if published_at < since:
                    continue
                
                # Build markdown content
                topics_str = ', '.join([f'`{t}`' for t in repo_topics[:5]])
                
                md_content = f"""# {repo_name}

**{owner}** created a new repository

## Description
{description or 'No description provided'}

## Stats
- ⭐ Stars: {stars}
- 🍴 Forks: {forks}
- 🏷️ Topics: {topics_str or 'None'}
- 💻 Language: {language or 'Not specified'}

## Links
- Repository: {url}
- Owner: https://github.com/{owner}
"""
                
                item = RawNewsItem(
                    external_id=str(repo.get('id', '')),
                    title=f"New GitHub Repo: {repo_name}",
                    url=url,
                    author=owner,
                    published_at=published_at,
                    content_raw=md_content,
                    image_urls=[]  # Could fetch repo image if available
                )
                items.append(item)
                
        except requests.RequestException as e:
            print(f"Error fetching from GitHub: {e}")
        except Exception as e:
            print(f"Unexpected error in GitHub adapter: {e}")
        
        return items
    
    def parse_content(self, raw_data) -> str:
        """Content is already in markdown format"""
        return str(raw_data)
