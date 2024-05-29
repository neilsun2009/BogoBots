import os
import sys
import streamlit as st
import numpy as np
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages.chat import ChatMessage
from langchain_core.messages.human import HumanMessage
from langchain_core.messages.ai import AIMessage
from langchain_core.messages.tool import ToolMessage
from langchain_openai.chat_models.base import ChatOpenAI
from langchain_community.callbacks import StreamlitCallbackHandler
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint import MemorySaver
from langchain_community.callbacks.streamlit.streamlit_callback_handler import StreamlitCallbackHandler

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from BogoBots.configs.models import available_models
from BogoBots.tools.bolosophy import BolosophyTool
from BogoBots.utils.streamlit import get_streamlit_cb
from BogoBots.utils.langchain import get_messages_from_checkpoint_tuple
from BogoBots.graphs.chat_with_tools_graph import get_chat_with_tools_graph
from BogoBots.callbacks.custom_streamlit_callback_handler import CustomStreamlitCallbackHandler

OPEN_ROUTER_API_BASE = 'https://openrouter.ai/api/v1'

MODEL_NAME_AVATAR_MAP = {}

for model_group in available_models:
    for model in model_group['models']:
        MODEL_NAME_AVATAR_MAP[model['api_name']] = model_group['icon']
        # MODEL_NAME_AVATAR_MAP[f"{model_group['open_router_prefix']}/{model['api_name']}"] = model_group['icon']

st.set_page_config(
    page_title='BogoBots', 
    page_icon='🎭'
)

def clear_history():
    # st.session_state.messages = []
    st.session_state.checkpoint_tuple = None

# Initialize chat history
if "checkpoint_tuple" not in st.session_state:
    st.session_state.checkpoint_tuple = None
    
# sidebar
with st.sidebar:
    # new chat
    # st.markdown('---')
    st.title('🎭BogoBots')
    # st.markdown('A chatbot assistant designed by Bogo.')
    st.button('New chat', on_click=clear_history)
    st.markdown('---')
    
    # model selection
    current_model_container = st.container()
    with st.popover('Switch model'):
        model_group = st.selectbox('Select model group', available_models, format_func=lambda x: x['group'])
        model = st.selectbox('Select model', model_group['models'], 
                            format_func=lambda x: ('[FREE!] ' if x['is_free'] else '') + x['display_name'])
    if model['is_free']:
        st.caption(' 🎉 Free model at your service!')
    else:
        st.caption('❗You can also find free models to use!')
    # current_model_container.subheader('✨ Using model')
    current_model_container.markdown(f'<img src="{model_group["icon"]}" alt="{model["display_name"]}" height="28px"> **{model["display_name"]}**', unsafe_allow_html=True)
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
    # api key
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
        st.caption('Your API key is safe with us. We won\'t store it or use it outside the scope of your action on this site.')
    
    # tools
    st.markdown('---')
    st.subheader('🛠️ Select tools')
    available_tools = [{
        'name': 'Bolosophy',
        'description': 'A knowledge base by Bogo, containing book notes and personal thoughts.',
        'func': BolosophyTool,
        'args': {}
    }]
    if not model['native_tool_support']:
        st.caption('''
            🚨 :red[No native tool support for this model!] \n
            Tools will be used in an ad-hoc manner by means of system message.
            The performance may be less optimal and is prone to errors. More tokens are also expected.
        ''')
    tools = st.multiselect('Select tools', available_tools, 
                           format_func=lambda x: x['name'],
                           placeholder='Try one or more tools!',
                           label_visibility='collapsed')
    tools = [tool['func'](**tool['args']) for tool in tools]
            
    # parameters
    st.markdown('---')
    st.subheader('🎰 Parameters')
    with st.container(height=200):
        temprature = st.slider('temprature', 
                                min_value=0.,
                                max_value=2.,
                                step=0.1,
                                value=1.,
                                format='%.1f',
                                help='''What sampling temperature to use, between 0 and 2. 
                                Higher values like 0.8 will make the output more random, while lower values like 0.2 will make it more focused and deterministic. 
                                We generally recommend altering this or `top_p` but not both. 
                                Default to 1.''')
        top_p = st.slider('top_p', 
                            min_value=0.,
                            max_value=1.,
                            step=0.1,
                            value=1.,
                            format='%.1f',
                            help='''An alternative to sampling with temperature, called nucleus sampling, 
                            where the model considers the results of the tokens with top_p probability mass. 
                            So 0.1 means only the tokens comprising the top 10% probability mass are considered. 
                            We generally recommend altering this or `temperature` but not both. 
                            Default to 1.''')
        frequency_penalty = st.slider('frequency_penalty', 
                                        min_value=-2.,
                                        max_value=2.,
                                        step=0.1,
                                        value=0.,
                                        format='%.1f',
                                        help='''Number between -2.0 and 2.0. Positive values penalize new tokens based on their existing frequency in the text so far, 
                                        decreasing the model's likelihood to repeat the same line verbatim.''')
        presence_penalty = st.slider('presence_penalty', 
                                        min_value=-2.,
                                        max_value=2.,
                                        step=0.1,
                                        value=0.,
                                        format='%.1f',
                                        help='''Number between -2.0 and 2.0. Positive values penalize new tokens based on whether they appear in the text so far, 
                                        increasing the model's likelihood to talk about new topics.''')
        max_tokens = st.number_input('max_tokens', 
                                        min_value=1,
                                        value=None,
                                        placeholder='No limit',
                                        help='''The maximum number of tokens that can be generated in the chat completion. 
                                        The total length of input tokens and generated tokens is limited by the model's context length.''')
        logprobs = st.checkbox('Return log probabilities', 
                                        value=False,
                                        help='''Whether to return log probabilities of the output tokens or not. If true, returns the log probabilities of each output token returned.''')
        if logprobs:
            top_logprobs = st.number_input('top_logprobs', 
                                        min_value=0,
                                        max_value=20,
                                        value=0,
                                        placeholder='Don\'t return',
                                        help='''An integer between 0 and 20 specifying the number of most likely tokens to return at each token position, each with an associated log probability. `logprobs` must be set to `true` if this parameter is used.''')
        else:
            top_logprobs = None
        
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
                        st.write(message.content)
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
                    st.write(message.content)
                # revert msg_container as well
                msg_container = None
            elif isinstance(message, ToolMessage):
                # append intermediate step info to the current container
                with msg_container:
                    with st.status(message.name, state='complete'):
                        st.write(message.content)
        
# React to user input
if prompt := st.chat_input("What is up?"):
    # For first message, empty the main placeholder
    if len(get_messages_from_checkpoint_tuple(st.session_state.checkpoint_tuple)) == 0:
        main_placeholder.empty()
        main_container = main_placeholder.container()
    # Display user message in chat message container
    with main_container:
        with st.chat_message("user"):
            st.write(prompt)
    
    if not api_key:
        st.error("Please add your API key to continue.")
        st.stop()
    
    # generate response
    with main_container:
        with st.chat_message("assistant", avatar=MODEL_NAME_AVATAR_MAP.get(model_name.split('/')[-1], None)):
            msg_container = st.container()
            # stream_handler = StreamHandler(msg_container)
            stream_handler = get_streamlit_cb(CustomStreamlitCallbackHandler, 
                                              parent_container=msg_container, 
                                              expand_new_thoughts=True, 
                                              collapse_completed_thoughts=False,)
            config = {
                "configurable": {"thread_id": "thread-1"},
                "callbacks": [stream_handler],
            }
            llm = ChatOpenAI(openai_api_base=api_base,
                            openai_api_key=api_key, 
                            model_name=model_name,
                            max_tokens=max_tokens,
                            temperature=temprature,
                            model_kwargs={
                                "top_p": top_p,
                                "frequency_penalty": frequency_penalty,
                                "presence_penalty": presence_penalty,
                                "logprobs": logprobs,
                                "top_logprobs": top_logprobs,
                                "stream_options": {
                                    "include_usage": True,
                                }
                            },
                            streaming=True, 
                            # callbacks=[stream_handler],
                        )
            # tools = []
            llm.bind_tools(tools)
            # set memory from session
            memory = MemorySaver()
            if st.session_state.get('checkpoint_tuple', None):
                memory.put(config=st.session_state.checkpoint_tuple.config,
                           checkpoint=st.session_state.checkpoint_tuple.checkpoint,
                           metadata=st.session_state.checkpoint_tuple.metadata)
            # get graph
            graph = get_chat_with_tools_graph(llm, tools, memory, 
                                              use_ad_hoc_tool_agent=len(tools) and not model['native_tool_support'])
            
            for s in graph.stream({'messages': [HumanMessage(role="user", content=prompt)]}, config, stream_mode="values"):
                message = s['messages'][-1]
                if isinstance(message, tuple):
                    print(message)
                else:
                    message.pretty_print()
                # print(message)
                # add model name to response metadata
                message.response_metadata['model_name'] = model_name
            # write last message when all intermedite nodes are done
            # msg_container.write(message.content)
            # update chat history
            checkpoint_tuple = memory.get_tuple(config)
            st.session_state.checkpoint_tuple = checkpoint_tuple

# additional informations

@st.experimental_dialog("Raw messages", width='large')
def show_raw_messages():
    with st.container(height=450):
        st.json(st.session_state.checkpoint_tuple.checkpoint)
    
if len(get_messages_from_checkpoint_tuple(st.session_state.checkpoint_tuple)):
    if st.button('Show raw messages'):
        show_raw_messages()
