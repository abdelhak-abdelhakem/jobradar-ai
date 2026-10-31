import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from src.config import DOMAIN_KEYWORDS, INRIA_BASE_URL, INRIA_SEARCH_URL, ROLE_KEYWORDS, SCRAPER_HEADERS


# Inria's standard "about" text is on every page and would match every job as "artificial intelligence".
BOILERPLATE = re.compile(r"strategic fields such as[^.]*\.", re.IGNORECASE)


def compile_keywords(keywords):
    """Matches whole words. Keywords in ALL CAPS are case-sensitive, so "AI" doesn't match "j'ai"."""
    return [
        re.compile(rf'(?<!\w){re.escape(kw)}(?!\w)', 0 if kw.isupper() else re.IGNORECASE)
        for kw in keywords
    ]


def matches_any(patterns, text):
    return any(pattern.search(text) for pattern in patterns)


def matches_domain(patterns, title, description):
    return matches_any(patterns, f"{title}\n{BOILERPLATE.sub('', description)}")


def scrape_job_details(url, headers):
    """Fetches the individual job page and returns its text, or None if that fails."""
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"  [!] Error fetching details for {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    main_content = soup.find('div', class_='contenu-offre') or soup.find('main') or soup.body
    if not main_content:
        print(f"  [!] No content found at {url}")
        return None

    for element in main_content(["script", "style", "nav", "footer", "header"]):
        element.decompose()

    return main_content.get_text(separator='\n\n', strip=True) or None


def get_inria_jobs(role_keywords=ROLE_KEYWORDS, domain_keywords=DOMAIN_KEYWORDS):
    """
    Returns internships in the target domain.
    Titles must match a role term. The title or full description must match a domain term, because
    many relevant titles name no AI term, such as "Stage : Reconnaissance d'entités nommées".
    Jobs whose details couldn't be fetched are kept with description=None, so dedup can report them.
    """
    print(f"Fetching job listings from: {INRIA_SEARCH_URL}...\n")
    try:
        response = requests.get(INRIA_SEARCH_URL, headers=SCRAPER_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching the main page: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    role_patterns = compile_keywords(role_keywords)
    domain_patterns = compile_keywords(domain_keywords)

    # 1. Gather unique job URLs whose titles name an internship
    job_dict = {}
    for link in soup.find_all('a', href=True):
        href = link['href']

        if "/public/classic/en/offres/" in href and any(char.isdigit() for char in href):
            job_title = link.get_text(strip=True)

            if matches_any(role_patterns, job_title):
                job_url = urljoin(INRIA_BASE_URL, href)
                if job_url not in job_dict:
                    job_dict[job_url] = job_title

    print(f"Found {len(job_dict)} internships. Fetching details...\n")

    # 2. Fetch details, then keep the jobs that match the domain
    job_listings = []
    for idx, (job_url, job_title) in enumerate(job_dict.items(), 1):
        print(f"[{idx}/{len(job_dict)}] Scraping: {job_title}")
        full_description = scrape_job_details(job_url, SCRAPER_HEADERS)

        if full_description is None or matches_domain(domain_patterns, job_title, full_description):
            job_listings.append({
                'source': 'inria',
                'id': job_url.split('/')[-1],
                'title': job_title,
                'company': 'Inria',
                'url': job_url,
                'description': full_description
            })

        time.sleep(0.5)

    print(f"\n{len(job_listings)} of {len(job_dict)} internships match the target domain.")
    return job_listings
