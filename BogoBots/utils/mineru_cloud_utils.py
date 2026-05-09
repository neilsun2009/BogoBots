"""MinerU Open API (mineru.net) — cloud PDF → markdown via public URL."""
from __future__ import annotations

from typing import Any, Callable, Optional


def mineru_extract_pdf_url(
    pdf_url: str,
    token: str,
    progress_callback: Optional[Callable[[str], None]] = None,
    *,
    extract_model: str = "vlm",
    ocr_enabled: bool = False,
    timeout: int = 600,
) -> tuple[str, Any]:
    """
    Call MinerU precision extract on a publicly reachable PDF URL.

    Requires ``mineru-open-sdk`` (``from mineru import MinerU``), not the
    local ``mineru`` CLI stack.
    """
    try:
        from mineru import MinerU
    except ImportError as e:
        raise ImportError(
            "Install the MinerU Open API client: pip install mineru-open-sdk"
        ) from e

    def _log(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    _log(f"MinerU extract: url={pdf_url!r} model={extract_model!r} ocr={ocr_enabled}")
    with MinerU(token) as client:
        try:
            result = client.extract(
                pdf_url,
                model=extract_model,
                ocr=ocr_enabled,
                timeout=timeout,
            )
        except TypeError:
            _log("MinerU extract: retrying with url + timeout only (SDK arg mismatch)")
            result = client.extract(pdf_url, timeout=timeout)
    markdown = (getattr(result, "markdown", None) or "").strip()
    images = getattr(result, "images", None)
    _log(f"MinerU done: markdown {len(markdown)} chars")
    if images is not None:
        try:
            n = len(images)
        except TypeError:
            n = "?"
        _log(f"MinerU images field: {n}")
    return markdown, images
