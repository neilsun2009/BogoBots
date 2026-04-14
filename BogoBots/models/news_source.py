# BogoBots/models/news_source.py
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from BogoBots.database.base import BaseModel

class NewsSource(BaseModel):
    """Configuration for news data sources"""
    __tablename__ = 'news_source'
    __table_args__ = {'comment': 'Configuration for AI news data sources'}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, comment='Source name (e.g., "OpenAI Blog")')
    source_type = Column(String(20), nullable=False, default='RSS', comment='Source fetch protocol. RSS only for now')
    news_type = Column(String(30), nullable=False, default='AI Company', comment='News domain type: ai company, media, twitter, github, wechat, paper, podcast, etc.')
    url = Column(String(500), nullable=False, comment='Source URL or endpoint')
    backup_url = Column(String(500), comment='Backup RSS URL')
    icon = Column(String(500), comment='Icon URL for source display')
    priority = Column(String(10), nullable=False, default='medium', comment='Priority level: high, medium, low')
    config_json = Column(Text, comment='Type-specific configuration in JSON format')
    crawl_schedule = Column(String(50), default='0 0 * * *', comment='Cron expression for crawl schedule')
    is_active = Column(Boolean, default=True, comment='Whether this source is active')
    last_crawled_at = Column(DateTime, comment='Last successful crawl timestamp')
    last_error = Column(Text, comment='Last error message if crawl failed')
    
    # Relationships
    items = relationship("NewsItem", back_populates="source")
    
    def __repr__(self):
        return f"<NewsSource(id={self.id}, name='{self.name}', source_type='{self.source_type}', news_type='{self.news_type}')>"
