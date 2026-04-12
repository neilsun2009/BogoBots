# BogoBots/crawlers/adapters/arxiv_adapter.py
import requests
from datetime import datetime
from typing import List, Optional
from xml.etree import ElementTree as ET

from BogoBots.crawlers.news_crawler import BaseNewsCrawler, RawNewsItem


class ArXivAdapter(BaseNewsCrawler):
    """
    Adapter for arXiv RSS feeds (CS.AI, CS.CL, CS.LG, CS.CV).
    Uses arXiv's API to fetch papers.
    """
    
    source_type = 'arxiv'
    
    # arXiv API endpoint
    ARXIV_API_URL = 'http://export.arxiv.org/api/query'
    
    def fetch_new_items(self, since: datetime) -> List[RawNewsItem]:
        """
        Fetch arXiv papers published after 'since' timestamp.
        """
        items = []
        
        # Get categories from config
        categories = self.config.get('categories', ['cs.AI', 'cs.CL', 'cs.LG'])
        if isinstance(categories, str):
            categories = categories.split(',')
        
        max_results = self.config.get('max_results', 50)
        
        # Build query for multiple categories
        cat_query = ' OR '.join([f'cat:{cat.strip()}' for cat in categories])
        
        # Query arXiv API
        params = {
            'search_query': cat_query,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending',
            'max_results': max_results
        }
        
        try:
            response = requests.get(self.ARXIV_API_URL, params=params, timeout=60)
            response.raise_for_status()
            
            # Parse Atom feed
            root = ET.fromstring(response.content)
            
            # Define namespaces
            ns = {
                'atom': 'http://www.w3.org/2005/Atom',
                'arxiv': 'http://arxiv.org/schemas/atom'
            }
            
            for entry in root.findall('atom:entry', ns):
                # Parse published date
                published = entry.find('atom:published', ns)
                if published is None:
                    continue
                
                published_at = datetime.fromisoformat(published.text.replace('Z', '+00:00'))
                
                # Skip if older than 'since'
                if published_at < since:
                    continue
                
                # Get title
                title_elem = entry.find('atom:title', ns)
                title = title_elem.text if title_elem is not None else 'Untitled'
                
                # Get ID/URL
                id_elem = entry.find('atom:id', ns)
                url = id_elem.text if id_elem is not None else ''
                arxiv_id = url.split('/abs/')[-1] if '/abs/' in url else url
                
                # Get authors
                authors = []
                for author in entry.findall('atom:author', ns):
                    name = author.find('atom:name', ns)
                    if name is not None:
                        authors.append(name.text)
                author_str = ', '.join(authors[:3])
                if len(authors) > 3:
                    author_str += f' et al. ({len(authors)} authors)'
                
                # Get summary/abstract
                summary_elem = entry.find('atom:summary', ns)
                content = summary_elem.text if summary_elem is not None else ''
                
                # Get categories
                categories = []
                for cat in entry.findall('atom:category', ns):
                    term = cat.get('term', '')
                    if term:
                        categories.append(term)
                
                # Get PDF link
                pdf_url = None
                for link in entry.findall('atom:link', ns):
                    if link.get('title') == 'pdf':
                        pdf_url = link.get('href')
                        break
                
                # Build markdown content
                md_content = f"""# {title}

**Authors:** {author_str}

**Categories:** {', '.join(categories)}

**arXiv ID:** {arxiv_id}

**PDF:** {pdf_url or 'N/A'}

## Abstract

{content}
"""
                
                item = RawNewsItem(
                    external_id=arxiv_id,
                    title=title,
                    url=url,
                    author=author_str,
                    published_at=published_at,
                    content_raw=md_content,
                    image_urls=[]
                )
                items.append(item)
                
        except requests.RequestException as e:
            print(f"Error fetching from arXiv: {e}")
        except ET.ParseError as e:
            print(f"Error parsing arXiv XML: {e}")
        
        return items
    
    def parse_content(self, raw_data) -> str:
        """Content is already in markdown format"""
        return str(raw_data)
