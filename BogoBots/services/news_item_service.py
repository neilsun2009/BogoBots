# BogoBots/services/news_item_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone

from BogoBots.database.session import get_session
from BogoBots.models.news_item import NewsItem
from BogoBots.models.news_source import NewsSource
from sqlalchemy.orm import joinedload
from sqlalchemy import case


class NewsItemService:
    """Service for managing news items"""
    
    @staticmethod
    def get_all_items(limit: int = 100, status: str = None) -> List[NewsItem]:
        """Get news items with optional filtering"""
        session = get_session()
        try:
            query = session.query(NewsItem).options(joinedload(NewsItem.source))
            if status:
                query = query.filter_by(status=status)
            return query.order_by(NewsItem.published_at.desc()).limit(limit).all()
        finally:
            session.close()
    
    @staticmethod
    def get_items_by_source(source_id: int, limit: int = 50) -> List[NewsItem]:
        """Get news items from a specific source"""
        session = get_session()
        try:
            return session.query(NewsItem).filter_by(source_id=source_id)\
                .order_by(NewsItem.published_at.desc()).limit(limit).all()
        finally:
            session.close()
    
    @staticmethod
    def get_items_by_date_range(start_date: datetime, end_date: datetime, 
                                 min_relevance: float = 0.0) -> List[NewsItem]:
        """Get news items within a date range"""
        session = get_session()
        try:
            return session.query(NewsItem).filter(
                NewsItem.published_at >= start_date,
                NewsItem.published_at <= end_date,
                NewsItem.relevance_score >= min_relevance
            ).order_by(NewsItem.published_at.desc()).all()
        finally:
            session.close()
    
    @staticmethod
    def get_item_by_id(item_id: int) -> Optional[NewsItem]:
        """Get a news item by ID"""
        session = get_session()
        try:
            return session.query(NewsItem).options(joinedload(NewsItem.source)).filter_by(id=item_id).first()
        finally:
            session.close()
    
    @staticmethod
    def update_item(item_id: int, **kwargs) -> Optional[NewsItem]:
        """Update a news item"""
        session = get_session()
        try:
            item = session.query(NewsItem).filter_by(id=item_id).first()
            if not item:
                return None
            
            for key, value in kwargs.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            
            item.updated_at = datetime.now(timezone.utc)
            session.commit()
            return item
        finally:
            session.close()
    
    @staticmethod
    def search_items(query: str, limit: int = 20) -> List[NewsItem]:
        """Search news items by title or content"""
        session = get_session()
        try:
            return session.query(NewsItem).filter(
                (NewsItem.title.contains(query)) | 
                (NewsItem.content_summary.contains(query)) |
                (NewsItem.content_raw.contains(query))
            ).order_by(NewsItem.published_at.desc()).limit(limit).all()
        finally:
            session.close()
    
    @staticmethod
    def get_items_for_report(start_date: datetime, end_date: datetime,
                             min_relevance: float = 0.3, status: str = 'processed') -> List[NewsItem]:
        """Get items ready to be included in a report"""
        session = get_session()
        try:
            return session.query(NewsItem).options(joinedload(NewsItem.source)).filter(
                NewsItem.published_at >= start_date,
                NewsItem.published_at <= end_date,
                NewsItem.relevance_score >= min_relevance,
                NewsItem.status == status
            ).order_by(NewsItem.relevance_score.desc(), NewsItem.published_at.desc()).all()
        finally:
            session.close()

    @staticmethod
    def get_starred_items_for_report(start_date: datetime, end_date: datetime) -> List[NewsItem]:
        session = get_session()
        try:
            return session.query(NewsItem).options(joinedload(NewsItem.source)).filter(
                NewsItem.published_at >= start_date,
                NewsItem.published_at <= end_date,
                NewsItem.is_starred == True,
                NewsItem.is_archived == False
            ).order_by(NewsItem.published_at.desc()).all()
        finally:
            session.close()

    @staticmethod
    def get_latest_ranked_items(limit: int = 50, unread_only: bool = False) -> List[NewsItem]:
        """
        Get latest items ranked by:
        1) starred first
        2) source priority (high > medium > low)
        3) relevance score desc
        4) published_at desc
        """
        session = get_session()
        try:
            priority_rank = case(
                (NewsSource.priority == 'high', 3),
                (NewsSource.priority == 'medium', 2),
                else_=1
            )
            query = session.query(NewsItem).join(NewsSource, NewsItem.source_id == NewsSource.id).options(
                joinedload(NewsItem.source)
            )
            if unread_only:
                query = query.filter(NewsItem.is_read == False)
            return query.order_by(
                NewsItem.is_starred.desc(),
                NewsItem.published_at.desc(),
                priority_rank.desc(),
                NewsItem.relevance_score.desc(),
            ).limit(limit).all()
        finally:
            session.close()

    @staticmethod
    def get_latest_ranked_items_paginated(
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False,
        starred_only: bool = False,
        archived: bool = False,
        source_ids: Optional[List[int]] = None,
        news_types: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Ranked feed with pagination + filters.
        Returns dict: {items, total, page, page_size, total_pages}
        """
        session = get_session()
        try:
            priority_rank = case(
                (NewsSource.priority == 'high', 3),
                (NewsSource.priority == 'medium', 2),
                else_=1
            )
            query = session.query(NewsItem).join(
                NewsSource, NewsItem.source_id == NewsSource.id
            ).options(joinedload(NewsItem.source))

            if unread_only:
                query = query.filter(NewsItem.is_read == False)
            if starred_only:
                query = query.filter(NewsItem.is_starred == True)
            if archived:
                query = query.filter(NewsItem.is_archived == True)
            else:
                query = query.filter(NewsItem.is_archived == False)
            if source_ids:
                query = query.filter(NewsItem.source_id.in_(source_ids))
            if news_types:
                query = query.filter(NewsSource.news_type.in_(news_types))
            if start_time:
                query = query.filter(NewsItem.published_at >= start_time)
            if end_time:
                query = query.filter(NewsItem.published_at <= end_time)

            total = query.count()
            total_pages = max(1, (total + page_size - 1) // page_size)
            page = max(1, min(page, total_pages))
            offset = (page - 1) * page_size

            items = query.order_by(
                NewsItem.is_starred.desc(),
                NewsItem.published_at.desc(),
                priority_rank.desc(),
                NewsItem.relevance_score.desc(),
            ).offset(offset).limit(page_size).all()

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            }
        finally:
            session.close()

    @staticmethod
    def set_item_starred(item_id: int, is_starred: bool = True) -> bool:
        session = get_session()
        try:
            item = session.query(NewsItem).filter_by(id=item_id).first()
            if not item:
                return False
            item.is_starred = is_starred
            if is_starred:
                item.is_read = True
            item.updated_at = datetime.now(timezone.utc)
            session.commit()
            return True
        finally:
            session.close()

    @staticmethod
    def set_item_archived(item_id: int, is_archived: bool = True) -> bool:
        session = get_session()
        try:
            item = session.query(NewsItem).filter_by(id=item_id).first()
            if not item:
                return False
            item.is_archived = is_archived
            item.updated_at = datetime.now(timezone.utc)
            session.commit()
            return True
        finally:
            session.close()

    @staticmethod
    def mark_item_read(item_id: int, is_read: bool = True) -> bool:
        session = get_session()
        try:
            item = session.query(NewsItem).filter_by(id=item_id).first()
            if not item:
                return False
            item.is_read = is_read
            item.updated_at = datetime.now(timezone.utc)
            session.commit()
            return True
        finally:
            session.close()
    
    @staticmethod
    def update_item_status(item_id: int, status: str) -> bool:
        """Update the status of a news item"""
        session = get_session()
        try:
            item = session.query(NewsItem).filter_by(id=item_id).first()
            if not item:
                return False
            
            item.status = status
            item.updated_at = datetime.now(timezone.utc)
            session.commit()
            return True
        finally:
            session.close()
    
    @staticmethod
    def get_item_count_by_status() -> Dict[str, int]:
        """Get count of items by status"""
        session = get_session()
        try:
            from sqlalchemy import func
            result = session.query(NewsItem.status, func.count(NewsItem.id)).group_by(NewsItem.status).all()
            return {status: count for status, count in result}
        finally:
            session.close()
    
    @staticmethod
    def delete_item(item_id: int) -> bool:
        """Delete a news item"""
        session = get_session()
        try:
            item = session.query(NewsItem).filter_by(id=item_id).first()
            if not item:
                return False
            
            session.delete(item)
            session.commit()
            return True
        finally:
            session.close()
