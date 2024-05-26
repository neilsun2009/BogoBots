import inspect

from typing import Callable, TypeVar
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
from streamlit.delta_generator import DeltaGenerator
from langchain_community.callbacks import StreamlitCallbackHandler

T = TypeVar('T')

def get_streamlit_cb(**kwargs):
    def decor(fn: Callable[..., T]) -> Callable[..., T]:
        ctx = get_script_run_ctx()
        def wrapper(*args, **kwargs) -> T:
            add_script_run_ctx(ctx=ctx)
            return fn(*args, **kwargs)
        return wrapper

    st_cb = StreamlitCallbackHandler(**kwargs)

    for name, fn in inspect.getmembers(st_cb, predicate=inspect.ismethod):
        if name.startswith('on_'):
            setattr(st_cb, name, decor(fn))

    return st_cb