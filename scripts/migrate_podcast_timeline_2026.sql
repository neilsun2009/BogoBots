-- Podcast timeline + NewsHubConfig podcast columns migration (MySQL 8+)
-- Run against your BogoBots database after deploying new code.

-- 1) news_item: timeline field
ALTER TABLE news_item
  ADD COLUMN podcast_timeline_summary TEXT NULL
  COMMENT 'LLM podcast timeline summary from transcript or audio'
  AFTER content_raw;

-- If the column already exists, skip or comment out the above and continue.

-- 2) news_hub_config: new podcast settings (adjust if columns already exist)
ALTER TABLE news_hub_config
  ADD COLUMN podcast_transcript_from_audio_model VARCHAR(100) NULL DEFAULT 'xiaomi/mimo-v2-omni'
    COMMENT 'LLM for podcast transcript-from-audio (writes content_raw)' AFTER translation_max_tokens,
  ADD COLUMN podcast_transcript_from_audio_first_prompt_template TEXT NULL
    COMMENT 'First-chunk prompt for transcript from audio' AFTER podcast_transcript_from_audio_model,
  ADD COLUMN podcast_transcript_from_audio_followup_prompt_template TEXT NULL
    COMMENT 'Follow-up chunk prompt for transcript from audio' AFTER podcast_transcript_from_audio_first_prompt_template,
  ADD COLUMN podcast_timeline_from_audio_model VARCHAR(100) NULL DEFAULT 'xiaomi/mimo-v2-omni'
    COMMENT 'LLM for podcast timeline-from-audio (writes podcast_timeline_summary)' AFTER podcast_transcript_from_audio_followup_prompt_template,
  ADD COLUMN podcast_timeline_from_audio_first_prompt_template TEXT NULL
    COMMENT 'First-chunk prompt for timeline from audio' AFTER podcast_timeline_from_audio_model,
  ADD COLUMN podcast_timeline_from_audio_followup_prompt_template TEXT NULL
    COMMENT 'Follow-up chunk prompt for timeline from audio' AFTER podcast_timeline_from_audio_first_prompt_template,
  ADD COLUMN podcast_timeline_from_text_model VARCHAR(100) NULL DEFAULT 'openai/gpt-5.4-mini'
    COMMENT 'LLM for podcast timeline from transcript text' AFTER podcast_timeline_from_audio_followup_prompt_template,
  ADD COLUMN podcast_timeline_from_text_prompt_template TEXT NULL
    COMMENT 'Prompt for timeline summary from transcript; use {title} {episode_description} {transcript}' AFTER podcast_timeline_from_text_model;

-- 3) Optional: copy legacy unified podcast transcription prompts into timeline-from-audio
-- (only if your table still has the old columns at migration time)
-- UPDATE news_hub_config SET
--   podcast_timeline_from_audio_model = COALESCE(podcast_timeline_from_audio_model, podcast_transcription_model),
--   podcast_timeline_from_audio_first_prompt_template = COALESCE(podcast_timeline_from_audio_first_prompt_template, podcast_transcription_first_prompt_template),
--   podcast_timeline_from_audio_followup_prompt_template = COALESCE(podcast_timeline_from_audio_followup_prompt_template, podcast_transcription_followup_prompt_template)
-- WHERE id = 1;

-- 4) Set transcript-from-audio defaults from legacy row if needed (optional)
-- UPDATE news_hub_config SET
--   podcast_transcript_from_audio_model = COALESCE(podcast_transcript_from_audio_model, podcast_transcription_model),
--   podcast_transcript_from_audio_first_prompt_template = COALESCE(podcast_transcript_from_audio_first_prompt_template, podcast_transcription_first_prompt_template),
--   podcast_transcript_from_audio_followup_prompt_template = COALESCE(podcast_transcript_from_audio_followup_prompt_template, podcast_transcription_followup_prompt_template)
-- WHERE id = 1;

-- 5) Drop legacy columns after verification (optional; uncomment when ready)
-- ALTER TABLE news_hub_config
--   DROP COLUMN podcast_transcription_model,
--   DROP COLUMN podcast_transcription_first_prompt_template,
--   DROP COLUMN podcast_transcription_followup_prompt_template;
