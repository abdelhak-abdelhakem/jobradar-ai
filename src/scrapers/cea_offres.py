import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from src.config import (
    CEA_BASE_URL, CEA_MAX_PAGES, CEA_PROFILES, CEA_SEARCH_URL, CONTRACTS,
    DOMAIN_KEYWORDS, SCRAPER_HEADERS,
)
from src.scrapers.inria_offres import compile_keywords, matches_any


OFFER_ID = re.compile(r'_(\d+)\.aspx$')


class OfferClosed(Exception):
    """CEA redirects closed offers to its homepage, though the search can still list them."""


def scrape_job_details(url, headers):
    """
    Fetches the offer page. Returns (full text, position text), or (None, None) if that fails.
    The position text leaves out the lab description, which often mentions AI even when the
    internship doesn't, so only it is used for the domain filter.
    """
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"  [!] Error fetching details for {url}: {e}")
        return None, None

    if not OFFER_ID.search(response.url):
        raise OfferClosed(url)

    soup = BeautifulSoup(response.text, 'html.parser')
    content = soup.select_one('#contenu-ficheoffre')
    if not content:
        print(f"  [!] No content found at {url}")
        return None, None

    # The "Organisation" paragraph is the same general CEA text on every offer.
    for element in content.select('[id$="divEntityDesc"]'):
        element.decompose()

    full_text = content.get_text(separator='\n\n', strip=True)
    if not full_text:
        return None, None

    # Sections are "General information" then "Position description" (or their French names).
    headings = content.find_all('h2')
    position_text = full_text
    if len(headings) > 1:
        position_heading = headings[1].get_text(strip=True)
        position_text = full_text.split(position_heading, 1)[-1]

    return full_text, position_text


def get_search_page(page, contract_code):
    params = {
        "facet_Contract": contract_code,
        "facet_Profile": CEA_PROFILES,
        "page": page,
        "LCID": 1036,
    }
    response = requests.get(CEA_SEARCH_URL, params=params, headers=SCRAPER_HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, 'html.parser')


def get_cea_jobs(domain_keywords=DOMAIN_KEYWORDS, contract_code=CONTRACTS["internship"]["site_codes"]["cea"]):
    """
    Returns CEA offers of one contract type in the target domain.
    The search is limited to that contract type in the software and IT fields, so only the domain filter
    is applied, on the title and the position description.
    Jobs whose details couldn't be fetched are kept with description=None, so dedup can report them.
    """
    print(f"Fetching contract {contract_code} listings from: {CEA_SEARCH_URL}...\n")
    domain_patterns = compile_keywords(domain_keywords)

    # 1. Gather the offers from every result page, until a page brings nothing new
    job_dict = {}
    for page in range(1, CEA_MAX_PAGES + 1):
        try:
            soup = get_search_page(page, contract_code)
        except requests.RequestException as e:
            print(f"Error fetching search page {page}: {e}")
            if page == 1:
                return []
            break

        new_offers = 0
        for link in soup.select('a.ts-offer-card__title-link[href]'):
            job_url = urljoin(CEA_BASE_URL, link['href'])
            if OFFER_ID.search(job_url) and job_url not in job_dict:
                job_dict[job_url] = link.get_text(strip=True)
                new_offers += 1

        if new_offers == 0:
            break
        time.sleep(0.5)

    print(f"Found {len(job_dict)} offers. Fetching details...\n")

    # 2. Fetch details, then keep the jobs that match the domain
    job_listings = []
    for idx, (job_url, job_title) in enumerate(job_dict.items(), 1):
        print(f"[{idx}/{len(job_dict)}] Scraping: {job_title}")
        try:
            full_description, position_text = scrape_job_details(job_url, SCRAPER_HEADERS)
        except OfferClosed:
            print("  Offer closed, skipped.")
            continue

        if full_description is None or matches_any(domain_patterns, f"{job_title}\n{position_text}"):
            job_listings.append({
                'source': 'cea',
                'id': OFFER_ID.search(job_url).group(1),
                'title': job_title,
                'company': 'CEA',
                'url': job_url,
                'description': full_description,
            })

        time.sleep(0.5)

    print(f"\n{len(job_listings)} of {len(job_dict)} offers match the target domain.")
    return job_listings
