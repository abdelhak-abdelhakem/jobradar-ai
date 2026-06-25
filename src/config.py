import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Models Configuration
LLM_MODEL = "gpt-5-nano"
LLM_TEMPERATURE = 0
EMBEDDING_MODEL = "text-embedding-3-small"

# Retrieval & Profile Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_INDEX_PATH = os.path.join(BASE_DIR, "data", "chroma", "profile_db")
CHROMA_COLLECTION_NAME = "jobradar_inria_jobs"
PROFILE_PATH = os.path.join(BASE_DIR, "data", "profile", "my_profile.md")
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
VECTOR_K = 3
BM25_K = 3
RETRIEVER_WEIGHTS = [0.5, 0.5]

# Scraper Configuration
INRIA_BASE_URL = "https://jobs.inria.fr"
INRIA_SEARCH_URL = f"{INRIA_BASE_URL}/public/classic/en/offres"
SCRAPER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Deduplication Configuration
DEDUP_CHROMA_DIR = "notebooks/docs/scraper_to_Chroma-mini-project/chroma_db"
DEDUP_COLLECTION_NAME = "inria_jobs"

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")