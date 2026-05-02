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
    response_json = response.json()
    _podcast_progress(
        progress_callback,
        f"Finished chunk {chunk_number}/{total_chunks} in {time.perf_counter() - start_time:.2f}s",
    )
    return response_json


def generate_podcast_transcript_for_item(
    item_id: int,
    api_key: str,
    model_name: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Generate a podcast transcript/summary from episode audio and save it to content_raw.
    Uses NewsHubConfig for model and prompt templates.
    """
    from BogoBots.database.session import get_session
    from BogoBots.models.news_hub_config import (
        NewsHubConfig,
    )
    from BogoBots.models.news_item import NewsItem

    session = get_session()
    try:
        item = session.query(NewsItem).filter_by(id=item_id).first()
        config = NewsHubConfig.get_or_create(session)
        if not item:
            raise ValueError(f"News item #{item_id} not found")
        if not item.audio_url:
            raise ValueError("This podcast item does not have an audio URL")

        selected_model = model_name or config.podcast_transcription_model or "xiaomi/mimo-v2-omni"
        first_prompt_template = (
            config.podcast_transcription_first_prompt_template
        )
        followup_prompt_template = (
            config.podcast_transcription_followup_prompt_template
        )
        episode_description = item.episode_description or ""
        audio_url = item.audio_url
    finally:
        session.close()

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
            response_json = _transcribe_audio_chunk(
                chunk=chunk,
                chunk_number=chunk_number,
                total_chunks=total_chunks,
                model_name=selected_model,
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

    transcript = "\n\n".join(part for part in transcript_parts if part)
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

    _podcast_progress(progress_callback, "Saved AI-generated podcast transcript")
    return {
        "transcript": transcript,
        "model": selected_model,
        "chunks": chunk_results,
    }
