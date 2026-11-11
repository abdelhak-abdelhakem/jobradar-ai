from src.agents.state import JobRadarState
from src.config import CONTRACTS
from src.scrapers.cea_offres import get_cea_jobs
from src.scrapers.cnrs_offres import get_cnrs_jobs
from src.scrapers.inria_offres import get_inria_jobs
from src.settings import SOURCES, load_settings

# Job boards whose search form filters on the contract type. Inria has no such filter.
FILTERED_BY_CONTRACT = ("cnrs", "cea")


def scrape_node(state: JobRadarState) -> dict:
    """Scrapes the job boards selected in the settings. One board failing doesn't stop the others."""
    settings = load_settings()
    contract = CONTRACTS[settings["contract_type"]]
    codes = contract["site_codes"]
    role_keywords = settings["role_keywords"]
    domain_keywords = settings["domain_keywords"]

    # Built at call time so tests can monkeypatch the scraper functions.
    # CNRS and CEA filter on the contract type in their search form, so only Inria uses the role keywords.
    scrapers = {
        "inria": lambda: get_inria_jobs(role_keywords=role_keywords, domain_keywords=domain_keywords),
        "cnrs": lambda: get_cnrs_jobs(domain_keywords=domain_keywords, contract_code=codes["cnrs"]),
        "cea": lambda: get_cea_jobs(domain_keywords=domain_keywords, contract_code=codes["cea"]),
    }
    selected = settings["sources"]
    print(f"Sources: {', '.join(selected)}. Contract: {contract['label']}.")

    job_listings = []
    for name in selected:
        if name in FILTERED_BY_CONTRACT and name not in codes:
            print(f"[!] {SOURCES[name]} has no {contract['label']} offers on its job site, so it was skipped.")
            continue
        try:
            jobs = scrapers[name]()
        except Exception as e:
            print(f"[!] The {name} scraper failed and was skipped: {e}")
            continue
        print(f"{name}: {len(jobs)} jobs")
        job_listings.extend(jobs)

    return {"job_listings": job_listings}
