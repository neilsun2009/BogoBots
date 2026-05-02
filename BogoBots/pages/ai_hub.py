# BogoBots/pages/ai_hub.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import streamlit as st
from datetime import datetime, timedelta, timezone
import json

from BogoBots.configs.access import access_level
from BogoBots.configs.models import available_models
from BogoBots.utils.router import render_toc
from BogoBots.utils.streamlit_utils import render_unlock_form
from BogoBots.utils.llm_utils import (
    get_model_price,
    summarize_news_item,
    extract_metadata,
    _chat_completion,
    generate_podcast_transcript,
)
from BogoBots.utils.report_render_utils import (
    build_report_markdown,
    build_foreword_prompt,
    extract_foreword_preview,
    markdown_to_html,
)

from BogoBots.services.news_source_service import NewsSourceService
from BogoBots.services.news_item_service import NewsItemService
from BogoBots.services.news_report_service import NewsReportService

from BogoBots.models.news_hub_config import (
    NewsHubConfig,
)
from BogoBots.database.session import get_session
from BogoBots.crawlers.news_crawler import get_crawler_for_source

# Page config
st.set_page_config(
    page_title='AI News Hub | BogoBots',
    page_icon='📰',
    layout='wide'
)

st.title('📰 AI News Hub')


def format_episode_duration(seconds):
    if seconds is None:
        return ""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


@st.dialog("News Item Detail", width="large")
def show_news_item_modal(item_id: int):
    item = NewsItemService.get_item_by_id(item_id)
    if not item:
        st.error("Item not found")
        return

    # Opening details marks item as read automatically
    # if not item.is_read:
    #     NewsItemService.mark_item_read(item_id, is_read=True)
    #     item = NewsItemService.get_item_by_id(item_id)

    st.markdown(f"### {item.title}")
    st.write(f"**Source:** {item.source.name if item.source else 'Unknown'}")
    st.write(f"**Published:** {item.published_at}")
    st.write(f"**Link:** {item.url}")
    can_edit_admin_fields = st.session_state.get('access_level', 0) >= access_level['admin']

    if item.audio_url:
        st.audio(item.audio_url)
    if item.episode_duration_seconds:
        st.write(f"**Duration:** {format_episode_duration(item.episode_duration_seconds)}")
    if item.episode_description:
        with st.expander("Episode Description", expanded=False):
            st.markdown(item.episode_description)
    
    with st.expander("Raw content"):
        if item.audio_url: # podcast type
            progress_expander = st.expander("AI Podcast Transcription Progress", expanded=False)
            progress_placeholder = progress_expander.empty()
            progress_messages = []

            def podcast_progress(msg: str):
                progress_messages.append(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}")
                progress_placeholder.code("\n".join(progress_messages[-300:]))

            if st.button(
                "Generate AI Transcript",
                icon=":material/graphic_eq:",
                # type="tertiary",
                key=f"generate_podcast_transcript_{item_id}",
                disabled=not can_edit_admin_fields,
            ):
                try:
                    with st.spinner("Generating podcast transcript..."):
                        result = generate_podcast_transcript(item_id, progress_callback=podcast_progress)
                        model_name = item.summary_model or "openai/gpt-5.4-mini"
                        summarize_news_item(item_id, item.title, result.get("transcript", ""), model_name=model_name)
                    st.success("Podcast transcript generated and summary refreshed.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Podcast transcript generation failed: {e}")
            
        else: # plain news type
            if st.button("Retry Markdown via jina", 
                        icon=":material/restore_page:",
                        key=f"retry_jina_{item_id}",
                        disabled=not can_edit_admin_fields):
                source = item.source
                if source:
                    crawler = get_crawler_for_source(source)
                    if crawler:
                        new_markdown = crawler.get_full_content(item.url)
                        NewsItemService.update_item(item_id, content_raw=new_markdown)
                        st.success("Markdown refreshed from source implementation.")
                        st.rerun()
                    else:
                        st.warning("No crawler implementation available for this source.")
        st.text(item.content_raw or "")

    summary_text = st.text_area(
        "Summary",
        value=item.content_summary or "",
        key=f"summary_{item_id}",
        height=180,
        disabled=not can_edit_admin_fields,
        help="Admins can manually edit and save summary text."
    )
    
    a1, a2 = st.columns([1, 2])
    
    with a1:
        if st.button("Save Summary",
                icon=":material/save:",
                key=f"save_summary_{item_id}",
                type="tertiary",
                disabled=not can_edit_admin_fields):
            NewsItemService.update_item(item_id, content_summary=summary_text)
            st.success("Summary saved.")
            st.rerun()
    with a2:
        if st.button("Regenerate Summary", 
                    icon=":material/article_shortcut:",
                    type="tertiary",
                    key=f"regen_summary_{item_id}",
                    disabled=not can_edit_admin_fields):
            model_name = item.summary_model or "openai/gpt-5.4-mini"
            summarize_news_item(
                item_id,
                item.title,
                item.content_raw or item.episode_description or "",
                model_name=model_name,
            )
            # extract_metadata(item_id, item.title, item.content_raw or "", model_name=model_name)
            st.success("Summary regenerated.")
            st.rerun()

    remarks = st.text_area(
        "Remarks",
        value=item.remarks or "",
        key=f"remarks_{item_id}",
        disabled=not can_edit_admin_fields
    )

    a1, a2, a3 = st.columns(3)
    with a1:
        if st.button("Save Remarks", 
                    icon=":material/save:",
                    key=f"save_remarks_{item_id}",
                    disabled=not can_edit_admin_fields):
            NewsItemService.update_item(item_id, remarks=remarks)
            st.success("Remarks saved.")
            st.rerun()
        
    with a2:
        star_label = "Unstar" if item.is_starred else "Star"
        if st.button(star_label, 
                     icon="⭐" if item.is_starred else ":material/star:",
                     type="tertiary",
                     key=f"star_{item_id}",
                     disabled=not can_edit_admin_fields):
            NewsItemService.set_item_starred(item_id, is_starred=not item.is_starred)
            st.success("Star status updated.")
            st.rerun()
    with a3:
        archive_label = "Release Archive" if item.is_archived else "Move to Archive"
        if st.button(archive_label, 
                     icon=":material/archive:",
                     type="tertiary",
                     key=f"archive_{item_id}",
                     disabled=not can_edit_admin_fields):
            NewsItemService.set_item_archived(item_id, is_archived=not item.is_archived)
            st.success("Archive status updated.")
            st.rerun()  


@st.dialog("Edit News Source", width="large")
def show_source_edit_modal(source_id: int):
    source = NewsSourceService.get_source_by_id(source_id)
    if not source:
        st.error("Source not found")
        return

    st.markdown(f"### #{source.id} · {source.name}")
    edit_active = st.checkbox("Active", value=source.is_active, key=f"edit_active_{source_id}")
    edit_priority = st.selectbox(
        "Priority",
        ["high", "medium", "low"],
        index=["high", "medium", "low"].index(source.priority if source.priority in ["high", "medium", "low"] else "medium"),
        key=f"edit_priority_{source_id}",
    )
    edit_icon = st.text_input("Icon URL", value=source.icon or "", key=f"edit_icon_{source_id}")
    edit_url = st.text_input("Primary RSS URL", value=source.url or "", key=f"edit_url_{source_id}")
    edit_backup_url = st.text_input("Backup RSS URL", value=source.backup_url or "", key=f"edit_backup_url_{source_id}")

    if st.button("Test Connection", 
                 type="tertiary", 
                 icon=":material/cell_tower:",
                 key=f"modal_test_conn_{source_id}"):
        test_result = NewsSourceService.test_source_connection(
            source.source_type,
            edit_url,
            json.loads(source.config_json) if source.config_json else {},
        )
        if test_result.get("success"):
            st.success(test_result.get("message", "Connection OK"))
        else:
            st.error(test_result.get("message", "Connection failed"))
    col_save, col_delete = st.columns(2)
    with col_save:
        if st.button("Save Changes",
                     icon=":material/save:",
                     key=f"modal_save_source_{source_id}"):
            NewsSourceService.update_source(
                source_id,
                is_active=edit_active,
                priority=edit_priority,
                icon=edit_icon,
                url=edit_url,
                backup_url=edit_backup_url,
            )
            st.success("Updated!")
            st.rerun()

    with col_delete:
        if st.button("Delete Source", type="primary", 
                     icon=":material/delete:",
                     key=f"modal_delete_source_{source_id}"):
            if NewsSourceService.delete_source(source_id):
                st.success("Deleted!")
                st.rerun()
            else:
                st.error("Failed to delete source")


REPORT_CATEGORY_ORDER = ["Top Story", "New Release", "Deep Focus", "Trending", "Fun Stuff"]


def suggest_report_category(item) -> str:
    title = (item.title or "").lower()
    news_type = (item.source.news_type if item.source else "").lower()
    priority = (item.source.priority if item.source else "").lower()

    if priority == "high":
        return "New Release"
    if any(k in title for k in ["model", "checkpoint", "release", "weights", "llm"]):
        return "New Release"
    if any(k in title for k in ["paper", "research", "benchmark", "method", "survey"]):
        return "Deep Focus"
    return "Trending"


@st.dialog("Edit Report", width="large")
def show_report_edit_modal(report_id: int):
    report = NewsReportService.get_report_by_id(report_id)
    if not report:
        st.error("Report not found")
        return
    if st.session_state.get('access_level', 0) < access_level['admin']:
        st.warning("Admin access required.")
        return

    title = st.text_input("Report Title", value=report.title or "", key=f"modal_report_title_{report_id}")
    content = st.text_area("Markdown Content", value=report.content or "", height=360, key=f"modal_report_content_{report_id}")

    if st.button("Save Report", icon=":material/save:", key=f"modal_save_report_{report_id}"):
        NewsReportService.update_report(
            report_id,
            title=title,
            content=content,
        )
        st.success("Report updated.")
        st.rerun()

# Sidebar navigation
with st.sidebar:
    render_toc()
    st.divider()
    
    # Show current access level
    access = st.session_state.get('access_level', 0)
    if access >= access_level['admin']:
        st.success("Admin access granted")
    elif access >= access_level['friend']:
        st.info("Friend access")
        render_unlock_form()
    else:
        st.warning("Visitor access - some features limited")
        render_unlock_form()
        

# Main tabs
tab_news, tab_crawl, tab_report, tab_config = st.tabs(
    ["🆕 Latest News", "🔄 Crawling Status", "📬 Reports & Review", "⚙️ Config (Admin)", ]
)

# ============= LATEST NEWS TAB =============
with tab_news:
    st.subheader("Latest News Items")
    is_admin = st.session_state.get('access_level', 0) >= access_level['admin']

    all_sources = NewsSourceService.get_all_sources()
    source_name_to_id = {s.name: s.id for s in all_sources}
    available_news_types = sorted(list({s.news_type for s in all_sources if s.news_type}))

    filter_page_size = 20

    f1, f2, f3, f4 = st.columns([2, 2, 2, 2])
    with f1:
        filter_start_date = st.date_input(
            "From date",
            value=(datetime.now(timezone.utc) - timedelta(days=7)).date(),
            key="news_tab_from_date",
        )
        filter_title_query = st.text_input("Search", value="", key="news_tab_title_query",
                                           placeholder="Search keywords in title")
        
    with f2:
        filter_end_date = st.date_input(
            "To date",
            value=datetime.now(timezone.utc).date(),
            key="news_tab_to_date",
        )
        filter_sort_by = st.selectbox(
            "Sort by",
            options=["Date", "Priority"],
            index=0,
            key="news_tab_sort_by",
        )
    with f3:
        filter_news_types = st.multiselect(
            "News Types",
            options=available_news_types,
            default=[],
            key="news_tab_news_types",
        )
        filter_type = st.pills('Filter by', options=['Unread only', 'Star only'], key="news_tab_filter_type")
    with f4:
        filter_sources = st.multiselect(
            "Sources",
            options=list(source_name_to_id.keys()),
            default=[],
            key="news_tab_sources",
        )
        # filter_page_size = st.selectbox("Page size", [10, 20, 50], index=1, key="news_tab_page_size")
        

    def render_news_list(archived: bool, unread_only: bool):
        page_key = "news_tab_page_arch" if archived else "news_tab_page_imp"
        if page_key not in st.session_state:
            st.session_state[page_key] = 1
        current_page_input = int(st.session_state[page_key])

        query_result = NewsItemService.get_latest_ranked_items_paginated(
            page=current_page_input,
            page_size=filter_page_size,
            unread_only=unread_only,
            starred_only=(filter_type == 'Star only'),
            archived=archived,
            source_ids=[source_name_to_id[s] for s in filter_sources] if filter_sources else None,
            news_types=filter_news_types if filter_news_types else None,
            start_time=datetime.combine(filter_start_date, datetime.min.time()),
            end_time=datetime.combine(filter_end_date, datetime.max.time()),
            title_query=filter_title_query,
            sort_by=filter_sort_by,
        )

        items = query_result["items"]
        total = query_result["total"]
        total_pages = query_result["total_pages"]
        current_page = query_result["page"]

        def display_pagination(key_suffix: str='top'):
            prev_col, next_col = st.columns([1, 1])
            with prev_col:
                if st.button(
                    "Prev",
                    icon=":material/chevron_left:",
                    key=f"news_prev_{'arch' if archived else 'imp'}_{key_suffix}",
                    disabled=current_page <= 1,
                    use_container_width=True,
                ):
                    st.session_state[page_key] = max(1, current_page - 1)
                    st.rerun()
            with next_col:
                if st.button(
                    "Next",
                    icon=":material/chevron_right:",
                    icon_position="right",
                    key=f"news_next_{'arch' if archived else 'imp'}_{key_suffix}",
                    disabled=current_page >= total_pages,
                    use_container_width=True,
                ):
                    st.session_state[page_key] = min(total_pages, current_page + 1)
                    st.rerun()

            st.caption(f"Total {total} items | Page {current_page}/{total_pages}")

        
        if not items:
            st.info("No items found for current filters.")
        else:
            display_pagination()
            for item in items:
                source_priority = (item.source.priority if item.source else "medium").lower()
                priority_icon = "🔴" if source_priority == "high" else ("🟡" if source_priority == "medium" else "⚪")
                read_icon = "🆕" if not item.is_read else "✅"
                star_icon = "⭐" if item.is_starred else ""
                title_md = f"**{item.title}**" if not item.is_read else item.title
                item_scope = "arch" if archived else "imp"

                c1, c2, c3, c4 = st.columns([6, 1, 1, 1])
                with c1:
                    st.markdown(f"{read_icon} {priority_icon} {star_icon} {title_md}")
                    s_icon_col, s_text_col = st.columns([1, 11])
                    with s_icon_col:
                        if item.source and item.source.icon:
                            st.image(item.source.icon, width=60)
                        else:
                            st.caption("📰")
                    with s_text_col:
                        st.caption(f"{(item.content_summary or '').strip()[:400]}...")
                        if item.audio_url:
                            st.audio(item.audio_url)
                        # duration_text = format_episode_duration(item.episode_duration_seconds)
                        st.caption(
                            f"{item.source.name if item.source else 'Unknown'} | "
                            f"{item.source.news_type if item.source else 'N/A'} | "
                            f"{item.published_at.strftime('%Y-%m-%d %H:%M')}"
                            # f"{' | ' + duration_text if duration_text else ''}"
                        )
                with c2:
                    if st.button("Detail", 
                                 icon=":material/article:",
                                 type="tertiary",
                                 key=f"news_tab_detail_{item.id}_{item_scope}"):
                        show_news_item_modal(item.id)
                with c3:
                    if item.url:
                        st.link_button("Open link", 
                                       icon=":material/open_in_new:",
                                       type="tertiary",
                                       url=item.url)
                    if is_admin:
                        read_label = "Mark as Unread" if item.is_read else "Mark as Read"
                        if st.button(read_label, 
                                    icon=":material/mark_email_unread:" if item.is_read else ":material/mark_email_read:",
                                    type="tertiary",
                                    key=f"toggle_read_{item.id}_{item_scope}",
                                    disabled=not is_admin):
                            NewsItemService.mark_item_read(item.id, is_read=not item.is_read)
                            st.success("Read status updated.")
                            st.rerun()
                with c4:
                    if is_admin:
                        star_label = "Unstar" if item.is_starred else "Star"
                        if st.button(star_label, 
                                    icon="⭐" if item.is_starred else ":material/star:",
                                    type="tertiary",
                                    key=f"news_star_{item.id}_{item_scope}",
                                    disabled=not is_admin):
                            NewsItemService.set_item_starred(item.id, is_starred=not item.is_starred)
                            st.rerun()
                        arc_label = "Release" if item.is_archived else "Archive"
                        if st.button(arc_label, 
                                    icon=":material/archive:",
                                    type="tertiary",
                                    key=f"news_arc_{item.id}_{item_scope}",
                                    disabled=not is_admin):
                            NewsItemService.set_item_archived(item.id, is_archived=not item.is_archived)
                            st.rerun()
                if is_admin:
                    with st.expander("Edit Remark", expanded=False):
                        remark_text = st.text_area(
                            "Remark",
                            value=item.remarks or "",
                            key=f"news_tab_remark_{item.id}_{item_scope}",
                            height=100,
                            disabled=not is_admin,
                        )
                        remark_saved_key = f"news_tab_remark_saved_{item.id}_{item_scope}"
                        save_col, success_col = st.columns([1, 2])
                        with save_col:
                            if st.button(
                                "Submit Remark",
                                icon=":material/save:",
                                type="tertiary",
                                key=f"news_tab_remark_save_{item.id}_{item_scope}",
                                disabled=not is_admin,
                            ):
                                NewsItemService.update_item(item.id, remarks=remark_text)
                                st.session_state[remark_saved_key] = True
                                st.rerun()
                        with success_col:
                            if st.session_state.pop(remark_saved_key, False):
                                st.success("Remark updated.")
            display_pagination(key_suffix='bottom')

    latest_subtab_important, latest_subtab_archived = st.tabs(["Important", "Archived"])

    with latest_subtab_important:
        render_news_list(archived=False, unread_only=(filter_type == 'Unread only'))
    with latest_subtab_archived:
        render_news_list(archived=True, unread_only=(filter_type == 'Unread only'))

# ============= CONFIG TAB =============
with tab_config:
    if st.session_state.get('access_level', 0) < access_level['admin']:
        st.error("⚠️ Admin access required. Please unlock in the sidebar.")
    else:
        st.subheader("AI Hub Configuration")
        
        config_subtabs = st.tabs(["📡 Source Management", "🤖 LLM Configuration"])
        
        # --- Sub-tab 1: Source Management ---
        with config_subtabs[0]:
            st.subheader("News Sources")
            
            # Source list
            sources = sorted(NewsSourceService.get_all_sources(), key=lambda s: s.id)
            
            # Display sources in card layout
            if sources:
                source_cols = st.columns(3)
                for idx, s in enumerate(sources):
                    with source_cols[idx % 3]:
                        with st.container(border=True):
                            c_icon, c_main = st.columns([1, 5])
                            with c_icon:
                                if s.icon:
                                    st.image(s.icon, width=44)
                                else:
                                    st.markdown("### 📰")
                            with c_main:
                                icon = "✅" if s.is_active else "⏸️"
                                st.markdown(f"**{icon} #{s.id} · {s.name}**")
                                st.caption(f"{s.source_type} / {s.news_type} · Priority: {s.priority}")
                                st.caption(
                                    "Last crawl: "
                                    + (s.last_crawled_at.strftime("%Y-%m-%d %H:%M") if s.last_crawled_at else "Never")
                                )
                                url_caption = f"Primary: {s.url}"
                                if s.backup_url:
                                    url_caption += f"\n\nBackup: {s.backup_url}"
                                st.caption(url_caption)
                                if s.last_error:
                                    st.error(f"Recent error: {s.last_error}")
                                if st.button(
                                    "Edit",
                                    icon=":material/edit:",
                                    type="tertiary",
                                    key=f"open_edit_source_{s.id}",
                                ):
                                    show_source_edit_modal(s.id)
            else:
                st.info("No sources configured yet. Add your first source below.")
            
            # Add new source
            st.divider()
            st.subheader("Add Source")

            with st.expander("➕ Add New Source", expanded=True):
                new_name = st.text_input("Source Name", placeholder="e.g., OpenAI Blog")
                new_source_type = st.selectbox("Source Type", options=["RSS", "Podcast"], index=0)
                new_news_type = st.selectbox(
                    "News Type",
                    options=["AI Company", "Media", "Blog", "Podcast"],
                    index=0,
                    help="Semantic news category. Additional integration config can be saved in config_json."
                )
                new_url = st.text_input("Source URL", placeholder="https://...")
                new_backup_url = st.text_input("Backup RSS URL (optional)", placeholder="https://...")
                new_icon = st.text_input("Icon URL (optional)", placeholder="https://.../icon.png")
                new_priority = st.selectbox("Priority", options=["high", "medium", "low"], index=1)
                # new_schedule = st.text_input("Cron Schedule", value="0 0 * * *",
                #                              help="Format: min hour day month weekday")
                
                # news_type-specific extension space
                new_config = {}
                new_config["news_type"] = new_news_type
                if new_news_type == "twitter":
                    new_config["env_keys"] = {
                        "api_key": "TWITTER_API_KEY",
                        "api_secret": "TWITTER_API_SECRET",
                        "bearer_token": "TWITTER_BEARER_TOKEN"
                    }
                    st.caption("Twitter keys are read from environment/secrets; placeholders saved in config.")
                elif new_news_type == "github":
                    new_config["env_keys"] = {"api_key": "GITHUB_API_TOKEN"}
                    st.caption("GitHub token is read from environment/secrets; placeholder saved in config.")
                
                if st.button("Test Connection", type="tertiary",
                             icon=":material/cell_tower:",):
                    if new_url:
                        result = NewsSourceService.test_source_connection(new_source_type, new_url, new_config)
                        if result['success']:
                            st.success(result['message'])
                        else:
                            st.error(result['message'])
                    else:
                        st.warning("Please enter a URL first")
                
                if st.button("Add Source", 
                             icon=":material/add:",
                             type="primary"):
                    if new_name and new_url:
                        try:
                            source = NewsSourceService.create_source(
                                name=new_name,
                                source_type=new_source_type,
                                news_type=new_news_type,
                                url=new_url,
                                backup_url=new_backup_url,
                                config=new_config,
                                icon=new_icon,
                                priority=new_priority,
                                # crawl_schedule=new_schedule,
                                is_active=True
                            )
                            st.success(f"Source '{new_name}' added successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error adding source: {e}")
                    else:
                        st.error("Name and URL are required")
        
        # --- Sub-tab 2: LLM Configuration ---
        with config_subtabs[1]:
            st.subheader("LLM Configuration for AI Hub")
            
            session = get_session()
            try:
                config = NewsHubConfig.get_or_create(session)
                
                # Build model options from BogoBots config
                model_options = []
                for group in available_models:
                    for model in group['models']:
                        model_options.append(f"{group['open_router_prefix']}/{model['api_name']}")
                
                audio_model_options = []
                for group in available_models:
                    for model in group['models']:
                        if model.get('supports_audio_input', False):
                            audio_model_options.append(f"{group['open_router_prefix']}/{model['api_name']}")

                # Row 1: Summary
                st.markdown("### Summary")
                s_left, s_right = st.columns([1, 1])
                with s_left:
                    summary_model = st.selectbox(
                        "Summary model",
                        options=model_options,
                        index=model_options.index(config.default_summary_model) if config.default_summary_model in model_options else 0
                    )
                    summary_price = get_model_price(summary_model, 'OpenRouter')
                    if summary_price:
                        st.caption("Summary model price")
                        st.json(summary_price)
                    else:
                        st.caption("Summary model price unavailable")
                    # max_tokens = st.slider("Summary max tokens", 50, 500, int(config.max_summary_tokens or 200))
                    # relevance_threshold = st.slider(
                    #     "Relevance threshold",
                    #     0.0,
                    #     1.0,
                    #     float(getattr(config, "relevance_threshold", 0.3) or 0.3),
                    #     0.05,
                    # )
                with s_right:
                    summary_template = st.text_area(
                        "Summary prompt template",
                        value=config.summary_prompt_template,
                        height=190,
                        help="Use {title} and {content} as placeholders"
                    )

                # Row 2: Foreword
                st.markdown("### Foreword")
                f_left, f_right = st.columns([1, 1])
                with f_left:
                    foreword_model = st.selectbox(
                        "Foreword model",
                        options=model_options,
                        index=model_options.index(getattr(config, "foreword_model", "openai/gpt-5.4-mini"))
                        if getattr(config, "foreword_model", "openai/gpt-5.4-mini") in model_options else 0,
                    )
                    foreword_price = get_model_price(foreword_model, 'OpenRouter')
                    if foreword_price:
                        st.caption("Foreword model price")
                        st.json(foreword_price)
                    # foreword_max_tokens = st.slider(
                    #     "Foreword max tokens",
                    #     min_value=100,
                    #     max_value=3000,
                    #     value=int(getattr(config, "foreword_max_tokens", 400) or 400),
                    #     step=50,
                    # )
                with f_right:
                    foreword_template = st.text_area(
                        "Foreword prompt template",
                        value=getattr(config, "foreword_prompt_template", "") or "",
                        height=190,
                        help="Use {title}, {start_date}, {end_date}, {articles_by_category}."
                    )

                # Row 3: Translation
                st.markdown("### Translation")
                t_left, t_right = st.columns([1, 1])
                with t_left:
                    translation_model = st.selectbox(
                        "Translation model",
                        options=model_options,
                        index=model_options.index(getattr(config, "translation_model", "openai/gpt-5.4-mini"))
                        if getattr(config, "translation_model", "openai/gpt-5.4-mini") in model_options else 0,
                    )
                    translation_price = get_model_price(translation_model, 'OpenRouter')
                    if translation_price:
                        st.caption("Translation model price")
                        st.json(translation_price)
                    # translation_max_tokens = st.slider(
                    #     "Translation max tokens",
                    #     min_value=500,
                    #     max_value=10000,
                    #     value=int(getattr(config, "translation_max_tokens", 5000) or 5000),
                    #     step=100,
                    # )
                with t_right:
                    translation_template = st.text_area(
                        "Translation prompt template",
                        value=getattr(config, "translation_prompt_template", ""),
                        height=190,
                        help="Use {title}, {start_date}, {end_date}, {content}."
                    )

                # Row 4: Podcast transcription
                st.markdown("### Podcast Transcription")
                p_left, p_right = st.columns([1, 1])
                with p_left:
                    podcast_transcription_model = st.selectbox(
                        "Podcast transcription model",
                        options=audio_model_options,
                        index=audio_model_options.index(getattr(config, "podcast_transcription_model", "xiaomi/mimo-v2.5"))
                        if getattr(config, "podcast_transcription_model", "xiaomi/mimo-v2.5") in audio_model_options else 0,
                    )
                    podcast_price = get_model_price(podcast_transcription_model, 'OpenRouter')
                    if podcast_price:
                        st.caption("Podcast transcription model price")
                        st.json(podcast_price)
                with p_right:
                    podcast_first_prompt = st.text_area(
                        "Podcast first chunk prompt",
                        value=(
                            getattr(config, "podcast_transcription_first_prompt_template", None)
                        ),
                        height=220,
                        help="Use {chunk_number}, {total_chunks}, {start_time}, {end_time}, {episode_description}."
                    )
                    podcast_followup_prompt = st.text_area(
                        "Podcast follow-up chunk prompt",
                        value=(
                            getattr(config, "podcast_transcription_followup_prompt_template", None)
                        ),
                        height=280,
                        help="Use {chunk_number}, {total_chunks}, {start_time}, {end_time}, {episode_description}, {speaker_context}."
                    )
                
                if st.button("Save LLM Configuration", type="primary"):
                    config.default_summary_model = summary_model
                    config.summary_prompt_template = summary_template
                    config.report_prompt_template = foreword_template
                    config.foreword_prompt_template = foreword_template
                    config.translation_prompt_template = translation_template
                    config.foreword_model = foreword_model
                    # config.foreword_max_tokens = foreword_max_tokens
                    config.translation_model = translation_model
                    config.podcast_transcription_model = podcast_transcription_model
                    config.podcast_transcription_first_prompt_template = podcast_first_prompt
                    config.podcast_transcription_followup_prompt_template = podcast_followup_prompt
                    # config.translation_max_tokens = translation_max_tokens
                    # config.max_summary_tokens = max_tokens
                    # config.relevance_threshold = relevance_threshold
                    config.updated_at = datetime.now(timezone.utc)
                    session.commit()
                    st.success("Configuration saved!")
            
            finally:
                session.close()

# ============= CRAWL TAB =============
with tab_crawl:
    st.subheader("Crawling Status")
    
    sources = NewsSourceService.get_all_sources()
    active_sources = [s for s in sources if s.is_active]
    
    # Summary stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Sources", len(sources))
    with col2:
        st.metric("Active Sources", len(active_sources))
    with col3:
        # Get recent items count
        recent_items = NewsItemService.get_items_by_date_range(
            datetime.now(timezone.utc) - timedelta(days=1),
            datetime.now(timezone.utc)
        )
        st.metric("Items (24h)", len(recent_items))
    with col4:
        # Status breakdown
        status_counts = NewsItemService.get_item_count_by_status()
        st.metric("New Items", status_counts.get('new', 0))
    
    st.divider()
    
    # Source status table
    st.subheader("Source Status")
    if sources:
        source_status_cols = st.columns(3)
        for idx, source in enumerate(sorted(sources, key=lambda s: s.id)):
            with source_status_cols[idx % 3]:
                with st.container(border=True):
                    c_icon, c_main = st.columns([1, 5])
                    with c_icon:
                        if source.icon:
                            st.image(source.icon, width=44)
                        else:
                            st.markdown("### 📰")
                    with c_main:
                        icon = "✅" if source.is_active else "⏸️"
                        st.markdown(f"**{icon} #{source.id} · {source.name}**")
                        st.caption(f"{source.source_type} / {source.news_type} · Priority: {source.priority}")
                        st.caption(
                            "Last crawl: "
                            + (source.last_crawled_at.strftime("%Y-%m-%d %H:%M") if source.last_crawled_at else "Never")
                        )
                        st.caption(f"Primary: {source.url}")
                        if source.backup_url:
                            st.caption(f"Backup: {source.backup_url}")
                        if source.last_error:
                            st.error(f"Error: {source.last_error[:80]}")
    else:
        st.info("No sources configured. Go to Config tab to add sources.")
    
    # Manual crawl section (must be admin, placed at end of page)
    st.divider()
    st.subheader("Manual Crawl")
    if st.session_state.get('access_level', 0) >= access_level['admin']:
        st.caption("Crawl from selected date (00:00:00) until now.")

        crawl_col1, crawl_col2 = st.columns([2, 3])
        with crawl_col1:
            crawl_from_date = st.date_input(
                "From Date",
                value=(datetime.now(timezone.utc) - timedelta(days=1)).date(),
                key="manual_crawl_from_date"
            )

        manual_since = datetime.combine(crawl_from_date, datetime.min.time())

        source_options = {f"{s.name} ({s.news_type})": s.id for s in active_sources}
        selected_source_label = st.multiselect(
            "Select Active Sources",
            options=list(source_options.keys()) if source_options else [],
            key="manual_multiple_sources"
        ) if source_options else None

        progress_expander = st.expander("Crawl Progress Log", expanded=False)
        progress_placeholder = progress_expander.empty()
        progress_messages = []

        def ui_progress(msg: str):
            progress_messages.append(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}")
            progress_placeholder.code("\n".join(progress_messages[-300:]))

        action_col1, action_col2 = st.columns([1, 1])
        with action_col1:
            if st.button("🔄 Crawl Selected Source", type="secondary", disabled=not bool(source_options)):
                selected_ids = [source_options[label] for label in selected_source_label] if selected_source_label else []
                if not selected_ids:
                    st.warning("Please select at least one source.")
                for source_id in selected_ids:
                    source = next((s for s in active_sources if s.id == source_id), None)
                    if source:
                        with st.spinner(f"Crawling {source.name}..."):
                            crawler = get_crawler_for_source(source, progress_callback=ui_progress)
                            if crawler:
                                stats = crawler.crawl_with_retry(
                                    since=manual_since,
                                    max_attempts=3,
                                    retry_interval_seconds=3,
                                )
                                st.success(f"{source.name}: {stats['saved']} saved, {stats['duplicates']} dupes")
                            else:
                                st.warning(f"No crawler available for {source.source_type}")
                    else:
                        st.warning("Selected source is unavailable.")
                if selected_ids:
                    st.rerun()

        with action_col2:
            if st.button("🚀 Crawl All Active Sources", type="primary", disabled=not bool(active_sources)):
                results = []
                progress = st.progress(0)
                for idx, source in enumerate(active_sources):
                    crawler = get_crawler_for_source(source, progress_callback=ui_progress)
                    if crawler:
                        stats = crawler.crawl_with_retry(
                            since=manual_since,
                            max_attempts=3,
                            retry_interval_seconds=3,
                        )
                        results.append(f"{source.name}: {stats['saved']} saved")
                    progress.progress((idx + 1) / len(active_sources))

                st.success("Crawl complete!")
                for r in results:
                    st.write(r)
                st.rerun()
    else:
        st.info("Admin access required for manual crawl.")

# ============= REPORT TAB =============
with tab_report:
    st.header("AI News Reports")
    
    reports = NewsReportService.get_all_reports(limit=10)
    is_admin = st.session_state.get('access_level', 0) >= access_level['admin']
    
    # Report generation section
    st.subheader("Generate New Report")
    if not is_admin:
        st.info("Admin access required for report generation.")
    else:
        cfg_session = get_session()
        try:
            report_cfg = NewsHubConfig.get_or_create(cfg_session)
            foreword_prompt_template = (getattr(report_cfg, "foreword_prompt_template", "") or "").strip()
            translation_prompt_template = (getattr(report_cfg, "translation_prompt_template", "") or "").strip()
            foreword_model = (getattr(report_cfg, "foreword_model", "") or "openai/gpt-5.4-mini").strip()
            translation_model = (getattr(report_cfg, "translation_model", "") or "openai/gpt-5.4-mini").strip()
            foreword_max_tokens = int(getattr(report_cfg, "foreword_max_tokens", 400) or 400)
            translation_max_tokens = int(getattr(report_cfg, "translation_max_tokens", 5000) or 5000)
        finally:
            cfg_session.close()

        col1, col2, col3 = st.columns(3)
        with col1:
            report_date = st.date_input("Report Date", datetime.now(timezone.utc).date())
        with col2:
            start_date = st.date_input("News From", datetime.now(timezone.utc).date() - timedelta(days=7))
        with col3:
            end_date = st.date_input("News To", datetime.now(timezone.utc).date())

        report_title = st.text_input(
            "Report Title",
            value=f"AI News Weekly Report ({start_date} to {end_date})"
        )

        # Candidate items (starred only), display by published date ASC.
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        candidate_items = sorted(
            NewsItemService.get_starred_items_for_report(start_dt, end_dt),
            key=lambda i: i.published_at
        )

        st.write(f"Found {len(candidate_items)} starred candidate items")

        selected_entries = []
        if candidate_items:
            st.write("**Select starred items to include:**")
            for item in candidate_items:
                default_cat = suggest_report_category(item)
                col_check, col_info, col_cat, col_rank = st.columns([1, 16, 4, 1])
                with col_check:
                    include = st.checkbox("Include", key=f"include_{item.id}", value=True, label_visibility="collapsed")
                with col_info:
                    st.write(f"⭐ **{item.title}**")
                    s_icon_col, s_text_col = st.columns([1, 14])
                    with s_icon_col:
                        if item.source and item.source.icon:
                            st.image(item.source.icon, width=40)
                        else:
                            st.caption("📰")
                    with s_text_col:
                        if item.content_summary:
                            st.caption(item.content_summary[:400])
                        st.caption(
                            f"{item.source.name if item.source else 'Unknown'} | "
                            f"{item.source.news_type if item.source else 'N/A'} | "
                            f"{item.published_at.strftime('%Y-%m-%d %H:%M')}"
                        )
                with col_cat:
                    category = st.selectbox(
                        "Category",
                        options=REPORT_CATEGORY_ORDER,
                        index=REPORT_CATEGORY_ORDER.index(default_cat),
                        key=f"report_cat_{item.id}",
                        label_visibility="collapsed",
                    )
                with col_rank:
                    rank = st.number_input(
                        "Rank",
                        min_value=1,
                        value=1,
                        step=1,
                        key=f"report_rank_{item.id}",
                        label_visibility="collapsed",
                    )
                if include:
                    selected_entries.append({"item": item, "category": category, "rank": int(rank)})
        else:
            st.info("No starred items in range. Star items in Latest News first.")

        st.markdown("---")

        foreword_key = "report_foreword_text"
        if foreword_key not in st.session_state:
            st.session_state[foreword_key] = ""
        if selected_entries and st.button("✨ Generate Foreword by AI", type="tertiary"):
            if not foreword_prompt_template:
                st.warning("Foreword prompt template is empty. Please configure it in Config > LLM Configuration.")
            else:
                prompt = build_foreword_prompt(
                    report_title,
                    start_date,
                    end_date,
                    selected_entries,
                    template=foreword_prompt_template,
                    category_order=REPORT_CATEGORY_ORDER,
                )
                generated, _, _ = _chat_completion(
                    foreword_model,
                    prompt,
                    # max_tokens=foreword_max_tokens,
                    temperature=0.5
                )
                st.session_state[foreword_key] = generated.strip()
                st.rerun()

        foreword_text = st.text_area("Foreword by Editor", height=120, key=foreword_key)

        if selected_entries and st.button("Generate Report", type="primary", icon=":material/article:"):
            with st.spinner("Generating report..."):
                selected_entries_sorted = sorted(
                    selected_entries,
                    key=lambda x: (REPORT_CATEGORY_ORDER.index(x["category"]), x["rank"], x["item"].published_at),
                )
                report_markdown = build_report_markdown(
                    report_title,
                    start_date,
                    end_date,
                    foreword_text,
                    selected_entries_sorted,
                    category_order=REPORT_CATEGORY_ORDER,
                )
                selected_ids = [e["item"].id for e in selected_entries_sorted]
                item_meta = {
                    e["item"].id: {"category": e["category"], "category_rank": e["rank"]}
                    for e in selected_entries_sorted
                }
                report = NewsReportService.create_report(
                    report_date=datetime.combine(report_date, datetime.min.time()),
                    title=report_title,
                    editorial=foreword_text or None,
                    content=report_markdown,
                    summary=report_markdown,
                    news_items=selected_ids,
                    news_from=start_dt,
                    news_to=end_dt,
                    item_meta=item_meta,
                )
                st.success(f"Report created!")
                st.rerun()
    
    # Existing reports
    st.subheader("Existing Reports")
    
    if reports:
        for report in reports:
            with st.expander(report.title):
                report_md = report.content or report.summary or ""
                foreword_preview = extract_foreword_preview(report_md)
                
                dl1, dl2 = st.columns([6, 2])
                
                with dl1:
                    st.caption(
                        f"Coverage: {(report.news_from.strftime('%Y-%m-%d') if report.news_from else '?')} "
                        f"to {(report.news_to.strftime('%Y-%m-%d') if report.news_to else '?')}"
                        f" | Items: {report.news_count}"
                    )
                    st.write(foreword_preview or report.editorial)

                if is_admin:
                    a1, a2 = st.columns(2)
                    with dl2:
                        if st.button("Edit", type="tertiary", 
                                     icon=":material/edit:",
                                     key=f"edit_modal_report_{report.id}"):
                            show_report_edit_modal(report.id)
                with dl2:
                    st.download_button(
                        "Download Markdown",
                        icon=":material/markdown:",
                        type="tertiary",
                        data=report_md.encode("utf-8"),
                        file_name=f"ai_report_{report.id}.md",
                        mime="text/markdown",
                        key=f"download_md_{report.id}",
                    )
                    report_html = markdown_to_html(report_md, report.title or "AI Report")
                    st.download_button(
                        "Download HTML",
                        icon=":material/web:",
                        type="tertiary",
                        data=report_html.encode("utf-8"),
                        file_name=f"{report.title}.html",
                        mime="text/html",
                        key=f"download_html_{report.id}",
                    )
                    if is_admin and st.button(
                        "Delete",
                        icon=":material/delete:",
                        type="tertiary",
                        key=f"delete_report_{report.id}",
                    ):
                        if NewsReportService.delete_report(report.id):
                            st.success("Report deleted.")
                            st.rerun()
                        else:
                            st.error("Failed to delete report.")
                if is_admin and getattr(report, "language", "original") != "cn":
                    with dl2:
                        st.markdown('---')
                        zh_default_title = (
                            f"AI新闻周报（{(report.news_from.strftime('%Y-%m-%d') if report.news_from else report.report_date.strftime('%Y-%m-%d'))}"
                            f" - {(report.news_to.strftime('%Y-%m-%d') if report.news_to else report.report_date.strftime('%Y-%m-%d'))}）"
                        )
                        zh_title = st.text_input(
                            "Chinese report title",
                            value=zh_default_title,
                            key=f"zh_title_{report.id}",
                        )
                        if st.button("Translate to Chinese by AI", icon=":material/translate:", type="secondary", key=f"translate_report_{report.id}"):
                            if not translation_prompt_template:
                                st.warning("Translation prompt template is empty. Please configure it in Config > LLM Configuration.")
                            else:
                                with st.spinner("Translating report..."):
                                    report_for_translate = NewsReportService.get_report_by_id(report.id)
                                    report_items_for_translate = (report_for_translate.items if report_for_translate else []) or []
                                    start_str = report.news_from.strftime('%Y-%m-%d') if report.news_from else report.report_date.strftime('%Y-%m-%d')
                                    end_str = report.news_to.strftime('%Y-%m-%d') if report.news_to else report.report_date.strftime('%Y-%m-%d')
                                    translate_prompt = translation_prompt_template.format(
                                        title=report.title or "",
                                        start_date=start_str,
                                        end_date=end_str,
                                        content=report_md,
                                    )
                                    zh_content, _, _ = _chat_completion(
                                        translation_model,
                                        translate_prompt,
                                        # max_tokens=15000,
                                        temperature=0.5
                                    )
                                    translated = NewsReportService.create_report(
                                        report_date=report.report_date,
                                        title=zh_title,
                                        editorial=report.editorial,
                                        content=zh_content,
                                        summary=zh_content,
                                        news_items=[ri.news_item_id for ri in report_items_for_translate],
                                        news_from=report.news_from,
                                        news_to=report.news_to,
                                        item_meta={
                                            ri.news_item_id: {
                                                "category": ri.category,
                                                "category_rank": ri.category_rank or 1
                                            } for ri in report_items_for_translate
                                        },
                                        language="cn",
                                    )
                                    st.success(f"Chinese report generated!")
                                    st.rerun()
    else:
        st.info("No reports generated yet.")
