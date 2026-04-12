# BogoBots/models/news_hub_config.py
from sqlalchemy import Column, String, Integer, Float, DateTime, Text
from BogoBots.database.base import BaseModel

class NewsHubConfig(BaseModel):
    """AI Hub global configuration (singleton)"""
    __tablename__ = 'news_hub_config'
    __table_args__ = {'comment': 'AI Hub global configuration singleton'}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    default_summary_model = Column(String(100), default='deepseek-chat', comment='LLM for news summarization')
    default_report_model = Column(String(100), default='deepseek-chat', comment='LLM for report generation')
    summary_prompt_template = Column(Text, default='''Summarize the following AI news article in 2-3 sentences. Focus on the key innovation, announcement, or finding. Be concise but informative.

Title: {title}
Content: {content}

Summary:''', comment='Prompt template for summarization')
    report_prompt_template = Column(Text, default='''Generate a daily AI news report based on the following news items. Organize them by category (models, papers, blog posts, tools). Provide a brief contextual summary for each item.

News items:
{news_items}

Report:''', comment='Prompt template for report generation')
    max_summary_tokens = Column(Integer, default=200, comment='Max tokens per summary')
    relevance_threshold = Column(Float, default=0.3, comment='Minimum relevance score to include')
    
    @classmethod
    def get_or_create(cls, session):
        """Get singleton config or create with defaults"""
        config = session.query(cls).first()
        if not config:
            config = cls()
            session.add(config)
            session.commit()
        return config
    
    def __repr__(self):
        return f"<NewsHubConfig(id={self.id}, summary_model='{self.default_summary_model}', report_model='{self.default_report_model}')>"
