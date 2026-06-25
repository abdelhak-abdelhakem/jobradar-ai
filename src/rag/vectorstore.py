from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from src.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_INDEX_PATH,
    EMBEDDING_MODEL,
)


embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)


def get_or_create_vector_store(doc_chunks):
    """
    Returns the Chroma vector store and ingests the
    provided document chunks if supplied.
    """

    vectorstore = Chroma(
        persist_directory=CHROMA_INDEX_PATH,
        embedding_function=embeddings,
        collection_name=CHROMA_COLLECTION_NAME,
    )

    if doc_chunks:
        vectorstore.add_documents(doc_chunks)

    return vectorstore