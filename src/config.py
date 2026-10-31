import os
from dotenv import load_dotenv

load_dotenv()

# Models Configuration
# gpt-5-nano doesn't support a custom temperature, so none is set.
LLM_MODEL = "gpt-5-nano"
LLM_MAX_CONCURRENCY = 8

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_PATH = os.path.join(BASE_DIR, "data", "profile", "my_profile.md")
SEEN_JOBS_DB = os.path.join(BASE_DIR, "data", "seen_jobs.sqlite3")

# Scoring
MATCH_SCORE_THRESHOLD = 70      # at or above this, a job gets a letter and a notification
NON_INTERNSHIP_MAX_SCORE = 40   # jobs that aren't internships can never reach the threshold
NO_DOMAIN_FIT_MAX_SCORE = 60    # neither can jobs with no link to the candidate's experience
ADJACENT_DOMAIN_MAX_SCORE = 79  # related experience can qualify, but can't reach the top band

# Letters
MAX_LETTER_REVISIONS = 2        # claim-check rounds before a letter is sent marked as unverified

# Scraper
INRIA_BASE_URL = "https://jobs.inria.fr"
INRIA_SEARCH_URL = f"{INRIA_BASE_URL}/public/classic/en/offres"
SCRAPER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# A job must match a role term in its title AND a domain term in its title or description.
# Keywords in ALL CAPS match case-sensitively, so "AI" doesn't match the French "j'ai".
ROLE_KEYWORDS = [
    "internship", "intern", "stage", "stagiaire", "pfe", "M2", "Master 2",
    "end-of-study", "end of study", "fin d'études", "fin d’études",
]
DOMAIN_KEYWORDS = [
    "AI", "IA", "ML", "NLP", "LLM", "LLMs", "RAG", "TAL", "GenAI",
    "artificial intelligence", "intelligence artificielle",
    "machine learning", "deep learning", "reinforcement learning",
    "federated learning", "representation learning", "self-supervised",
    "apprentissage automatique", "apprentissage profond", "apprentissage par renforcement",
    "natural language processing", "traitement automatique du langage",
    "large language model", "large language models", "language model", "language models",
    "modèle de langage", "modèles de langage",
    "generative AI", "prompt engineering", "vector database", "fine-tuning",
    "computer vision", "vision par ordinateur",
    "neural network", "neural networks", "réseau de neurones", "réseaux de neurones",
    "langchain", "langgraph", "hugging face", "transformer", "transformers",
    "world model", "world models",
]
# Combined list for scrapers that only filter on titles (welcome_to_jungle.py).
SEARCH_KEYWORDS = ROLE_KEYWORDS + DOMAIN_KEYWORDS

# The main page we navigate to trigger the API call
APEC_SEARCH_URL = "https://www.apec.fr/candidat/recherche-stage.html/stage?motsCles=Intelligence+Artificielle"

# The exact backend endpoint you identified
APEC_API_ENDPOINT = "https://www.apec.fr/cms/webservices/rechercheOffre"

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")
