# BogoBots/models/news_report.py
from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.orm import relationship
from BogoBots.database.base import BaseModel

class NewsReport(BaseModel):
    """Generated news reports"""
    __tablename__ = 'news_report'
    __table_args__ = {'comment': 'Generated AI news reports'}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_date = Column(DateTime, nullable=False, index=True, comment='Date of report')
    title = Column(String(300), comment='Generated report title')
    editorial = Column(Text, comment='Editorial opening for report')
    content = Column(Text, comment='Editable final report content')
    summary = Column(Text, comment='Overall report summary')
    status = Column(String(20), default='draft', comment='Status: draft, published, archived')
    news_count = Column(Integer, default=0, comment='Number of items in report')
    
    # Relationships
    items = relationship("NewsReportItem", back_populates="report", order_by="NewsReportItem.order_index")
    
    def __repr__(self):
        return f"<NewsReport(id={self.id}, date='{self.report_date}', status='{self.status}')>"
