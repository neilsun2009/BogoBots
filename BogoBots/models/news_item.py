# BogoBots/models/news_item.py
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from BogoBots.database.base import BaseModel

class NewsItem(BaseModel):
    """Crawled news content"""
    __tablename__ = 'news_item'
    __table_args__ = {'comment': 'Crawled AI news items'}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey('news_source.id'), nullable=False, comment='FK to news source')
    external_id = Column(String(200), comment='Unique ID from source')
    title = Column(String(500), nullable=False, comment='News title')
    url = Column(String(1000), nullable=False, comment='Original URL')
    author = Column(String(200), comment='Content author')
    published_at = Column(DateTime, nullable=False, index=True, comment='Original publish time')
    content_raw = Column(Text, comment='Raw content in markdown')
    content_summary = Column(Text, comment='LLM-generated summary')
    episode_description = Column(Text, comment='Podcast episode description/show notes')
    episode_duration_seconds = Column(Integer, comment='Podcast episode duration in seconds')
    audio_url = Column(String(1000), comment='Podcast audio enclosure URL')
    summary_model = Column(String(100), comment='LLM model used for summarization')
    summary_tokens_input = Column(Integer, comment='Input tokens used for summarization')
    summary_tokens_output = Column(Integer, comment='Output tokens used for summarization')
    llm_extracted_metadata = Column(JSON, comment='Entities, tags, importance indicators')
    status = Column(String(20), default='new', comment='Item status: new, processed, included_in_report, archived')
    relevance_score = Column(Float, default=0.5, comment='Relevance score 0-1')
    is_read = Column(Boolean, default=False, comment='Whether user has marked this item as read')
    is_starred = Column(Boolean, default=False, comment='Whether user starred this item')
    is_archived = Column(Boolean, default=False, comment='Whether user archived this item')
    remarks = Column(Text, comment='Admin remarks for this news item')
    image_urls = Column(JSON, comment='Array of image URLs')
    crawled_at = Column(DateTime, comment='When this item was crawled')
    
    # Relationships
    source = relationship("NewsSource", back_populates="items")
    report_items = relationship("NewsReportItem", back_populates="news_item")
    
    def __repr__(self):
        return f"<NewsItem(id={self.id}, title='{self.title[:50]}...')>"
