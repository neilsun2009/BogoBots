# BogoBots/crawlers/adapters/api_adapter.py
import requests
from datetime import datetime
from typing import List, Optional, Dict, Any

from BogoBots.crawlers.news_crawler import BaseNewsCrawler, RawNewsItem


class APIAdapter(BaseNewsCrawler):
    """
    Generic adapter for various APIs.
    Supports HuggingFace Trending, Papers with Code, and other JSON APIs.
    
    Config options:
    - api_type: 'huggingface_trending', 'hf_papers', 'paperswithcode', 'generic'
    - api_key: API key if required
    - endpoint: Custom endpoint URL (for generic type)
    - params: Additional query parameters
    - headers: Additional headers
    - date_field: Field name for date in response
    - title_field: Field name for title
    - url_field: Field name for URL
    - content_field: Field name for content/summary
    """
    
    source_type = 'api'
    
    def fetch_new_items(self, since: datetime) -> List[RawNewsItem]:
        """
        Fetch items from configured API.
        """
        api_type = self.config.get('api_type', 'generic')
        
        if api_type == 'huggingface_trending':
            return self._fetch_huggingface_trending(since)
        elif api_type == 'hf_papers':
            return self._fetch_hf_papers(since)
        elif api_type == 'paperswithcode':
            return self._fetch_paperswithcode(since)
        else:
            return self._fetch_generic(since)
    
    def _fetch_huggingface_trending(self, since: datetime) -> List[RawNewsItem]:
        """Fetch trending models from HuggingFace"""
        items = []
        
        # HF API for trending models
        # Note: HF doesn't have a direct "trending" API, so we fetch recent models
        url = 'https://huggingface.co/api/models'
        
        params = {
            'limit': self.config.get('max_results', 20),
            'sort': 'lastModified',
            'direction': -1,
            'filter': self.config.get('filter', '')  # e.g., 'text-generation'
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            for model in data:
                # Parse last modified date
                last_modified = model.get('lastModified', '')
                if not last_modified:
                    continue
                
                try:
                    published_at = datetime.fromisoformat(last_modified.replace('Z', '+00:00'))
                except:
                    continue
                
                if published_at < since:
                    continue
                
                model_id = model.get('id', '')
                if not model_id:
                    continue
                
                downloads = model.get('downloads', 0)
                likes = model.get('likes', 0)
                
                # Get model info
                tags = model.get('tags', [])
                pipeline_tag = model.get('pipeline_tag', '')
                
                # Skip if not relevant
                min_downloads = self.config.get('min_downloads', 1000)
                if downloads < min_downloads:
                    continue
                
                # Build content
                hf_url = f"https://huggingface.co/{model_id}"
                
                md_content = f"""# HuggingFace Model: {model_id}

A trending model on HuggingFace Hub

## Stats
- ⬇️ Downloads: {downloads:,}
- ❤️ Likes: {likes:,}
- 🏷️ Pipeline: {pipeline_tag or 'Not specified'}
- 🏷️ Tags: {', '.join(tags[:5])}

## Links
- Model Card: {hf_url}
- Run with Inference API: {hf_url}?inference_api=true
"""
                
                item = RawNewsItem(
                    external_id=model_id,
                    title=f"Trending HF Model: {model_id}",
                    url=hf_url,
                    author=model_id.split('/')[0] if '/' in model_id else 'Unknown',
                    published_at=published_at,
                    content_raw=md_content,
                    image_urls=[]
                )
                items.append(item)
                
        except requests.RequestException as e:
            print(f"Error fetching from HuggingFace: {e}")
        
        return items
    
    def _fetch_hf_papers(self, since: datetime) -> List[RawNewsItem]:
        """Fetch daily papers from HuggingFace"""
        items = []
        
        # HF Daily Papers API
        url = 'https://huggingface.co/api/daily_papers'
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            papers = response.json()
            
            for paper in papers:
                # Parse published date
                published = paper.get('publishedAt', '')
                if not published:
                    continue
                
                try:
                    published_at = datetime.fromisoformat(published.replace('Z', '+00:00'))
                except:
                    continue
                
                if published_at < since:
                    continue
                
                paper_id = paper.get('id', '')
                title = paper.get('title', '')
                authors = paper.get('authors', [])
                summary = paper.get('summary', '')
                arxiv_id = paper.get('paper', {}).get('id', '')
                
                # Build author string
                author_names = [a.get('name', '') for a in authors]
                author_str = ', '.join(author_names[:3])
                if len(author_names) > 3:
                    author_str += f' et al.'
                
                # Build URLs
                paper_url = f"https://huggingface.co/papers/{arxiv_id}" if arxiv_id else ''
                arxiv_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ''
                
                # Get thumbnail
                thumbnail = paper.get('thumbnail', '')
                image_urls = [thumbnail] if thumbnail else []
                
                md_content = f"""# {title}

**Authors:** {author_str}

## Summary
{summary}

## Links
- HuggingFace Paper: {paper_url}
- arXiv: {arxiv_url}
"""
                
                item = RawNewsItem(
                    external_id=paper_id or arxiv_id,
                    title=title,
                    url=paper_url or arxiv_url,
                    author=author_str,
                    published_at=published_at,
                    content_raw=md_content,
                    image_urls=image_urls
                )
                items.append(item)
                
        except requests.RequestException as e:
            print(f"Error fetching HF papers: {e}")
        
        return items
    
    def _fetch_paperswithcode(self, since: datetime) -> List[RawNewsItem]:
        """Fetch trending papers from Papers with Code"""
        items = []
        
        # PWC API - trending papers
        url = 'https://paperswithcode.com/api/v1/papers/'
        
        params = {
            'ordering': '-published',
            'items_per_page': self.config.get('max_results', 20)
        }
        
        arxiv_type = self.config.get('arxiv_type', '')
        if arxiv_type:
            params['arxiv_id__contains'] = arxiv_type
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            for paper in data.get('results', []):
                # Parse date
                published = paper.get('published', '')
                if not published:
                    continue
                
                try:
                    published_at = datetime.fromisoformat(published.replace('Z', '+00:00'))
                except:
                    continue
                
                if published_at < since:
                    continue
                
                paper_id = paper.get('id', '')
                title = paper.get('title', '')
                authors = paper.get('authors', [])
                abstract = paper.get('abstract', '')
                url_pwc = paper.get('url', '')
                arxiv_id = paper.get('arxiv_id', '')
                
                # Build content
                author_str = ', '.join(authors[:3])
                if len(authors) > 3:
                    author_str += ' et al.'
                
                arxiv_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ''
                
                md_content = f"""# {title}

**Authors:** {author_str}

## Abstract
{abstract}

## Links
- Papers with Code: https://paperswithcode.com{url_pwc}
- arXiv: {arxiv_url}
"""
                
                item = RawNewsItem(
                    external_id=str(paper_id),
                    title=title,
                    url=f"https://paperswithcode.com{url_pwc}" if url_pwc else arxiv_url,
                    author=author_str,
                    published_at=published_at,
                    content_raw=md_content,
                    image_urls=[]
                )
                items.append(item)
                
        except requests.RequestException as e:
            print(f"Error fetching from Papers with Code: {e}")
        
        return items
    
    def _fetch_generic(self, since: datetime) -> List[RawNewsItem]:
        """Fetch from custom/generic API endpoint"""
        items = []
        
        endpoint = self.config.get('endpoint', '')
        if not endpoint:
            print("No endpoint configured for generic API adapter")
            return items
        
        headers = self.config.get('headers', {})
        params = self.config.get('params', {})
        api_key = self.config.get('api_key', '')
        
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, dict) and 'results' in data:
                results = data['results']
            elif isinstance(data, list):
                results = data
            else:
                results = [data]
            
            date_field = self.config.get('date_field', 'published_at')
            title_field = self.config.get('title_field', 'title')
            url_field = self.config.get('url_field', 'url')
            content_field = self.config.get('content_field', 'content')
            
            for item_data in results:
                # Parse date
                date_val = item_data.get(date_field, '')
                if not date_val:
                    continue
                
                try:
                    published_at = datetime.fromisoformat(str(date_val).replace('Z', '+00:00'))
                except:
                    continue
                
                if published_at < since:
                    continue
                
                title = item_data.get(title_field, 'Untitled')
                url = item_data.get(url_field, '')
                content = item_data.get(content_field, '')
                
                item = RawNewsItem(
                    external_id=str(item_data.get('id', '')),
                    title=title,
                    url=url,
                    author=item_data.get('author', ''),
                    published_at=published_at,
                    content_raw=content,
                    image_urls=item_data.get('images', [])
                )
                items.append(item)
                
        except requests.RequestException as e:
            print(f"Error fetching from generic API: {e}")
        
        return items
    
    def parse_content(self, raw_data) -> str:
        """Content is already formatted"""
        return str(raw_data)
