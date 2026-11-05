from src.agents.state import JobRadarState
from src.scrapers.cnrs_offres import get_cnrs_jobs
from src.scrapers.inria_offres import get_inria_jobs


def scrape_node(state: JobRadarState) -> dict:
    """Scrapes every job board. One board failing doesn't stop the others."""
    # Built at call time so tests can monkeypatch the scraper functions.
    scrapers = [
        ("inria", get_inria_jobs),
        ("cnrs", get_cnrs_jobs),
    ]

    job_listings = []
    for name, scraper in scrapers:
        try:
            jobs = scraper()
        except Exception as e:
            print(f"[!] The {name} scraper failed and was skipped: {e}")
            continue
        print(f"{name}: {len(jobs)} jobs")
        job_listings.extend(jobs)

    return {"job_listings": job_listings}
