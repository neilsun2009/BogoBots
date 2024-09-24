import os
import sys
import streamlit as st
import traceback
import time
import json
from io import StringIO
from langchain_openai.chat_models.base import ChatOpenAI
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from BogoBots.database.session import get_session
from BogoBots.models.book import Book
from BogoBots.utils.router import render_toc
from BogoBots.configs import embedding as embedding_config
from BogoBots.document_loaders.weread_loader import WeReadLoader
from BogoBots.utils.embedding_utils import get_zilliz_vectorstore, get_embeddings
from BogoBots.utils.misc import (get_book_cover_from_douban, upload_image_to_imgur,
                                get_image_bytes_from_url)

st.set_page_config(
    page_title='Book Manager | BogoBots', 
    page_icon='📚'
)

with st.sidebar:
    render_toc()
    
st.title('📚 Book Manager')

BOOK_LIST_COLUMNS = 2
EMBEDDING_BATCH_SIZE = 64
DEFAULT_COVER_URL = 'https://hatscripts.github.io/circle-flags/flags/xx.svg'

# dialogs
@st.dialog('Add a book', width='large')
def add_book(title, authors, source_type, language, book_notes_file):
    if book_notes_file is None:
        raise ValueError('Please upload a book notes file')
    
    # ensure no title conflict
    with get_session() as session:
        if session.query(Book).filter(Book.name == title).first():
            raise ValueError('Book already exists')
    
    embedding_model = embedding_config.model_name
    summary_model = embedding_config.summarizer_model_name[language]
    new_book = Book(
                name=title,
                authors=authors.split(','),  # Assuming authors are comma-separated
                source_type=1 if source_type == 'WeRead' else 2,
                language=1 if language == 'cn' else 2,
                embedding_model=embedding_model,
                summary_model=summary_model
            )
    st_display_book_details(new_book, show_stats=False)
    
    # summarizer
    summarizer = ChatOpenAI(openai_api_base=embedding_config.summarizer_api_base[language],
                    openai_api_key=st.secrets['summarizer_key'], 
                    model_name=summary_model,
                    temperature=1,
                    streaming=False, 
                )
    summarizer = ChatPromptTemplate.from_template(embedding_config.summarizer_template[language]) | summarizer
    
    if source_type == 'WeRead':
        Loader = WeReadLoader
    else:
        raise ValueError(f"Unsupported book source type: {source_type}")
    
    book_notes_file_source = StringIO(book_notes_file.getvalue().decode("utf-8"))
    
    parsed_cache_file = f'static/parsed_cache/{title}.json'
    parsed_done_file = f'static/parsed_done/{title}.json'
    if not os.path.exists(os.path.dirname(parsed_cache_file)):
        os.makedirs(os.path.dirname(parsed_cache_file))
    if not os.path.exists(os.path.dirname(parsed_done_file)):
        os.makedirs(os.path.dirname(parsed_done_file))
    if os.path.exists(parsed_cache_file):
        read_cache = st.toggle('Read from cache', value=True)
    else:
        read_cache = False
    
    close_on_finish = st.toggle('Close on finish', value=False)
        
    placeholder = st.empty()
    confirm_btn = placeholder.button('Confirm')
    if confirm_btn:
        with placeholder.container():
            if read_cache:
                with open(parsed_cache_file, 'r', encoding='utf-8') as f:
                    docs = json.load(f)
                    new_book.num_notes = docs[-1]['metadata']['note_idx']
                    new_book.num_entries = len(docs)
            else:   
                with st.status('Parsing notes...', state='running', expanded=True) as status:
                    try:
                        load_ctn = st.container(height=200)
                        loader = Loader(book_notes_file_source, title, summarizer=summarizer, st_container=load_ctn)
                        docs = loader.load()
                        new_book.num_notes = loader.note_idx
                        new_book.num_entries = len(docs)
                        status.update(label=f'{len(docs)} notes parsed, {new_book.num_entries} entries', state='complete', expanded=False)
                    except Exception as e:
                        status.update(label='Error parsing notes', state='error')
                        st.write(f":red[An error occurred while parsing notes: {str(e)}]")
                        with st.container(height=200):
                            st.code(traceback.format_exc(), language='python')
                        st.stop()

                # write cache
                with open(parsed_cache_file, 'w', encoding='utf-8') as f:
                    json.dump([doc.dict() for doc in docs], f, ensure_ascii=False, indent=4)
            
            with st.status('Writing to database...', state='running', expanded=True) as status:
                try:
                    with get_session() as session:
                        session.add(new_book)
                        session.commit()
                    status.update(label='Database written', state='complete', expanded=False)
                    st.write(f"Book '{title}' has been added to the database.")
                except Exception as e:
                    status.update(label='Error writing to database', state='error')
                    st.write(f":red[An error occurred while writing to database: {str(e)}]")
                    with st.container(height=200):
                        st.code(traceback.format_exc(), language='python')
                    st.stop()

            vectorstore = get_zilliz_vectorstore()
            embeddings = get_embeddings()
            num_entries = len(docs)
            with st.status('Writing to vector store...', state='running', expanded=True) as status:
                try:
                    # progress_bar = st.progress(0, text=f'Progressing... {0}/{num_entries}')
                    batch_idx = 0
                    for i in range(0, len(docs), EMBEDDING_BATCH_SIZE):
                        batch_idx += 1
                        st.write(f'Progressing batch #{batch_idx}...')
                        batch = docs[i:i+EMBEDDING_BATCH_SIZE]
                        # parse to dict, because cached docs are dicts
                        if not isinstance(batch[0], dict):
                            batch = [doc.dict() for doc in batch]
                        content_batch = [doc["page_content"] for doc in batch]
                        summary_batch = [doc['metadata']['summary'] for doc in batch]
                        content_embeddings = embeddings.embed_documents(content_batch)  # replace with your embedding function
                        time.sleep(1)
                        summary_embeddings = embeddings.embed_documents(summary_batch)  # replace with your embedding function
                        # Write into vectorstore
                        vectorstore.insert(data=[
                            {
                                "text": doc['page_content'],
                                "summary": doc['metadata']['summary'][:100],
                                "source": doc['metadata']['source'],
                                "chapter": doc['metadata']['chapter'],
                                "note_idx": doc['metadata']['note_idx'],
                                "is_thought": doc['metadata']['is_thought'],
                                "text_vector": content_embeddings[j],
                                "summary_vector": summary_embeddings[j],
                            } for j, doc in enumerate(batch)
                        ])
                        # progress_bar.progress((i + 1) / num_entries, text=f'Progressing... {i + 1}/{num_entries}')
                    status.update(label='Vector store written', state='complete', expanded=False)
                    st.write(f'{len(docs)} entries written')
                except Exception as e:
                    status.update(label='Error writing to vector store', state='error')
                    st.write(f":red[An error occurred while writing to vector store: {str(e)}]")
                    with st.container(height=200):
                        st.code(traceback.format_exc(), language='python')
                    st.stop()
                    
            
        st.toast(f'Book {title} added!', icon='🍾')
        # delete cache
        os.rename(parsed_cache_file, parsed_done_file)
        if close_on_finish:
            time.sleep(1)
            st.rerun()

@st.dialog('Book details', width='large')
def show_book_details(book_id):
    with get_session() as session:
        book = session.query(Book).get(book_id)
        st_display_book_details(book)
        update_btn = st.button('Update')
        if update_btn:
            with st.status('Updating database...', state='running', expanded=True) as status:
                try:
                    session.commit()
                    session.refresh(book)
                    status.update(label='Database updated', state='complete', expanded=False)
                    st.write(f"Book '{book.name}' has been updated in database.")
                except Exception as e:
                    status.update(label='Error updating database', state='error')
                    st.write(f":red[An error occurred while updating database: {str(e)}]")
                    with st.container(height=200):
                        st.code(traceback.format_exc(), language='python')
    
        del_placeholder = st.empty()
        del_btn = del_placeholder.button('Delete', type='primary')
        if del_btn:
            with del_placeholder.container():
                with st.status('Deleting from vector store...', state='running', expanded=True) as status:
                    try:
                        vectorstore = get_zilliz_vectorstore()
                        del_result = vectorstore.delete(f'source == "{book.name}"')
                        status.update(label='Deleted from vector store', state='complete', expanded=False)
                        st.write(f'{del_result.delete_count} entries deleted')
                        st.write(f"Book '{book.name}' has been deleted from vector store.")
                    except Exception as e:
                        status.update(label='Error deleting from vector store', state='error')
                        st.write(f":red[An error occurred while deleting from vector store: {str(e)}]")
                        with st.container(height=200):
                            st.code(traceback.format_exc(), language='python')
                        st.stop()
                        
                with st.status('Deleting from database...', state='running', expanded=True) as status:
                    try:
                        session.delete(book)
                        session.commit()
                        status.update(label='Deleted from database', state='complete', expanded=False)
                        st.write(f"Book '{book.name}' has been deleted from database.")
                    except Exception as e:
                        status.update(label='Error deleting from database', state='error')
                        st.write(f":red[An error occurred while deleting from database: {str(e)}]")
                        with st.container(height=200):
                            st.code(traceback.format_exc(), language='python')
                        st.stop()
            
            st.toast('Book deleted!', icon='🗑️')
            time.sleep(1)
            st.rerun()

# db operations
def get_books():
    with get_session() as session:
        return session.query(Book).all()
    
def st_display_book_details(book: Book, show_stats=True):
    columns = st.columns([1, 2])
    with columns[0]:
        cover_placeholder = st.empty()
        if not book.cover_url:
            book.cover_url = get_book_cover_from_douban(book.name)
        if book.cover_url:
            cover_placeholder.image(get_image_bytes_from_url(book.cover_url),
                                    use_column_width=True)
        else:
            cover_placeholder.image(DEFAULT_COVER_URL, use_column_width=True)
    with columns[1]:
        st.write(f'**{book.name}** by {", ".join(book.authors)}')
        source_type = 'WeRead' if book.source_type == 1 else 'iReader'
        language = 'CN' if book.language == 1 else 'EN'
        st.write(f'`{source_type}` `{language}`')
        st.write(f'Embedding Model: `{book.embedding_model}`')
        st.write(f'Summary Model: `{book.summary_model}`')
        if show_stats:
            st.write(f'Notes: {book.num_notes} | Entries: {book.num_entries}')
        st.divider()
        uploaded_cover = st.file_uploader('Upload Cover', type=['jpg', 'png', 'jpeg', 'gif'])
        if uploaded_cover:
            book.cover_url = upload_image_to_imgur(uploaded_cover, book.name, f'Cover of {book.name}')
            cover_placeholder.image(get_image_bytes_from_url(book.cover_url),
                                    use_column_width=True)

# Add a book
st.subheader('Add a book')

with st.form('add_book_form', clear_on_submit=True):
    title = st.text_input('Title')
    authors = st.text_input('Authors', help='Separate authors with commas')
    source_type = st.radio('Source Type', ['WeRead', 'iReader'],
                           horizontal=True,
                        #    format_func=lambda x: 'WeRead' if x == 'weread' else 'iReader'
                           )
    language = st.radio('Language', ['cn', 'en'],
                        horizontal=True,
                        format_func=lambda x: ':flag-cn:' if x == 'cn' else ':flag-gb:'
                        )
    book_notes_file = st.file_uploader('Book Notes File', type=['txt'])
    
    submitted = st.form_submit_button('Add Book')
    if submitted:
        add_book(title, authors, source_type, language, book_notes_file)

# Book list
st.subheader('Book List')
books = get_books()
if not books:
    st.info('No books found. Please add a book.')
else:
    for i in range(0, len(books), BOOK_LIST_COLUMNS):
        columns = st.columns(BOOK_LIST_COLUMNS)
        for j in range(BOOK_LIST_COLUMNS):
            if i + j < len(books):
                book = books[i + j]
                with columns[j]:
                    with st.container(border=True):
                        inner_columns = st.columns([1, 2])
                        with inner_columns[0]:
                            cover_url = book.cover_url or DEFAULT_COVER_URL
                            st.image(get_image_bytes_from_url(cover_url), use_column_width=True)
                        with inner_columns[1]:
                            st.markdown(f"**{book.name}**")
                            st.write(", ".join(book.authors))
                            st.caption(f"Notes: {book.num_notes} | Entries: {book.num_entries}")
                        st.button('More', on_click=show_book_details, args=(book.id,), key=f'more_{book.id}')
st.button('Refresh', on_click=st.rerun)
