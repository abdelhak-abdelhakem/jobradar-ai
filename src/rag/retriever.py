from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from src.rag.ingest import load_and_split_profile
from src.rag.vectorstore import get_or_create_vector_store
from src.config import VECTOR_K, BM25_K, RETRIEVER_WEIGHTS

# Initialize and expose the ensemble retriever for the nodes to use
chunks = load_and_split_profile()
vectorstore = get_or_create_vector_store(chunks)

chroma_retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": VECTOR_K}
)

bm25_retriever = BM25Retriever.from_documents(chunks)
bm25_retriever.k = BM25_K

ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, chroma_retriever],
    weights=RETRIEVER_WEIGHTS
)