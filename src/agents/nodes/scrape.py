from src.agents.state import JobRadarState
from src.scrapers.inria_offres import get_inria_jobs


def scrape_node(state: JobRadarState) -> dict:
    """Scrapes the job boards."""
    return {"job_listings": get_inria_jobs()}
