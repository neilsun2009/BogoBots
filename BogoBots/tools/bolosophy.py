from typing import Optional, Type
import requests
import json

from langchain.pydantic_v1 import BaseModel, Field
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool, ToolException

class BolosophyInput(BaseModel):
    query: str = Field(description="search query string")
    num_entries: Optional[int] = Field(description="maximum number of knowledge base entries to return",
                             gt=0,
                             lte=10,
                             default=5)


class BolosophyTool(BaseTool):
    name = "Bolosophy"
    description = "A local knowledge base constructed by Bogo, containing book notes, personal thoughts formulated by him. Useful for when you are asked to search Bogo\'s knowledge base or to answer questions about some professional topics you have no knowledge of"
    args_schema: Type[BaseModel] = BolosophyInput
    return_direct: bool = True

    def _run(
        self, query: str, num_entries: Optional[int] = 5, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool."""
        try:
            response = requests.get(f"http://127.0.0.1:8000/query?q={query}&num_entries={num_entries}", headers={'Content-Type': 'application/json'})
        except Exception as e:
            raise ToolException(f"Request to Bolosophy failed with error: {str(e)}")

        json_response = response.json()
        # print("bogology results:", json_response)
        if response.status_code != 200:
            raise ToolException(f"Request Bolosophy failed with status {response.status_code}: {json_response['error']['message']}")

        return json.dumps(json_response, ensure_ascii=False)

if __name__ == '__main__':
    tool = BolosophyTool()
    print(tool.name)
    print(tool.description)
    print(tool.args)
    print(tool.return_direct)

    print(tool.invoke({"query": '商鞅与管仲对商人阶层的区别', "num_entries": 5}))