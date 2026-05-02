# BogoBots/models/news_hub_config.py
from sqlalchemy import Column, String, Integer, Float, DateTime, Text
from BogoBots.database.base import BaseModel


PODCAST_TRANSCRIPTION_FIRST_PROMPT_DEFAULT = '''This is podcast audio segment {chunk_number} of {total_chunks}, covering approximately {start_time} to {end_time}.

Episode description:
{episode_description}

Please listen to this first segment and produce a detailed timeline-based markdown transcript/summary in the original language. Do not translate to Chinese.

Start with a `## Speaker Info` section. Identify the speaker(s), their roles, and useful voice/context clues. If names are unclear, use `Speaker 1`, `Speaker 2`, etc.

After that, include the timeline content. Attribute each item to the speaker, for example `00:03:12 - Speaker 1: ...`.'''


PODCAST_TRANSCRIPTION_FOLLOWUP_PROMPT_DEFAULT = '''This is podcast audio segment {chunk_number} of {total_chunks}, covering approximately {start_time} to {end_time}.

Episode description:
{episode_description}

Use the speaker information from the first segment below to keep speaker labels consistent. If a new speaker appears, add a short note before the timeline item and assign the next speaker label.

{speaker_context}

Listen to this segment and produce a detailed timeline-based markdown transcript/summary in the original language. Do not translate to Chinese. Attribute each timeline item to the speaker, for example `00:33:12 - Speaker 1: ...`. Do not add a title or repeat the segment number.'''


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
    foreword_prompt_template = Column(Text, default='''Write a concise, warm foreword for an AI weekly report titled "{title}" covering {start_date} to {end_date}.
The foreword should welcome readers and build appetite for reading the detailed report. Keep it around 120-180 words.

Articles by category:
{articles_by_category}
''', comment='Prompt template for report foreword generation')
    translation_prompt_template = Column(Text, default='''Translate the following markdown report into concise professional Chinese.
Keep markdown structure, links, and section order unchanged.

Title: {title}
Coverage: {start_date} to {end_date}

Markdown:
{content}
''', comment='Prompt template for report translation')
    foreword_model = Column(String(100), default='openai/gpt-5.4-mini', comment='LLM model for foreword generation')
    foreword_max_tokens = Column(Integer, default=400, comment='Max tokens for foreword generation')
    translation_model = Column(String(100), default='openai/gpt-5.4-mini', comment='LLM model for report translation')
    translation_max_tokens = Column(Integer, default=5000, comment='Max tokens for translation generation')
    podcast_transcription_model = Column(String(100), default='xiaomi/mimo-v2-omni', comment='LLM model for podcast transcription')
    podcast_transcription_first_prompt_template = Column(
        Text,
        default=PODCAST_TRANSCRIPTION_FIRST_PROMPT_DEFAULT,
        comment='Prompt template for first podcast audio chunk'
    )
    podcast_transcription_followup_prompt_template = Column(
        Text,
        default=PODCAST_TRANSCRIPTION_FOLLOWUP_PROMPT_DEFAULT,
        comment='Prompt template for later podcast audio chunks with speaker context'
    )
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
