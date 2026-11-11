from src.agents.state import JobRadarState
from src.scrapers.cea_offres import get_cea_jobs
from src.scrapers.cnrs_offres import get_cnrs_jobs
from src.scrapers.inria_offres import get_inria_jobs
from src.settings import load_settings


def scrape_node(state: JobRadarState) -> dict:
    """Scrapes the job boards selected in the settings. One board failing doesn't stop the others."""
    settings = load_settings()
    role_keywords = settings["role_keywords"]
    domain_keywords = settings["domain_keywords"]

    # Built at call time so tests can monkeypatch the scraper functions.
    # CNRS and CEA filter on the contract type in their search form, so only Inria uses the role keywords.
    scrapers = {
        "inria": lambda: get_inria_jobs(role_keywords=role_keywords, domain_keywords=domain_keywords),
        "cnrs": lambda: get_cnrs_jobs(domain_keywords=domain_keywords),
        "cea": lambda: get_cea_jobs(domain_keywords=domain_keywords),
    }
    selected = settings["sources"]
    print(f"Sources: {', '.join(selected)}")

    job_listings = []
    for name in selected:
        try:
            jobs = scrapers[name]()
        except Exception as e:
            print(f"[!] The {name} scraper failed and was skipped: {e}")
            continue
        print(f"{name}: {len(jobs)} jobs")
        job_listings.extend(jobs)

    return {"job_listings": job_listings}
