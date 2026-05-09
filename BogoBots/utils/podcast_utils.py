import base64
import json
import mimetypes
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import unquote, urlparse

import requests


PODCAST_CHUNK_SECONDS = 20 * 60
AUDIO_CHUNK_MAX_ATTEMPTS = 3


def _podcast_progress(progress_callback: Optional[Callable[[str], None]], message: str):
    if progress_callback:
        progress_callback(message)
    print(message)


def _format_audio_time(seconds: float) -> str:
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _run_audio_command(command: List[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        error_output = (error.stderr or error.stdout or "").strip()
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{error_output}") from error


def _ensure_audio_tools():
    missing_tools = [
        tool_name
        for tool_name in ("ffmpeg", "ffprobe")
        if shutil.which(tool_name) is None
    ]
    if missing_tools:
        raise RuntimeError(
            "Missing required audio tool(s): "
            f"{', '.join(missing_tools)}. Install ffmpeg first."
        )


def _filename_from_url(url: str, content_type: str = "") -> str:
    parsed_url = urlparse(url)
    filename = Path(unquote(parsed_url.path)).name
    if filename:
        return filename

    extension = mimetypes.guess_extension(content_type or "") or ".mp3"
    return f"podcast_audio{extension}"


def _download_podcast_audio(audio_url: str, download_dir: Path, progress_callback=None) -> Path:
    start_time = time.perf_counter()
    _podcast_progress(progress_callback, f"Downloading podcast audio: {audio_url}")
    response = requests.get(audio_url, stream=True, timeout=60)
    response.raise_for_status()

    output_path = download_dir / _filename_from_url(audio_url, response.headers.get("Content-Type", ""))
    downloaded_bytes = 0
    with output_path.open("wb") as audio_file:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                audio_file.write(chunk)
                downloaded_bytes += len(chunk)

    _podcast_progress(
        progress_callback,
        f"Downloaded {downloaded_bytes / 1024 / 1024:.2f} MB in {time.perf_counter() - start_time:.2f}s",
    )
    return output_path


def _get_audio_duration_seconds(audio_path: Path, progress_callback=None) -> float:
    _podcast_progress(progress_callback, f"Detecting audio duration for {audio_path.name}")
    result = _run_audio_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(audio_path),
        ]
    )
    duration = float(json.loads(result.stdout)["format"]["duration"])
    _podcast_progress(progress_callback, f"Audio duration: {_format_audio_time(duration)}")
    return duration


def _split_audio_if_needed(audio_path: Path, duration: float, progress_callback=None) -> List[Dict[str, Any]]:
    chunk_minutes = int(PODCAST_CHUNK_SECONDS / 60)
    if duration <= PODCAST_CHUNK_SECONDS:
        _podcast_progress(progress_callback, f"Audio is {chunk_minutes} minutes or shorter; no splitting needed")
        return [{"path": audio_path, "start_seconds": 0, "end_seconds": duration}]

    chunk_dir = audio_path.parent / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = chunk_dir / f"part_%03d{audio_path.suffix}"

    _podcast_progress(progress_callback, f"Splitting audio into {chunk_minutes}-minute chunks under {chunk_dir}")
    _run_audio_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(audio_path),
            "-f",
            "segment",
            "-segment_time",
            str(PODCAST_CHUNK_SECONDS),
            "-c",
            "copy",
            str(output_pattern),
        ]
    )

    chunk_paths = sorted(chunk_dir.glob(f"part_*{audio_path.suffix}"))
    if not chunk_paths:
        raise RuntimeError("ffmpeg did not produce any audio chunks")

    chunks = []
    for index, chunk_path in enumerate(chunk_paths):
        chunks.append(
            {
                "path": chunk_path,
                "start_seconds": index * PODCAST_CHUNK_SECONDS,
                "end_seconds": min((index + 1) * PODCAST_CHUNK_SECONDS, duration),
            }
        )

    _podcast_progress(progress_callback, f"Created {len(chunks)} audio chunks")
    return chunks


def _encode_audio_to_base64(audio_path: Path) -> str:
    with audio_path.open("rb") as audio_file:
        return base64.b64encode(audio_file.read()).decode("utf-8")


def _audio_format(audio_path: Path) -> str:
    return audio_path.suffix.lower().lstrip(".") or "mp3"


def _extract_openrouter_text(response_json: Dict[str, Any]) -> str:
    try:
        content = response_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return json.dumps(response_json, ensure_ascii=False)

    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ).strip()
    return str(content).strip()


def _extract_speaker_context(transcript_text: str) -> str:
    if not transcript_text:
        return ""

    heading = "## Speaker Info"
    start = transcript_text.find(heading)
    if start == -1:
        return transcript_text[:4000]

    next_heading = transcript_text.find("\n## ", start + len(heading))
    speaker_context = transcript_text[start:] if next_heading == -1 else transcript_text[start:next_heading]
    return speaker_context.strip()[:4000]


def _format_podcast_prompt(
    template: str,
    chunk_number: int,
    total_chunks: int,
    start_seconds: float,
    end_seconds: float,
    episode_description: str,
    speaker_context: str = "",
) -> str:
    return template.format(
        chunk_number=chunk_number,
        total_chunks=total_chunks,
        start_time=_format_audio_time(start_seconds),
        end_time=_format_audio_time(end_seconds),
        episode_description=episode_description or "",
        speaker_context=speaker_context or "",
    )


def _transcribe_audio_chunk(
    chunk: Dict[str, Any],
    chunk_number: int,
    total_chunks: int,
    model_name: str,
    prompt: str,
    api_key: str,
    progress_callback=None,
) -> Dict[str, Any]:
    _podcast_progress(progress_callback, f"Transcribing chunk {chunk_number}/{total_chunks} with model {model_name}")
    start_time = time.perf_counter()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": _encode_audio_to_base64(chunk["path"]),
                            "format": _audio_format(chunk["path"]),
                        },
                    },
                ],
            }
        ],
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=600,
    )
    response.raise_for_status()
    try:
        response_json = response.json()
    except ValueError:
        response_text = response.text.replace("\n", "").strip()
        response_json = json.loads(response_text)
    _podcast_progress(
        progress_callback,
        f"Finished chunk {chunk_number}/{total_chunks} in {time.perf_counter() - start_time:.2f}s",
    )
    return response_json


def _transcribe_audio_chunk_with_retries(
    chunk: Dict[str, Any],
    chunk_number: int,
    total_chunks: int,
    model_name: str,
    prompt: str,
    api_key: str,
    progress_callback=None,
) -> Dict[str, Any]:
    """Call OpenRouter for one audio chunk; retry on HTTP/JSON failures."""
    last_exc: Optional[BaseException] = None
    for attempt in range(1, AUDIO_CHUNK_MAX_ATTEMPTS + 1):
        try:
            return _transcribe_audio_chunk(
                chunk=chunk,
                chunk_number=chunk_number,
                total_chunks=total_chunks,
                model_name=model_name,
                prompt=prompt,
                api_key=api_key,
                progress_callback=progress_callback,
            )
        except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
            last_exc = exc
            if attempt >= AUDIO_CHUNK_MAX_ATTEMPTS:
                break
            wait_s = min(2.0 * attempt, 10.0)
            _podcast_progress(
                progress_callback,
                f"Chunk {chunk_number}/{total_chunks} attempt {attempt}/{AUDIO_CHUNK_MAX_ATTEMPTS} "
                f"failed ({type(exc).__name__}: {exc}); retrying in {wait_s:.1f}s...",
            )
            time.sleep(wait_s)
    raise RuntimeError(
        f"OpenRouter failed for chunk {chunk_number}/{total_chunks} "
        f"after {AUDIO_CHUNK_MAX_ATTEMPTS} attempts"
    ) from last_exc


def _run_chunked_audio_llm(
    *,
    item_id: int,
    audio_url: str,
    episode_description: str,
    api_key: str,
    model_name: str,
    first_prompt_template: str,
    followup_prompt_template: str,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> tuple[str, List[Dict[str, Any]]]:
    """Download audio, chunk, call OpenRouter per chunk, return combined markdown and chunk metadata."""
    if not api_key:
        raise RuntimeError("Missing OpenRouter API key")

    _ensure_audio_tools()
    with tempfile.TemporaryDirectory(prefix=f"podcast_item_{item_id}_") as temp_dir:
        temp_path = Path(temp_dir)
        audio_path = _download_podcast_audio(audio_url, temp_path, progress_callback=progress_callback)
        duration = _get_audio_duration_seconds(audio_path, progress_callback=progress_callback)
        chunks = _split_audio_if_needed(audio_path, duration, progress_callback=progress_callback)

        chunk_results = []
        transcript_parts = []
        speaker_context = ""
        total_chunks = len(chunks)

        for chunk_number, chunk in enumerate(chunks, start=1):
            template = first_prompt_template if chunk_number == 1 else followup_prompt_template
            prompt = _format_podcast_prompt(
                template=template,
                chunk_number=chunk_number,
                total_chunks=total_chunks,
                start_seconds=chunk["start_seconds"],
                end_seconds=chunk["end_seconds"],
                episode_description=episode_description,
                speaker_context=speaker_context,
            )
            response_json = _transcribe_audio_chunk_with_retries(
                chunk=chunk,
                chunk_number=chunk_number,
                total_chunks=total_chunks,
                model_name=model_name,
                prompt=prompt,
                api_key=api_key,
                progress_callback=progress_callback,
            )
            chunk_text = _extract_openrouter_text(response_json)
            transcript_parts.append(chunk_text)
            chunk_results.append(
                {
                    "chunk_number": chunk_number,
                    "total_chunks": total_chunks,
                    "start_seconds": chunk["start_seconds"],
                    "end_seconds": chunk["end_seconds"],
                    "response": response_json,
                }
            )
            if chunk_number == 1:
                speaker_context = _extract_speaker_context(chunk_text)
                if speaker_context:
                    _podcast_progress(progress_callback, "Extracted speaker context from first chunk")

    combined = "\n\n".join(part for part in transcript_parts if part)
    return combined, chunk_results


def generate_podcast_transcript_for_item(
    item_id: int,
    api_key: str,
    model_name: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Transcribe episode audio into timestamped transcript; saves content_raw only.
    """
    from BogoBots.database.session import get_session
    from BogoBots.models.news_hub_config import NewsHubConfig
    from BogoBots.models.news_item import NewsItem

    session = get_session()
    try:
        item = session.query(NewsItem).filter_by(id=item_id).first()
        config = NewsHubConfig.get_or_create(session)
        if not item:
            raise ValueError(f"News item #{item_id} not found")
        if not item.audio_url:
            raise ValueError("This podcast item does not have an audio URL")

        selected_model = model_name or config.podcast_transcript_from_audio_model or "xiaomi/mimo-v2-omni"
        first_prompt_template = config.podcast_transcript_from_audio_first_prompt_template
        followup_prompt_template = config.podcast_transcript_from_audio_followup_prompt_template
        episode_description = item.episode_description or ""
        audio_url = item.audio_url
    finally:
        session.close()

    transcript, chunk_results = _run_chunked_audio_llm(
        item_id=item_id,
        audio_url=audio_url,
        episode_description=episode_description,
        api_key=api_key,
        model_name=selected_model,
        first_prompt_template=first_prompt_template,
        followup_prompt_template=followup_prompt_template,
        progress_callback=progress_callback,
    )

    session = get_session()
    try:
        item = session.query(NewsItem).filter_by(id=item_id).first()
        if item:
            item.content_raw = transcript
            item.summary_model = selected_model
            item.updated_at = datetime.now(timezone.utc)
            session.commit()
    finally:
        session.close()

    _podcast_progress(progress_callback, "Saved transcript to content_raw")
    return {
        "transcript": transcript,
        "model": selected_model,
        "chunks": chunk_results,
    }


def generate_podcast_timeline_from_audio_for_item(
    item_id: int,
    api_key: str,
    model_name: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Build an episode timeline from audio chunks; saves podcast_timeline_summary only.
    """
    from BogoBots.database.session import get_session
    from BogoBots.models.news_hub_config import NewsHubConfig
    from BogoBots.models.news_item import NewsItem

    session = get_session()
    try:
        item = session.query(NewsItem).filter_by(id=item_id).first()
        config = NewsHubConfig.get_or_create(session)
        if not item:
            raise ValueError(f"News item #{item_id} not found")
        if not item.audio_url:
            raise ValueError("This podcast item does not have an audio URL")

        selected_model = model_name or config.podcast_timeline_from_audio_model or "xiaomi/mimo-v2-omni"
        first_prompt_template = config.podcast_timeline_from_audio_first_prompt_template
        followup_prompt_template = config.podcast_timeline_from_audio_followup_prompt_template
        episode_description = item.episode_description or ""
        audio_url = item.audio_url
    finally:
        session.close()

    timeline_text, chunk_results = _run_chunked_audio_llm(
        item_id=item_id,
        audio_url=audio_url,
        episode_description=episode_description,
        api_key=api_key,
        model_name=selected_model,
        first_prompt_template=first_prompt_template,
        followup_prompt_template=followup_prompt_template,
        progress_callback=progress_callback,
    )

    session = get_session()
    try:
        item = session.query(NewsItem).filter_by(id=item_id).first()
        if item:
            item.podcast_timeline_summary = timeline_text
            item.summary_model = selected_model
            item.updated_at = datetime.now(timezone.utc)
            session.commit()
    finally:
        session.close()

    _podcast_progress(progress_callback, "Saved timeline to podcast_timeline_summary")
    return {
        "timeline": timeline_text,
        "model": selected_model,
        "chunks": chunk_results,
    }


def generate_podcast_timeline_from_text_for_item(
    item_id: int,
    model_name: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Build podcast_timeline_summary from content_raw via text model (OpenRouter via llm_utils).
    """
    from BogoBots.database.session import get_session
    from BogoBots.models.news_hub_config import NewsHubConfig
    from BogoBots.models.news_item import NewsItem
    from BogoBots.utils.llm_utils import _chat_completion

    session = get_session()
    try:
        item = session.query(NewsItem).filter_by(id=item_id).first()
        config = NewsHubConfig.get_or_create(session)
        if not item:
            raise ValueError(f"News item #{item_id} not found")
        transcript = (item.content_raw or "").strip()
        if not transcript:
            raise ValueError("No transcript in content_raw; add RSS transcript or run transcript-from-audio first.")

        template = config.podcast_timeline_from_text_prompt_template
        selected_model = model_name or config.podcast_timeline_from_text_model or "openai/gpt-5.4-mini"
        title = item.title or ""
        episode_description = item.episode_description or ""
    finally:
        session.close()

    # max_transcript_chars = 120_000
    # if len(transcript) > max_transcript_chars:
    #     transcript = transcript[:max_transcript_chars]
    #     _podcast_progress(progress_callback, f"Transcript truncated to {max_transcript_chars} chars for LLM context")

    prompt = template.format(
        title=title,
        episode_description=episode_description,
        transcript=transcript,
    )
    _podcast_progress(progress_callback, f"Generating timeline from transcript with {selected_model}")
    timeline_text, input_tokens, output_tokens = _chat_completion(
        model_name=selected_model,
        prompt=prompt,
        # max_tokens=8000,
        temperature=0.3,
    )

    session = get_session()
    try:
        item = session.query(NewsItem).filter_by(id=item_id).first()
        if item:
            item.podcast_timeline_summary = timeline_text
            item.summary_model = selected_model
            item.summary_tokens_input = input_tokens
            item.summary_tokens_output = output_tokens
            item.updated_at = datetime.now(timezone.utc)
            session.commit()
    finally:
        session.close()

    _podcast_progress(progress_callback, "Saved timeline to podcast_timeline_summary")
    return {
        "timeline": timeline_text,
        "model": selected_model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def generate_podcast_timeline_summary_for_item(
    item_id: int,
    api_key: str,
    model_name: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Prefer non-empty content_raw → timeline-from-text; else audio_url → timeline-from-audio.
    """
    from BogoBots.database.session import get_session
    from BogoBots.models.news_item import NewsItem

    session = get_session()
    try:
        item = session.query(NewsItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"News item #{item_id} not found")
        transcript = (item.content_raw or "").strip()
        audio_url = (item.audio_url or "").strip()
    finally:
        session.close()

    if transcript:
        return generate_podcast_timeline_from_text_for_item(
            item_id=item_id,
            model_name=model_name,
            progress_callback=progress_callback,
        )
    if audio_url:
        return generate_podcast_timeline_from_audio_for_item(
            item_id=item_id,
            api_key=api_key,
            model_name=model_name,
            progress_callback=progress_callback,
        )
    raise ValueError(
        "Cannot generate timeline: need a non-empty transcript (content_raw) or an audio URL."
    )
