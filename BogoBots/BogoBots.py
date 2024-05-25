import os
import sys
import streamlit as st
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages.chat import ChatMessage
from langchain_openai import ChatOpenAI
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BogoBots.configs.models import available_models

OPEN_ROUTER_API_BASE = 'https://openrouter.ai/api/v1'

MODEL_NAME_AVATAR_MAP = {}

for model_group in available_models:
    for model in model_group['models']:
        MODEL_NAME_AVATAR_MAP[model['api_name']] = model_group['icon']
        # MODEL_NAME_AVATAR_MAP[f"{model_group['open_router_prefix']}/{model['api_name']}"] = model_group['icon']

class StreamHandler(BaseCallbackHandler):
    def __init__(self, container, initial_text=""):
        self.container = container
        self.text = initial_text

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.text += token
        self.container.markdown(self.text)


st.set_page_config(
    page_title='BogoBots', 
    page_icon='🎭'
)

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
    
# sidebar
with st.sidebar:
    st.title('🎭BogoBots')
    st.markdown('A chatbot assistant designed by Bogo.')
    st.markdown('---')
    # model selection
    model_group = st.selectbox('Select model group', available_models, format_func=lambda x: x['group'])
    model = st.selectbox('Select model', model_group['models'], 
                         format_func=lambda x: ('[FREE!] ' if x['is_free'] else '') + x['display_name'])
    # api key
    ambi_api_support = model_group['supports_original_api'] and model_group['supports_open_router']
    if ambi_api_support:
        api_provider = st.radio('Which API to use', horizontal=True, 
                                options=['Original API', 'OpenRouter'],
                                help='OpenRouter is an LLM router service. One key for all major LLMs. [learn more](https://openrouter.ai/)')
    elif model_group['supports_original_api']:
        api_provider = 'Original API'
        
    elif model_group['supports_open_router']:
        api_provider = 'OpenRouter'
    else:
        api_provider = None
        st.warning(f'No API provider available for {model_group["group"]}.')
        
    if api_provider == 'Original API':
        api_key = st.text_input(f'{model_group["group"]} API Key', type='password')
        api_base = model_group['original_api_base']
        model_name = model['api_name']
    elif api_provider == 'OpenRouter':
        api_key = st.text_input('OpenRouter API Key', type='password')
        api_base = OPEN_ROUTER_API_BASE
        model_name = f"{model_group['open_router_prefix']}/{model['api_name']}"
    else:
        api_key = None
        api_base = None
        model_name = None
        
    st.caption('Your API key is safe with us. We won\'t store it or use it outside the scope of your interaction on this site.')
    
# Display chat messages from history on app rerun
if len(st.session_state.messages) == 0:
    st.title('📎Welcome to BogoBots!')
    st.markdown("Ask me anything!")
else:
    for message in st.session_state.messages:
        avatar = None
        if message.role == 'assistant' and hasattr(message, 'name'):
            avatar = MODEL_NAME_AVATAR_MAP.get(message.name, None)
        with st.chat_message(message.role, avatar=avatar):
            st.markdown(message.content)
        
# React to user input
if prompt := st.chat_input("What is up?"):
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append(ChatMessage(role="user", content=prompt))
    
    if not api_key:
        st.warning("Please add your API key to continue.")
        st.stop()
    
    # generate response
    with st.chat_message("assistant", avatar=MODEL_NAME_AVATAR_MAP.get(model_name.split('/')[-1], None)):
        msg_container = st.empty()
        msg_container.write('Thinking...')
        stream_handler = StreamHandler(msg_container)
        llm = ChatOpenAI(openai_api_base=api_base,
                         openai_api_key=api_key, 
                         model_name=model_name,
                         streaming=True, 
                         callbacks=[stream_handler])
        response = llm.invoke(st.session_state.messages)
        st.session_state.messages.append(ChatMessage(role='assistant', name=model_name.split('/')[-1], content=response.content))

# additional informations

@st.experimental_dialog("Raw messages", width='large')
def show_raw_messages():
    with st.container(height=450):
        st.json(st.session_state.messages)
    
    
if len(st.session_state.messages):
    if st.button('Show raw messages'):
        show_raw_messages()