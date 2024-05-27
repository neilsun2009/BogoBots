import os
import sys
import streamlit as st
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages.chat import ChatMessage
from langchain_core.messages.human import HumanMessage
from langchain_core.messages.ai import AIMessage
from langchain_core.messages.tool import ToolMessage
from langchain_openai import ChatOpenAI
from langchain_community.callbacks import StreamlitCallbackHandler
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint import MemorySaver

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from BogoBots.configs.models import available_models
from BogoBots.tools.bolosophy import BolosophyTool
from BogoBots.utils.streamlit import get_streamlit_cb
from BogoBots.utils.langchain import get_messages_from_checkpoint_tuple
from BogoBots.graphs.chat_with_tools_graph import get_chat_with_tools_graph

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
    # st.session_state.messages = []
    st.session_state.checkpoint_tuple = None

# Initialize chat history
# if "messages" not in st.session_state:
#     st.session_state.messages = []
if "checkpoint_tuple" not in st.session_state:
    st.session_state.checkpoint_tuple = None
    
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
if st.session_state.checkpoint_tuple is None or len(get_messages_from_checkpoint_tuple(st.session_state.checkpoint_tuple)) == 0:
    # Display welcome message
    with main_container:
        st.title('📎Welcome to BogoBots!')
        st.markdown("Ask me anything!")
else:
    # Display chat messages from history on app rerun
    with main_container:
        msg_container = None
        for message in get_messages_from_checkpoint_tuple(st.session_state.checkpoint_tuple):
            if isinstance(message, AIMessage):
                role = 'assistant'
                avatar = None
                msg_model_name = message.response_metadata.get('model_name', None)
                if msg_model_name:
                    avatar = MODEL_NAME_AVATAR_MAP.get(msg_model_name.split('/')[-1], None)
                # if has tool calls
                tool_calls = message.tool_calls
                if len(tool_calls) == 0:
                    # no tool call in this step
                    # if msg_container is not None, it means this is the result of tool calls
                    if msg_container is None:
                        msg_container = st.chat_message(role, avatar=avatar)
                    with msg_container:
                        st.markdown(message.content)
                    # revert msg_container to None
                    msg_container = None
                else:
                    # start a new container to display intermediate steps
                    # and the final message
                    msg_container = st.chat_message(role, avatar=avatar)
            elif isinstance(message, HumanMessage):
                role = 'user'
                msg_container = st.chat_message(role)
                with msg_container:
                    st.markdown(message.content)
                # revert msg_container as well
                msg_container = None
            elif isinstance(message, ToolMessage):
                # append intermediate step info to the current container
                with msg_container:
                    with st.status(message.name, state='complete'):
                        st.markdown(message.content)
            # if message.role == 'assistant' and hasattr(message, 'name'):
            #     avatar = MODEL_NAME_AVATAR_MAP.get(message.name, None)
        
# React to user input
if prompt := st.chat_input("What is up?"):
    # For first message, empty the main placeholder
    if len(get_messages_from_checkpoint_tuple(st.session_state.checkpoint_tuple)) == 0:
        main_placeholder.empty()
        main_container = main_placeholder.container()
    # Display user message in chat message container
    with main_container:
        with st.chat_message("user"):
            st.markdown(prompt)
    # Add user message to chat history
    # st.session_state.messages.append(ChatMessage(role="user", content=prompt))
    
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
            # tools = []
            llm.bind_tools(tools)
            # put memory from session
            memory = MemorySaver()
            if st.session_state.get('checkpoint_tuple', None) is not None:
                memory.put(config=st.session_state.checkpoint_tuple.config,
                           checkpoint=st.session_state.checkpoint_tuple.checkpoint,
                           metadata=st.session_state.checkpoint_tuple.metadata)
            # get graph
            graph = get_chat_with_tools_graph(llm, tools, memory, 
                                              use_ad_hoc_tool_agent=len(tools) and not model['native_tool_support'])
            
            # graph = create_react_agent(llm, tools=tools,
            #                         #    messages_modifier=system_prompt,
            #                            checkpointer=memory)
            for s in graph.stream({'messages': [HumanMessage(role="user", content=prompt)]}, config, stream_mode="values"):
            # for s in graph.stream(HumanMessage(role="user", content=prompt), config, stream_mode="values"):
                message = s['messages'][-1]
                if isinstance(message, tuple):
                    print(message)
                else:
                    message.pretty_print()
                # print(response)
            # write last message when all intermedite nodes are done
            st.markdown(message.content)
            # response = graph.invoke(HumanMessage(role="user", content=prompt), config, stream_mode="values")
            # print(response)
            # duplicate display line, to avoid the message being overwritten by the spinner
            # st.markdown(response['messages'][-1].content)
            # update chat history
            checkpoint_tuple = memory.get_tuple(config)
            # st.session_state.messages.append(ChatMessage(role='assistant', name=model_name.split('/')[-1], content=checkpoint_tuple.checkpoint.content))
            st.session_state.checkpoint_tuple = checkpoint_tuple

# additional informations

@st.experimental_dialog("Raw messages", width='large')
def show_raw_messages():
    with st.container(height=450):
        st.json(st.session_state.checkpoint_tuple.checkpoint)
    
if len(get_messages_from_checkpoint_tuple(st.session_state.checkpoint_tuple)):
    if st.button('Show raw messages'):
        show_raw_messages()
