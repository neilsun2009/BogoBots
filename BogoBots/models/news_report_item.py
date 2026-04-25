# BogoBots/models/news_report_item.py
from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from BogoBots.database.base import BaseModel

class NewsReportItem(BaseModel):
    """Junction table linking reports to news items with comments and ratings"""
    __tablename__ = 'news_report_item'
    __table_args__ = {'comment': 'Report items with comments and ratings'}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey('news_report.id'), nullable=False, comment='FK to news report')
    news_item_id = Column(Integer, ForeignKey('news_item.id'), nullable=False, comment='FK to news item')
    order_index = Column(Integer, default=0, comment='Position in report')
    category = Column(String(40), comment='Editorial category in final report')
    category_rank = Column(Integer, default=1, comment='Rank within category')
    
    # Relationships
    report = relationship("NewsReport", back_populates="items")
    news_item = relationship("NewsItem", back_populates="report_items")
    
    def __repr__(self):
        return f"<NewsReportItem(id={self.id}, report_id={self.report_id}, news_item_id={self.news_item_id})>"
