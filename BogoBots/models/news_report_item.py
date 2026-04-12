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
    importance = Column(Integer, default=3, comment='Importance rating 1-5 stars')
    admin_comment = Column(Text, comment='Admin comment on this item')
    custom_summary = Column(Text, comment='Override LLM summary')
    report_llm_model = Column(String(100), comment='LLM used for report generation')
    report_tokens_input = Column(Integer, comment='Input tokens for this item')
    report_tokens_output = Column(Integer, comment='Output tokens for this item')
    
    # Relationships
    report = relationship("NewsReport", back_populates="items")
    news_item = relationship("NewsItem", back_populates="report_items")
    
    def __repr__(self):
        return f"<NewsReportItem(id={self.id}, report_id={self.report_id}, news_item_id={self.news_item_id})>"
