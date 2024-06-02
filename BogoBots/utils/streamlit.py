import inspect

from typing import Callable, TypeVar
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
from streamlit.delta_generator import DeltaGenerator

T = TypeVar('T')

def get_streamlit_cb(cb, **kwargs):
    def decor(fn: Callable[..., T]) -> Callable[..., T]:
        ctx = get_script_run_ctx()
        def wrapper(*args, **kwargs) -> T:
            add_script_run_ctx(ctx=ctx)
            return fn(*args, **kwargs)
        return wrapper

    st_cb = cb(**kwargs)

    for name, fn in inspect.getmembers(st_cb, predicate=inspect.ismethod):
        if name.startswith('on_'):
            setattr(st_cb, name, decor(fn))

    return st_cb
        
def write_token_usage(container, message):
    if usage := message.usage_metadata:
        usage_str = f"""input {usage['input_tokens']} |
            output {usage['output_tokens']} |
            total {usage['total_tokens']} tkns"""
        # use markdown to be compatible to langchain streamlit handler
        container.markdown(f'<p style="color: rgb(163, 168, 184); font-size: 14px;">{usage_str}</p>',
                        unsafe_allow_html=True)