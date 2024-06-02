from typing import AsyncIterator, Iterator
import re

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


class WeReadLoader(BaseLoader):
    """A loader for book notes from WeRead."""
    
    # separator considering multilingual text like Chinese
    separators = [
        "\n\n",
        "\n",
        " ",
        ".",
        ",",
        "\u200b",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
    ]
    # regex for chapter name
    chapter_name_regex = r"^第[一二三四五六七八九十百千万亿]+章 "
    
    def __init__(self, file_path, book_name):
        self.file_path = file_path
        self.book_name = book_name
        self.note_idx = 0
        self.text_splitter = RecursiveCharacterTextSplitter(
            separators=self.separators,
            chunk_size=300, 
            chunk_overlap=20,
        )
        
    def _yield_accu_text(self, accu_text, chapter_name) -> Iterator[Document]:
        if accu_text:
            self.note_idx += 1
            doc = Document(page_content=accu_text, 
                            metadata={
                                "source": self.book_name, 
                                "chapter": chapter_name,
                                'note_idx': self.note_idx,  
                            })
            if self.note_idx % 100 == 0:
                print(f'adding note No.{self.note_idx}...')
            yield from self.text_splitter.split_documents([doc])
                        
    def lazy_load(self) -> Iterator[Document]:
        with open(self.file_path, encoding="utf-8") as f:
            # text are added in a accumulated manner by lines
            accu_text = ''
            chapter_name = ''
            for idx, line in enumerate(f):
                # skip metadata lines
                if idx < 5: 
                    continue
                line = line.strip()
                line = line.replace('\ufffc', '')
                # skip empty lines
                if len(line) == 0:
                    continue
                # locate chapter name
                # when a new chapter starts, yield the accumulated text
                if line == '点评':
                    yield from self._yield_accu_text(accu_text, chapter_name)
                    accu_text = ''
                    chapter_name = line
                elif re.match(self.chapter_name_regex, line):
                    yield from self._yield_accu_text(accu_text, chapter_name)
                    accu_text = ''
                    chapter_name = line.split(' ', maxsplit=1)[1]
                elif line.startswith('◆ '):
                    # a new book note starts
                    yield from self._yield_accu_text(accu_text, chapter_name)
                    accu_text = line[2:] # skip '◆ '
                else:
                    accu_text += '\n' + line
                    
    def load(self):
        return list(self.lazy_load())
    
if __name__ == '__main__':
    loader = WeReadLoader(file_path='../data/booknotes/haodang2000.txt', book_name='浩荡两千年：中国企业公元前7世纪~1869年')
    for idx, doc in enumerate(loader.load()):
        if idx < 20:
            print(doc)