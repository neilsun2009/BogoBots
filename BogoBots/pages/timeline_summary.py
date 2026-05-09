# BogoBots/pages/timeline_summary.py
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st

from BogoBots.configs.access import access_level
from BogoBots.configs.models import available_models
from BogoBots.configs.public_urls import transcription_pdf_public_url
from BogoBots.utils.mineru_cloud_utils import mineru_extract_pdf_url
from BogoBots.utils.report_render_utils import markdown_to_html
from BogoBots.utils.router import render_toc
from BogoBots.utils.llm_utils import _chat_completion, get_model_price
from BogoBots.utils.streamlit_utils import render_unlock_form

st.set_page_config(
    page_title="Timeline Summary | BogoBots",
    page_icon="📝",
    layout="wide",
)

TIMELINE_FROM_DOC_DEFAULT = """You are given document text extracted from a PDF (often a transcript). Produce a detailed markdown timeline summary in a markdown table format in the original language, in chronological order. For each segment or time block where the source allows, include **Topic**, **Speaker** (if identifiable; otherwise "—" or omit), and **Summary** of what was said in separate columns. Use time references when present in the source. Do not translate to Chinese.

Document (markdown):
{document_markdown}

Timeline summary:"""

STATIC_TRANSCRIPTIONS_DIR = Path("static") / "transcriptions"


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _safe_pdf_filename(original_name: str) -> str:
    stem = Path(original_name).stem
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", stem).strip("._")[:80] or "upload"
    return f"{uuid.uuid4().hex[:12]}_{stem}.pdf"


def _flatten_openrouter_models():
    opts = []
    for group in available_models:
        for model in group["models"]:
            opts.append(f"{group['open_router_prefix']}/{model['api_name']}")
    return opts


with st.sidebar:
    render_toc()
    st.divider()
    access = st.session_state.get("access_level", 0)
    if access >= access_level["admin"]:
        st.success("Admin access granted")
    elif access >= access_level["vip"]:
        st.info("VIP access")
    elif access >= access_level["friend"]:
        st.info("Friend access")
        # render_unlock_form()
    else:
        st.warning("Visitor access - some features limited")
        render_unlock_form()

st.title("📝 Transcription timeline summary")

is_friend = st.session_state.get("access_level", 0) >= access_level["friend"]

if not is_friend:
    st.warning("Friend access required. Unlock with the friend PIN in the sidebar.")
    st.stop()

model_options = _flatten_openrouter_models()
default_model = "openai/gpt-oss-120b"
if default_model not in model_options and model_options:
    default_model = model_options[0]

uploaded = st.file_uploader("PDF", type=["pdf"], label_visibility="collapsed")

if uploaded is not None:
    upload_sig = (uploaded.name, uploaded.size)
    if st.session_state.get("ts_upload_sig") != upload_sig:
        STATIC_TRANSCRIPTIONS_DIR.mkdir(parents=True, exist_ok=True)
        fname = _safe_pdf_filename(uploaded.name)
        dest = STATIC_TRANSCRIPTIONS_DIR / fname
        dest.write_bytes(uploaded.getvalue())
        st.session_state["ts_upload_sig"] = upload_sig
        st.session_state["ts_saved_name"] = fname
        st.session_state["ts_saved_path"] = str(dest)
        st.session_state["ts_public_url"] = transcription_pdf_public_url(fname)
        st.session_state["ts_original_name"] = uploaded.name
        for k in ("ts_extracted_md", "ts_timeline_md", "ts_logs", "ts_tokens"):
            st.session_state.pop(k, None)

    st.subheader("Preview")
    st.pdf(uploaded.getvalue(), height=600)

    st.markdown(
        f"**Saved file:** `{st.session_state['ts_saved_name']}`  \n"
        f"**Public URL (for MinerU):** `{st.session_state['ts_public_url']}`"
    )

    with st.expander("Parameters", icon=":material/settings:", expanded=True):
        st.selectbox(
            "OCR / extraction",
            options=["MinerU (cloud URL)"],
            index=0,
            disabled=True,
        )
        # extract_model = st.selectbox(
        #     "MinerU extract model",
        #     options=["vlm", "pipeline", "html"],
        #     index=0,
        #     help="Forwarded to mineru-open-sdk `extract()`.",
        # )
        # ocr_enabled = st.checkbox("MinerU OCR", value=True)
        # mineru_timeout = st.slider("MinerU timeout (seconds)", 60, 1800, 600, 30)

        llm_model = st.selectbox(
            "Timeline LLM",
            options=model_options,
            index=model_options.index(default_model) if default_model in model_options else 0,
            key="ts_llm_model",
        )
        price = get_model_price(llm_model, "OpenRouter")
        if price:
            st.caption("Model pricing")
            st.json(price)
        prompt_template = st.text_area(
            "LLM prompt",
            value=TIMELINE_FROM_DOC_DEFAULT,
            height=260,
            help="Include the placeholder {document_markdown}.",
        )
        temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.05)

    log_exp = st.expander("Process log", icon=":material/code:", expanded=False)
    log_ph = log_exp.empty()
    logs = st.session_state.get("ts_logs") or []
    log_ph.code("\n".join(logs[-300:]) if logs else "(no run yet)")

    if st.button("Run it!", icon=":material/play_arrow:", type="primary"):
        logs = []
        st.session_state["ts_logs"] = logs

        def progress(msg: str) -> None:
            logs.append(f"[{_utc_ts()}] {msg}")
            st.session_state["ts_logs"] = list(logs)
            log_ph.code("\n".join(logs[-300:]))

        token = st.secrets.get("mineru_token", "") or ""
        if not str(token).strip():
            progress("ERROR: st.secrets['mineru_token'] is missing or empty")
            st.error("Set `mineru_token` in Streamlit secrets.")
        elif "{document_markdown}" not in prompt_template:
            progress("ERROR: prompt must contain {document_markdown}")
            st.error("Prompt must include `{document_markdown}`.")
        else:
            try:
                with st.spinner("MinerU extracting PDF…"):
                    md, _imgs = mineru_extract_pdf_url(
                        st.session_state["ts_public_url"],
                        str(token).strip(),
                        progress_callback=progress,
                        extract_model='vlm',
                        ocr_enabled=False,
                        timeout=600,
                    )
                st.session_state["ts_extracted_md"] = md
                progress(f"Extracted markdown: {len(md)} characters")
                prompt = prompt_template.format(document_markdown=md)
                with st.spinner("LLM timeline summary…"):
                    timeline, inp_tok, out_tok = _chat_completion(
                        llm_model,
                        prompt,
                        temperature=temperature,
                    )
                st.session_state["ts_timeline_md"] = timeline
                st.session_state["ts_tokens"] = (inp_tok, out_tok)
                progress(f"LLM done: input_tokens={inp_tok} output_tokens={out_tok}")
                st.success("Done.")
            except TypeError as te:
                progress(f"ERROR (TypeError): {te!r}")
                st.error(f"MinerU extract call failed: {te}")
            except Exception as e:
                progress(f"ERROR: {e!r}")
                st.error(str(e))

        log_ph.code("\n".join((st.session_state.get("ts_logs") or [])[-300:]))

    if st.session_state.get("ts_extracted_md"):
        with st.expander("PDF extracted document (Markdown)", expanded=False):
            st.text_area(
                "extracted",
                value=st.session_state["ts_extracted_md"],
                height=400,
                disabled=True,
                label_visibility="collapsed",
            )

    if st.session_state.get("ts_timeline_md"):
        st.subheader("Timeline summary")
        with st.container(border=True):
            st.markdown(st.session_state["ts_timeline_md"])
        stem = Path(st.session_state.get("ts_saved_name", "timeline")).stem
        md_bytes = st.session_state["ts_timeline_md"].encode("utf-8")
        ex_bytes = (st.session_state.get("ts_extracted_md") or "").encode("utf-8")
        html_doc = markdown_to_html(st.session_state["ts_timeline_md"], "Timeline summary")
        # c1, c2, c3 = st.columns(3)
        # with c1:
        st.download_button(
            "Download HTML",
            html_doc.encode("utf-8"),
            icon=":material/html:",
            file_name=f"{stem}_timeline.html",
            mime="text/html",
        )
        st.download_button(
            "Download Markdown",
            md_bytes,
            icon=":material/markdown:",
            file_name=f"{stem}_timeline.md",
            mime="text/markdown",
        )
        # with c2:
            # st.download_button(
            #     "Download extracted (.md)",
            #     ex_bytes,
            #     file_name=f"{stem}_extracted.md",
            #     mime="text/markdown",
            # )
        
else:
    st.info("Upload a PDF to begin.")
