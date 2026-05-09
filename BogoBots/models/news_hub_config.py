# BogoBots/models/news_hub_config.py
from sqlalchemy import Column, String, Integer, Float, DateTime, Text
from BogoBots.database.base import BaseModel


# Timeline from audio (chunked input_audio) — structured episode timeline, not raw transcript
PODCAST_TIMELINE_FROM_AUDIO_FIRST_PROMPT_DEFAULT = '''This is podcast audio segment {chunk_number} of {total_chunks}, covering approximately {start_time} to {end_time}.

Episode description:
{episode_description}

Listen to this segment and produce a detailed markdown timeline for the episode in the original language. Cover key beats, topics, and takeaways with approximate timing. Do not translate to Chinese.

Start with a `## Speaker Info` section if multiple voices are audible. Then timeline items, for example `00:03:12 - Topic or speaker: ...`. Do not output a full word-for-word transcript here.'''


PODCAST_TIMELINE_FROM_AUDIO_FOLLOWUP_PROMPT_DEFAULT = '''This is podcast audio segment {chunk_number} of {total_chunks}, covering approximately {start_time} to {end_time}.

Episode description:
{episode_description}

Use the speaker/context information from earlier segments below to stay consistent.

{speaker_context}

Continue the markdown timeline in the original language for this segment only. Do not translate to Chinese. Do not repeat segment numbering or titles.'''


# Transcript from audio (chunked) — timestamped transcript / speaker attribution only
PODCAST_TRANSCRIPT_FROM_AUDIO_FIRST_PROMPT_DEFAULT = '''This is podcast audio segment {chunk_number} of {total_chunks}, covering approximately {start_time} to {end_time}.

Episode description:
{episode_description}

Transcribe this segment in the original language. Output timestamped lines with speaker labels where possible (e.g. `00:03:12 Speaker 1: ...`). Do not add a high-level episode summary or timeline overview — transcript only. Do not translate to Chinese.

Start with a short `## Speaker Info` block listing who is speaking if you can tell.'''


PODCAST_TRANSCRIPT_FROM_AUDIO_FOLLOWUP_PROMPT_DEFAULT = '''This is podcast audio segment {chunk_number} of {total_chunks}, covering approximately {start_time} to {end_time}.

Episode description:
{episode_description}

Continue using this speaker context for consistent labels:

{speaker_context}

Transcribe this segment only in the original language. Timestamped transcript lines only; no episode summary. Do not translate to Chinese.'''


PODCAST_TIMELINE_FROM_TEXT_PROMPT_DEFAULT = '''You are given a podcast episode transcript. Produce a detailed markdown timeline summary in the original language. Focus on topics, arguments, and takeaways with time references where the transcript provides them. Do not translate to Chinese.

Title: {title}

Episode description:
{episode_description}

Transcript:
{transcript}

Timeline summary:'''


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

    podcast_transcript_from_audio_model = Column(
        String(100), default='xiaomi/mimo-v2-omni', comment='LLM for podcast transcript-from-audio (writes content_raw)'
    )
    podcast_transcript_from_audio_first_prompt_template = Column(
        Text,
        default=PODCAST_TRANSCRIPT_FROM_AUDIO_FIRST_PROMPT_DEFAULT,
        comment='First-chunk prompt for transcript from audio',
    )
    podcast_transcript_from_audio_followup_prompt_template = Column(
        Text,
        default=PODCAST_TRANSCRIPT_FROM_AUDIO_FOLLOWUP_PROMPT_DEFAULT,
        comment='Follow-up chunk prompt for transcript from audio',
    )

    podcast_timeline_from_audio_model = Column(
        String(100), default='xiaomi/mimo-v2-omni', comment='LLM for podcast timeline-from-audio (writes podcast_timeline_summary)'
    )
    podcast_timeline_from_audio_first_prompt_template = Column(
        Text,
        default=PODCAST_TIMELINE_FROM_AUDIO_FIRST_PROMPT_DEFAULT,
        comment='First-chunk prompt for timeline from audio',
    )
    podcast_timeline_from_audio_followup_prompt_template = Column(
        Text,
        default=PODCAST_TIMELINE_FROM_AUDIO_FOLLOWUP_PROMPT_DEFAULT,
        comment='Follow-up chunk prompt for timeline from audio',
    )

    podcast_timeline_from_text_model = Column(
        String(100), default='openai/gpt-5.4-mini', comment='LLM for podcast timeline from transcript text'
    )
    podcast_timeline_from_text_prompt_template = Column(
        Text,
        default=PODCAST_TIMELINE_FROM_TEXT_PROMPT_DEFAULT,
        comment='Prompt for timeline summary from transcript; use {title} {episode_description} {transcript}',
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
