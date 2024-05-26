import os
import sys
import streamlit as st
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages.chat import ChatMessage
from langchain_core.messages.human import HumanMessage
from langchain_core.tools import render_text_description
from langchain_openai import ChatOpenAI
from langchain_community.callbacks import StreamlitCallbackHandler
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint import MemorySaver

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from BogoBots.configs.models import available_models
from BogoBots.tools import BolosophyTool
from BogoBots.utils.streamlit import get_streamlit_cb

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

def clear_history():
    st.session_state.messages = []
    st.session_state.checkpoint_tuple = None

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
    
# sidebar
with st.sidebar:
    st.title('🎭BogoBots')
    # st.markdown('A chatbot assistant designed by Bogo.')
    st.markdown('---')
    # model selection
    current_model_container = st.container()
    with st.popover('Switch model'):
        model_group = st.selectbox('Select model group', available_models, format_func=lambda x: x['group'])
        model = st.selectbox('Select model', model_group['models'], 
                            format_func=lambda x: ('[FREE!] ' if x['is_free'] else '') + x['display_name'])
    current_model_container.markdown('**Current model:**')
    current_model_container.markdown(f'<img src="{model_group["icon"]}" alt="{model["display_name"]}" height="24px"> {model["display_name"]}', unsafe_allow_html=True)
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
        st.error(f'No API provider available for {model_group["group"]}.')
        
    use_free_key = False
    if api_provider == 'Original API':
        api_key = st.text_input(f'{model_group["group"]} API Key', type='password')
        api_base = model_group['original_api_base']
        model_name = model['api_name']
    elif api_provider == 'OpenRouter':
        if model['is_free']:
            use_free_key = st.checkbox('Fancy free trial?', value=True, help='Check this box to use a free trial key provided by us.')
        if use_free_key:
            api_key = st.secrets['free_open_router_key']
        else:
            api_key = st.text_input('OpenRouter API Key', type='password')
        api_base = OPEN_ROUTER_API_BASE
        model_name = f"{model_group['open_router_prefix']}/{model['api_name']}"
    else:
        api_key = None
        api_base = None
        model_name = None
    if not use_free_key:    
        st.caption('Your API key is safe with us. We won\'t store it or use it outside the scope of your interaction on this site.')
    # new chat
    st.markdown('---')
    st.button('New chat', on_click=clear_history)
    
# tools
tools = [BolosophyTool()]
    
main_placeholder = st.empty()
main_container = main_placeholder.container()
if len(st.session_state.messages) == 0:
    # Display welcome message
    with main_container:
        st.title('📎Welcome to BogoBots!')
        st.markdown("Ask me anything!")
else:
    # Display chat messages from history on app rerun
    with main_container:
        for message in st.session_state.messages:
            avatar = None
            if message.role == 'assistant' and hasattr(message, 'name'):
                avatar = MODEL_NAME_AVATAR_MAP.get(message.name, None)
            with st.chat_message(message.role, avatar=avatar):
                st.markdown(message.content)
        
# React to user input
if prompt := st.chat_input("What is up?"):
    # For first message, empty the main placeholder
    if len(st.session_state.messages) == 0:
        main_placeholder.empty()
        main_container = main_placeholder.container()
    # Display user message in chat message container
    with main_container:
        with st.chat_message("user"):
            st.markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append(ChatMessage(role="user", content=prompt))
    
    if not api_key:
        st.error("Please add your API key to continue.")
        st.stop()
    
    # generate response
    with main_container:
        with st.chat_message("assistant", avatar=MODEL_NAME_AVATAR_MAP.get(model_name.split('/')[-1], None)):
            # stream_handler = StreamHandler(msg_container)
            stream_handler = get_streamlit_cb(parent_container=st.container(), expand_new_thoughts=False)
            config = {
                "configurable": {"thread_id": "thread-1"},
                "callbacks": [stream_handler],
            }
            llm = ChatOpenAI(openai_api_base=api_base,
                            openai_api_key=api_key, 
                            model_name=model_name,
                            # streaming=True, 
                            # callbacks=[stream_handler],
                            )
            # put memory from session
            memory = MemorySaver()
            if st.session_state.get('checkpoint_tuple', None) is not None:
                memory.put(config=st.session_state.checkpoint_tuple.config,
                           checkpoint=st.session_state.checkpoint_tuple.checkpoint,
                           metadata=st.session_state.checkpoint_tuple.metadata)
            # system prompt with tools
            rendered_tools = render_text_description(tools)
            print(rendered_tools)
            system_prompt = f"""\
You are an assistant that has access to the following set of tools. 
Here are the names and descriptions for each tool:

{rendered_tools}

Given the user input, return the name and input of the tool to use. 
Return your response as a JSON blob with 'name' and 'arguments' keys.

The `arguments` should be a dictionary, with keys corresponding 
to the argument names and the values corresponding to the requested values.
"""
            agent = create_react_agent(llm, tools=tools,
                                       messages_modifier=system_prompt,
                                       checkpointer=memory)
            response = agent.invoke({'messages': [HumanMessage(role="user", content=prompt)]}, config, stream_mode="values")
            # message = s["messages"][-1]
            # if isinstance(message, tuple):
            #     print(message)
            # else:
                # response.pretty_print()
            print(response)
                    # response = llm.invoke(st.session_state.messages)
            # duplicate display line, to avoid the message being overwritten by the spinner
            st.markdown(response['messages'][-1].content)
            # update chat history
            st.session_state.messages.append(ChatMessage(role='assistant', name=model_name.split('/')[-1], content=response['messages'][-1].content))
            st.session_state.checkpoint_tuple = memory.get_tuple(config)
            print(st.session_state.checkpoint)

# additional informations

@st.experimental_dialog("Raw messages", width='large')
def show_raw_messages():
    with st.container(height=450):
        st.json(st.session_state.checkpoint_tuple.checkpoint)
    
if len(st.session_state.messages):
    if st.button('Show raw messages'):
        show_raw_messages()
