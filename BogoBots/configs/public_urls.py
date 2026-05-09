# Public URLs for files saved under ./static/ (served in production via reverse proxy).
#
# Streamlit does not expose /app/static by itself; map this path on bots.bogobogo.me
# to the app's ./static directory.

PUBLIC_APP_BASE = "https://bots.bogobogo.me"

# URL path segment (per deployment). Joined as: {PUBLIC_APP_BASE}{TRANSCRIPTIONS_URL_PREFIX}{filename}
TRANSCRIPTIONS_URL_PREFIX = "/app/static/transcriptions/"


def transcription_pdf_public_url(filename: str) -> str:
    """Build HTTPS URL for MinerU to fetch an uploaded PDF."""
    base = PUBLIC_APP_BASE.rstrip("/")
    prefix = TRANSCRIPTIONS_URL_PREFIX
    if not prefix.startswith("/"):
        prefix = "/" + prefix
    if not prefix.endswith("/"):
        prefix = prefix + "/"
    return f"{base}{prefix}{filename}"
