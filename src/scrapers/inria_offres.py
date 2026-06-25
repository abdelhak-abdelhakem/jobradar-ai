import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from src.config import INRIA_BASE_URL, INRIA_SEARCH_URL, SCRAPER_HEADERS

def scrape_job_details(url, headers):
    """Fetches the individual job page and extracts the full description."""
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        main_content = soup.find('div', class_='contenu-offre') or soup.find('main')
        if not main_content:
            main_content = soup.body

        for element in main_content(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        full_text = main_content.get_text(separator='\n\n', strip=True)
        return full_text

    except requests.RequestException as e:
        print(f"  [!] Error fetching details for {url}: {e}")
        return "Error fetching description."

def get_inria_jobs():
    """Scrapes all jobs from the Inria job board and returns a structured list."""
    print(f"Fetching job listings from: {INRIA_SEARCH_URL}...\n")
    try:
        response = requests.get(INRIA_SEARCH_URL, headers=SCRAPER_HEADERS)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching the main page: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    job_listings = []

    # 1. Gather all unique job URLs and map them to their titles
    job_dict = {}
    for link in soup.find_all('a', href=True):
        href = link['href']
        if "/public/classic/en/offres/" in href and any(char.isdigit() for char in href):
            job_url = urljoin(INRIA_BASE_URL, href)
            job_title = link.get_text(strip=True)
            if job_url not in job_dict:
                job_dict[job_url] = job_title

    print(f"Found {len(job_dict)} unique jobs. Starting deep scrape...\n")

    # 2. Scrape full details for each job
    for idx, (job_url, job_title) in enumerate(job_dict.items(), 1):
        print(f"[{idx}/{len(job_dict)}] Scraping: {job_title}")
        job_id = job_url.split('/')[-1]
        full_description = scrape_job_details(job_url, SCRAPER_HEADERS)

        job_listings.append({
            'id': job_id,
            'title': job_title,
            'url': job_url,
            'description': full_description
        })

        time.sleep(0.5)  # be polite to the server
        
    return job_listings