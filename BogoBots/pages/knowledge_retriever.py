import os
import sys
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from BogoBots.utils.router import render_toc
from BogoBots.utils.langchain import get_zilliz_vectorstore

st.set_page_config(
    page_title='Knowledge Retriever | BogoBots', 
    page_icon='👓'
)

with st.sidebar:
    render_toc()
    
def retrieve(query, top_k=5):
    vectorstore = get_zilliz_vectorstore()
    result_list = vectorstore.similarity_search_with_score(query, k=top_k)
    docs = list()
    for doc, score in result_list:
        doc.metadata["score"] = score
        docs.append(doc)
    return docs

st.header('👓Knowledge Retriever')

st.write('Retrieves knowledge from Bogo\'s knowledge base.')

with st.form('query_form'):
    query = st.text_input('Query')
    top_k = st.slider('Top K', value=10, min_value=1, max_value=20)
    # score_threshold = st.slider('Score Threshold', value=0.5, min_value=0.0, max_value=1.0, step=0.01)
    st.form_submit_button('Submit')

if query:
    with st.spinner('Retrieving results...'):
        docs = retrieve(query, top_k=top_k)
    st.write(f'{len(docs)} results retrieved')
    for idx, doc in enumerate(docs):
        metadata = doc.metadata
        with st.container(border=True):
            st.write(f'**#{idx+1}**')
            st.write(doc.page_content)
            st.caption(f"《{metadata['source']}》 {metadata['chapter']}")
            st.caption(f"Relevance score: {metadata['score']:.4f}")