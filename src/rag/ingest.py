from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.config import PROFILE_PATH, CHUNK_SIZE, CHUNK_OVERLAP

def load_and_split_profile():
    """Loads the candidate profile and splits it into chunks."""
    loader = UnstructuredMarkdownLoader(PROFILE_PATH)
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(docs)
    return chunks