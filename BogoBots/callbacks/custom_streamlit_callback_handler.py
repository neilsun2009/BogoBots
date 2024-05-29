from typing import TYPE_CHECKING, Any, Dict, List, NamedTuple, Optional

from langchain_community.callbacks.streamlit.streamlit_callback_handler import StreamlitCallbackHandler
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.outputs import LLMResult

class CustomStreamlitCallbackHandler(StreamlitCallbackHandler):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        print('LLM END RESPOSNE', response, kwargs)
        super().on_llm_end(response, **kwargs)
        # self._require_current_thought().on_llm_end(response, **kwargs)
        # self._prune_old_thought_containers()
        if self._current_thought is not None:
            self._current_thought.complete(
                self._thought_labeler.get_final_agent_thought_label()
            )
            self._current_thought = None
        
    # def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
    #     print('CHAIN END OUTPUTS', outputs, kwargs)
    #     super().on_chain_end(outputs, **kwargs)
        
    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        print('LLM NEW TOKEN', token, kwargs)
        super().on_llm_new_token(token, **kwargs)
        
    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        print('LLM START SERIALIZED', serialized, prompts, kwargs)
        super().on_llm_start(serialized, prompts, **kwargs)
        
    def on_agent_finish(
        self, finish: AgentFinish, color: Optional[str] = None, **kwargs: Any
    ) -> None:
        print('AGENT FINISH', finish, color, kwargs)
        super().on_agent_finish(finish, color, **kwargs)
        # if self._current_thought is not None:
        #     self._current_thought.complete(
        #         self._thought_labeler.get_final_agent_thought_label()
        #     )
        #     self._current_thought = None