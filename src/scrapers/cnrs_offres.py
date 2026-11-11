import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from src.config import (
    CNRS_BASE_URL, CNRS_SEARCH_URL, CONTRACTS, DOMAIN_KEYWORDS, SCRAPER_HEADERS,
)
from src.scrapers.inria_offres import compile_keywords, matches_any


# Every offer page ends with the same "About the CNRS" text, so it's cut off before filtering.
BOILERPLATE_START = "À propos du CNRS"


def scrape_job_details(url, headers):
    """Fetches the offer page and returns its text, or None if that fails."""
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"  [!] Error fetching details for {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    content = soup.select_one('article .post-body') or soup.find('main')
    if not content:
        print(f"  [!] No content found at {url}")
        return None

    text = content.get_text(separator='\n\n', strip=True)
    return text.split(BOILERPLATE_START)[0].strip() or None


def get_cnrs_jobs(domain_keywords=DOMAIN_KEYWORDS, contract_code=CONTRACTS["internship"]["site_codes"]["cnrs"]):
    """
    Returns CNRS offers of one contract type in the target domain.
    The search form already filters on the contract type, so only the domain filter is applied,
    on the title and full description.
    Jobs whose details couldn't be fetched are kept with description=None, so dedup can report them.
    """
    print(f"Fetching {contract_code} listings from: {CNRS_SEARCH_URL}...\n")
    try:
        response = requests.post(
            CNRS_SEARCH_URL,
            data={"ContractType": contract_code, "Page": 0},
            headers=SCRAPER_HEADERS,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching the search page: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    domain_patterns = compile_keywords(domain_keywords)

    # 1. Gather the offers. Each result card has the title link and the lab name.
    job_dict = {}
    for card in soup.select('.card-body'):
        link = card.select_one('h3 a[href*="/Offres/"]')
        if not link:
            continue
        job_url = urljoin(CNRS_BASE_URL, link['href'])
        lab = card.select_one('.meta strong')
        job_dict.setdefault(job_url, {
            'title': link.get_text(strip=True),
            'lab': lab.get_text(strip=True) if lab else None,
        })

    print(f"Found {len(job_dict)} offers. Fetching details...\n")

    # 2. Fetch details, then keep the jobs that match the domain
    job_listings = []
    for idx, (job_url, meta) in enumerate(job_dict.items(), 1):
        print(f"[{idx}/{len(job_dict)}] Scraping: {meta['title']}")
        full_description = scrape_job_details(job_url, SCRAPER_HEADERS)

        text = f"{meta['title']}\n{full_description or ''}"
        if full_description is None or matches_any(domain_patterns, text):
            job_listings.append({
                'source': 'cnrs',
                # URLs look like /Offres/PASS/UMR5814-LOUDAI-062/Default.aspx; the offer reference is the ID.
                'id': job_url.rstrip('/').split('/')[-2],
                'title': meta['title'],
                'company': f"CNRS - {meta['lab']}" if meta['lab'] else 'CNRS',
                'url': job_url,
                'description': full_description,
            })

        time.sleep(0.5)

    print(f"\n{len(job_listings)} of {len(job_dict)} offers match the target domain.")
    return job_listings
