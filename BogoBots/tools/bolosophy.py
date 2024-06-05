from typing import Optional, Type
import requests
import json

from langchain.pydantic_v1 import BaseModel, Field
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool, ToolException
from langchain_huggingface.embeddings import HuggingFaceEndpointEmbeddings
from langchain_milvus.vectorstores import Zilliz
import streamlit as st

from BogoBots.utils.langchain import get_zilliz_vectorstore

class BolosophyInput(BaseModel):
    query: str = Field(description="search query string")


class BolosophyTool(BaseTool):
    name = "Bolosophy"
    description = "A local knowledge base constructed by Bogo, containing book notes, personal thoughts formulated by him. Useful for when you are asked to search Bogo\'s knowledge base or to answer questions about some professional topics you have no knowledge of"
    args_schema: Type[BaseModel] = BolosophyInput
    return_direct: bool = False
    
    emoji: str = "📚"
    vectorstore: Zilliz = None
    num_entries: int = 5
    
    def __init__(self):
        super().__init__()
        self.vectorstore = get_zilliz_vectorstore()

    def _run(
        self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool."""
        # try:
        #     response = requests.get(f"http://0.0.0.0:8000/query?q={query}&num_entries={num_entries}", headers={'Content-Type': 'application/json'})
        # except Exception as e:
        #     raise ToolException(f"Request to Bolosophy failed with error: {str(e)}")

        # json_response = response.json()
        # # print("bogology results:", json_response)
        # if response.status_code != 200:
        #     raise ToolException(f"Request Bolosophy failed with status {response.status_code}: {json_response['error']['message']}")

        # return json.dumps(json_response, ensure_ascii=False)

        # self.vectorstore = get_zilliz_vectorstore()
        print('Bolosophy test with query:', query)
        # retriever = vectorstore.as_retriever()
        retriever = self.vectorstore.as_retriever(search_kwargs={"k": self.num_entries})
        docs = retriever.invoke(query)
        print(f'{len(docs)} results retrieved')
        # result = {'query_results': [doc.page_content for doc in docs]}
        # return json.dumps(result, ensure_ascii=False)
        if len(docs):
            result = 'Following are the results from thie query: \n\n' + '\n'.join([f"- {doc.page_content}" for doc in docs])
        else:
            result = 'No results found for this query'
        return result
    
    def st_config(self):
        """config setting in streamlit"""
        self.num_entries = st.slider('Number of entries', 
                            min_value=1,
                            max_value=10,
                            step=1,
                            value=5,
                            help='''Maximum number of knowledge base entries to return.''')

if __name__ == '__main__':
    tool = BolosophyTool()
    print(tool.name)
    print(tool.description)
    print(tool.args)
    print(tool.return_direct)

    print(tool.invoke({"query": '商鞅与管仲对商人阶层的区别', "num_entries": 5}))