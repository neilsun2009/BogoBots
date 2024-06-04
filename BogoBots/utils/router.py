import streamlit as st

from BogoBots.configs.access import access_level

PAGES = [
    {
        "label": "BogoChat",
        "icon": "🎭",
        "link": "BogoBots.py",
        "access": access_level['visitor'],
    },
    {
        "label": "Knowledge Retriever",
        "icon": "👓",
        "link": "pages/knowledge_retriever.py",
        "access": access_level['visitor'],
    },
    {
        "label": "Admin",
        "icon": "🔒",
        "link": "pages/admin.py",
        "access": access_level['admin'],
    },
]

def render_toc_with_expander():
    with st.expander("👻 **Meet all our agents**"):
        render_toc()
            
def render_toc():
    for page in PAGES:
        if st.session_state.get('access_level', 0) < page['access']:
            continue
        st.page_link(
            label=page['label'],
            icon=page['icon'],
            page=page['link'],
        )