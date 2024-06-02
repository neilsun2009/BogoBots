import os
import sys
import argparse

from langchain.indexes import SQLRecordManager
from langchain_core.indexing.api import index

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from BogoBots.document_loaders.weread_loader import WeReadLoader
from BogoBots.utils.langchain import get_zilliz_vectorstore
from BogoBots.configs.embedding import collection_name


def main():
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--file_path', type=str, required=True, help='Path to the file')
    parser.add_argument('--book_name', type=str, required=True, help='Name of the book')
    parser.add_argument('--booknote_type', type=str, choices=['weread'], default='weread', help='Type of the booknote')
    # parser.add_argument('--embedding_model', type=str, default="BAAI/bge-m3", help='Model for embedding')
    parser.add_argument('--embedding_batch_size', type=int, default=64, help='Batch size for embedding')
    # parser.add_argument('--force_update', action='store_true', default=False, help='Force update')
    
    args = parser.parse_args()
    
    # get loader
    if args.booknote_type == 'weread':
        loader = WeReadLoader(args.file_path, args.book_name)
    else:
        raise ValueError(f"Unsupported booknote type: {args.booknote_type}")
    
    # get embeddings
    # embeddings = get_embeddings()
    
    # connect to zilliz
    vectorstore = get_zilliz_vectorstore()
    
    # test embedding
    embeddings = vectorstore.embedding_func
    embedding_sample = embeddings.embed_query('说点smart的话')
    print('embedding dimension', len(embedding_sample))
    # vectorstore.add_texts(["test"], metadatas=[{"source": "test"}])
    
    # set record manager
    namespace = f"zilliz/{collection_name}"
    print('namespace:', namespace)
    record_manager = SQLRecordManager(
        namespace, db_url="sqlite:///record_manager_cache.sql"
    )
    record_manager.create_schema()
    
    # embedding and indexing
    result = index(loader, record_manager, vectorstore, batch_size=args.embedding_batch_size, 
          cleanup="incremental", source_id_key="source", force_update=False)
    print('indexing result')

if __name__ == "__main__":
    main()