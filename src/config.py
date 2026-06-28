import os
from dotenv import load_dotenv

load_dotenv()

# Models Configuration
LLM_MODEL = "gpt-5-nano"
LLM_TEMPERATURE = 0
EMBEDDING_MODEL = "text-embedding-3-small"

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_PATH = os.path.join(BASE_DIR, "data", "profile", "my_profile.md")

# Profile RAG (CV chunks)
CHROMA_INDEX_PATH = os.path.join(BASE_DIR, "data", "chroma", "profile_db")
PROFILE_COLLECTION_NAME = "candidate_profile"

# Deduplication (scraped jobs)
DEDUP_CHROMA_DIR = os.path.join(BASE_DIR, "data", "chroma", "dedup_db")
DEDUP_COLLECTION_NAME = "inria_jobs"

# Chunking & Retrieval
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
VECTOR_K = 3
BM25_K = 3
RETRIEVER_WEIGHTS = [0.5, 0.5]

# Scraper
INRIA_BASE_URL = "https://jobs.inria.fr"
INRIA_SEARCH_URL = f"{INRIA_BASE_URL}/public/classic/en/offres"
SCRAPER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

SEARCH_KEYWORDS = [
    "ia", "intelligence artificielle", "ai", "Artificial Intelligence",
    "machine learning", "deep learning", "learning", "ML Engineer",
    "nlp", "natural language processing", 
    "llm", "rag", "langchain", "langgraph", "agent", "Large Language Model",
    "Generative AI", "GenAI", "Prompt Engineering", "Vector Database", "Fine-tuning",
    "stage", "ingénieur", "engineer", "pfe", "internship",
    "computer vision", "neural", "neuronal", 
    "data", "language model", 
    "End-of-study internship", "Final Year Internship", "Stage Bac+5", 
    "Master 2", "Junior AI Engineer", "AI Internship France",
    "hugging face", "transformer"
]

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")