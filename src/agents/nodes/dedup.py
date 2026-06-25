from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from src.agents.state import JobRadarState
from src.config import DEDUP_CHROMA_DIR, EMBEDDING_MODEL, DEDUP_COLLECTION_NAME

def dedup_node(state: JobRadarState) -> JobRadarState:
    """
    For each scraped job, checks if a near-duplicate already exists in Chroma.
    Returns only the genuinely new jobs.
    """
    job_listings = state["job_listings"]
    documents = []
    
    for item in job_listings:
        combined_text = f"{item['title']}\n\n{item['description']}"
        doc = Document(
            page_content=combined_text,
            metadata={"url": item["url"], "job_id": item["id"]}
        )
        documents.append(doc)
        
    vector_db = Chroma(
        persist_directory=DEDUP_CHROMA_DIR,
        embedding_function=OpenAIEmbeddings(model=EMBEDDING_MODEL),
        collection_name=DEDUP_COLLECTION_NAME
    )
    
    existing = vector_db.get()  
    existing_ids = {meta.get("job_id") for meta in existing["metadatas"]}

    new_jobs = [doc for doc in documents if doc.metadata["job_id"] not in existing_ids]
    print(f"\n{len(new_jobs)} new jobs found, {len(documents) - len(new_jobs)} duplicates skipped (by ID).")
    
    state["new_jobs"] = new_jobs
    return state