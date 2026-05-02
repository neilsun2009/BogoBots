# BogoBots/services/news_source_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from BogoBots.database.session import get_session
from BogoBots.models.news_source import NewsSource


class NewsSourceService:
    """Service for managing news sources"""
    
    @staticmethod
    def get_all_sources() -> List[NewsSource]:
        """Get all news sources"""
        session = get_session()
        try:
            return session.query(NewsSource).order_by(NewsSource.name).all()
        finally:
            session.close()
    
    @staticmethod
    def get_active_sources() -> List[NewsSource]:
        """Get only active news sources"""
        session = get_session()
        try:
            return session.query(NewsSource).filter_by(is_active=True).order_by(NewsSource.name).all()
        finally:
            session.close()
    
    @staticmethod
    def get_source_by_id(source_id: int) -> Optional[NewsSource]:
        """Get a news source by ID"""
        session = get_session()
        try:
            return session.query(NewsSource).filter_by(id=source_id).first()
        finally:
            session.close()
    
    @staticmethod
    def create_source(name: str, source_type: str, news_type: str, url: str, config: Dict = None,
                      backup_url: str = None,
                      icon: str = None, priority: str = 'medium',
                      crawl_schedule: str = '0 8 * * *', is_active: bool = True) -> NewsSource:
        """Create a new news source"""
        session = get_session()
        try:
            import json
            source = NewsSource(
                name=name,
                source_type=source_type,
                news_type=news_type,
                url=url,
                backup_url=backup_url,
                icon=icon,
                priority=priority,
                config_json=json.dumps(config) if config else None,
                crawl_schedule=crawl_schedule,
                is_active=is_active
            )
            session.add(source)
            session.commit()
            return source
        finally:
            session.close()
    
    @staticmethod
    def update_source(source_id: int, **kwargs) -> Optional[NewsSource]:
        """Update a news source"""
        session = get_session()
        try:
            source = session.query(NewsSource).filter_by(id=source_id).first()
            if not source:
                return None
            
            # Handle config_json specially
            if 'config' in kwargs:
                import json
                kwargs['config_json'] = json.dumps(kwargs.pop('config'))
            
            for key, value in kwargs.items():
                if hasattr(source, key):
                    setattr(source, key, value)
            
            source.updated_at = datetime.now(timezone.utc)
            session.commit()
            return source
        finally:
            session.close()
    
    @staticmethod
    def delete_source(source_id: int) -> bool:
        """Delete a news source"""
        session = get_session()
        try:
            source = session.query(NewsSource).filter_by(id=source_id).first()
            if not source:
                return False
            
            session.delete(source)
            session.commit()
            return True
        finally:
            session.close()
    
    @staticmethod
    def test_source_connection(source_type: str, url: str, config: Dict = None) -> Dict[str, Any]:
        """Test if a source can be reached and parsed"""
        try:
            if source_type not in ('RSS', 'Podcast'):
                return {
                    'success': False,
                    'message': "Only RSS and Podcast source types are supported currently."
                }

            if source_type in ('RSS', 'Podcast'):
                import feedparser
                feed = feedparser.parse(url)
                
                if feed.bozo and feed.bozo_exception:
                    return {
                        'success': False,
                        'message': f"Parse warning: {feed.bozo_exception}",
                        'entries_count': len(feed.entries)
                    }
                
                return {
                    'success': True,
                    'message': f"Successfully parsed feed with {len(feed.entries)} entries",
                    'feed_title': feed.get('title', 'Unknown'),
                    'entries_count': len(feed.entries)
                }
            
            # Add more source types as needed
            return {
                'success': True,
                'message': f"Source type '{source_type}' connection test placeholder"
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Connection failed: {str(e)}"
            }
