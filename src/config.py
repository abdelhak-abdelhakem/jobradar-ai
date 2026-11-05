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
SETTINGS_PATH = os.path.join(BASE_DIR, "data", "settings.json")   # written by the dashboard

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
CNRS_BASE_URL = "https://emploi.cnrs.fr"
CNRS_SEARCH_URL = f"{CNRS_BASE_URL}/Offres/Recherche.aspx"
CNRS_INTERNSHIP_CONTRACT = "STAG"   # the search form's "Convention de stage" filter
CEA_BASE_URL = "https://www.emploi.cea.fr"
CEA_SEARCH_URL = f"{CEA_BASE_URL}/offre-de-emploi/liste-offres.aspx"
CEA_INTERNSHIP_CONTRACT = 579   # the "Stage" contract filter
CEA_PROFILES = [1898, 1909]     # "Mathématiques, information scientifique, logiciel" and "Systèmes d'information"
CEA_MAX_PAGES = 15              # 20 offers per page; a safety stop in case pagination never ends
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

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")
