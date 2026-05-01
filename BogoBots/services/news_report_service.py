# BogoBots/services/news_report_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from BogoBots.database.session import get_session
from BogoBots.models.news_report import NewsReport
from BogoBots.models.news_report_item import NewsReportItem
from BogoBots.models.news_item import NewsItem
from sqlalchemy.orm import joinedload


class NewsReportService:
    """Service for managing news reports"""
    
    @staticmethod
    def get_all_reports(limit: int = 50) -> List[NewsReport]:
        """Get all reports ordered by date"""
        session = get_session()
        try:
            return session.query(NewsReport).order_by(NewsReport.report_date.desc()).limit(limit).all()
        finally:
            session.close()
    
    @staticmethod
    def get_report_by_id(report_id: int) -> Optional[NewsReport]:
        """Get a report by ID with its items"""
        session = get_session()
        try:
            return session.query(NewsReport).options(
                joinedload(NewsReport.items).joinedload(NewsReportItem.news_item)
            ).filter_by(id=report_id).first()
        finally:
            session.close()
    
    @staticmethod
    def get_reports_by_date_range(start_date: datetime, end_date: datetime) -> List[NewsReport]:
        """Get reports within a date range"""
        session = get_session()
        try:
            return session.query(NewsReport).filter(
                NewsReport.report_date >= start_date,
                NewsReport.report_date <= end_date
            ).order_by(NewsReport.report_date.desc()).all()
        finally:
            session.close()
    
    @staticmethod
    def create_report(report_date: datetime, title: str = None,
                      editorial: str = None, content: str = None,
                      summary: str = None, news_items: List[int] = None,
                      llm_model: str = None,
                      news_from: datetime = None, news_to: datetime = None,
                      item_meta: Optional[Dict[int, Dict[str, Any]]] = None,
                      language: str = "original") -> NewsReport:
        """Create a new report with optional items"""
        session = get_session()
        try:
            # Create report
            report = NewsReport(
                report_date=report_date,
                news_from=news_from,
                news_to=news_to,
                title=title or f"AI News Report - {report_date.strftime('%Y-%m-%d')}",
                editorial=editorial,
                content=content,
                summary=summary,
                status='draft',
                language=language or "original",
                news_count=len(news_items) if news_items else 0
            )
            session.add(report)
            session.flush()  # Get the ID
            
            # Add items if provided
            if news_items:
                for idx, item_id in enumerate(news_items):
                    meta = (item_meta or {}).get(item_id, {})
                    report_item = NewsReportItem(
                        report_id=report.id,
                        news_item_id=item_id,
                        order_index=idx,
                        category=meta.get("category"),
                        category_rank=meta.get("category_rank", idx + 1),
                    )
                    session.add(report_item)
                    
                    # Update news item status
                    news_item = session.query(NewsItem).filter_by(id=item_id).first()
                    if news_item:
                        news_item.status = 'included_in_report'
            
            session.commit()
            return report
        finally:
            session.close()
    
    @staticmethod
    def update_report(report_id: int, **kwargs) -> Optional[NewsReport]:
        """Update a report"""
        session = get_session()
        try:
            report = session.query(NewsReport).filter_by(id=report_id).first()
            if not report:
                return None
            
            for key, value in kwargs.items():
                if hasattr(report, key):
                    setattr(report, key, value)
            
            report.updated_at = datetime.now(timezone.utc)
            session.commit()
            return report
        finally:
            session.close()
    
    @staticmethod
    def add_item_to_report(report_id: int, news_item_id: int, 
                          order_index: int = None,
                          category: str = None,
                          category_rank: int = 1) -> Optional[NewsReportItem]:
        """Add a news item to a report"""
        session = get_session()
        try:
            # Get current max order if not provided
            if order_index is None:
                existing = session.query(NewsReportItem).filter_by(report_id=report_id).all()
                order_index = len(existing)
            
            report_item = NewsReportItem(
                report_id=report_id,
                news_item_id=news_item_id,
                order_index=order_index,
                category=category,
                category_rank=category_rank,
            )
            session.add(report_item)
            
            # Update news item status
            news_item = session.query(NewsItem).filter_by(id=news_item_id).first()
            if news_item:
                news_item.status = 'included_in_report'
            
            # Update report count
            report = session.query(NewsReport).filter_by(id=report_id).first()
            if report:
                report.news_count = session.query(NewsReportItem).filter_by(report_id=report_id).count()
            
            session.commit()
            return report_item
        finally:
            session.close()
    
    @staticmethod
    def update_report_item(report_item_id: int, **kwargs) -> Optional[NewsReportItem]:
        """Update editable fields on a report item"""
        session = get_session()
        try:
            report_item = session.query(NewsReportItem).filter_by(id=report_item_id).first()
            if not report_item:
                return None
            
            for key, value in kwargs.items():
                if hasattr(report_item, key):
                    setattr(report_item, key, value)
            
            report_item.updated_at = datetime.now(timezone.utc)
            session.commit()
            return report_item
        finally:
            session.close()
    
    @staticmethod
    def remove_item_from_report(report_id: int, news_item_id: int) -> bool:
        """Remove a news item from a report"""
        session = get_session()
        try:
            report_item = session.query(NewsReportItem).filter_by(
                report_id=report_id, news_item_id=news_item_id
            ).first()
            if not report_item:
                return False
            
            session.delete(report_item)
            
            # Update news item status back to processed
            news_item = session.query(NewsItem).filter_by(id=news_item_id).first()
            if news_item:
                news_item.status = 'processed'
            
            # Update report count
            report = session.query(NewsReport).filter_by(id=report_id).first()
            if report:
                report.news_count = session.query(NewsReportItem).filter_by(report_id=report_id).count()
            
            session.commit()
            return True
        finally:
            session.close()
    
    @staticmethod
    def reorder_report_items(report_id: int, item_order: List[int]) -> bool:
        """Reorder items in a report by their IDs"""
        session = get_session()
        try:
            for idx, item_id in enumerate(item_order):
                report_item = session.query(NewsReportItem).filter_by(
                    report_id=report_id, news_item_id=item_id
                ).first()
                if report_item:
                    report_item.order_index = idx
            
            session.commit()
            return True
        finally:
            session.close()
    
    @staticmethod
    def delete_report(report_id: int) -> bool:
        """Delete a report and all its items"""
        session = get_session()
        try:
            report = session.query(NewsReport).filter_by(id=report_id).first()
            if not report:
                return False
            
            # Delete all report items
            for report_item in report.items:
                session.delete(report_item)
            
            # Reset status of associated news items
            for report_item in report.items:
                news_item = session.query(NewsItem).filter_by(id=report_item.news_item_id).first()
                if news_item:
                    news_item.status = 'processed'
            
            session.delete(report)
            session.commit()
            return True
        finally:
            session.close()
