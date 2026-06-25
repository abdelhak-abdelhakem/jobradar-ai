from src.agents.state import JobRadarState
from src.scrapers.inria_offres import get_inria_jobs

def scrape_node(state: JobRadarState) -> JobRadarState:
    """scrape jobs"""
    state["job_listings"] = get_inria_jobs()
    return state