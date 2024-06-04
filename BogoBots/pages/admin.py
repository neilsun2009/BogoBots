import os
import sys
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from BogoBots.configs.access import access_level
from BogoBots.utils.router import render_toc

st.set_page_config(
    page_title='Admin | BogoBots', 
    page_icon='🔒'
)

with st.sidebar:
    render_toc()


if st.session_state.get('access_level', 0) < access_level['admin']:
    st.button('Verify yourself!', on_click=lambda: st.session_state.update({'access_level': access_level['admin']}))
else:
    st.write('Hello, admin!')
    logout_clicked = st.button('Logout', type='primary', on_click=lambda: st.session_state.update({'access_level': access_level['visitor']}))