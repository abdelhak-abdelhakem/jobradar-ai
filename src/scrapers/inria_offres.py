import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from src.config import INRIA_BASE_URL, INRIA_SEARCH_URL, SCRAPER_HEADERS, SEARCH_KEYWORDS

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

def get_inria_jobs(keywords=SEARCH_KEYWORDS):
    """Scrapes job listings, filters using regex word boundaries, and returns a structured list."""
    print(f"Fetching job listings from: {INRIA_SEARCH_URL}...\n")
    try:
        response = requests.get(INRIA_SEARCH_URL, headers=SCRAPER_HEADERS)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching the main page: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    job_listings = []
    
    # Compile regex patterns with word boundaries (\b) for each keyword
    # re.IGNORECASE removes the need for manual .lower() conversion
    patterns = [re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE) for kw in keywords]

    # 1. Gather all unique job URLs and filter them by title
    job_dict = {}
    for link in soup.find_all('a', href=True):
        href = link['href']
        
        if "/public/classic/en/offres/" in href and any(char.isdigit() for char in href):
            job_title = link.get_text(strip=True)
            
            # THE FIX: Check if any regex pattern matches as a distinct word
            if any(pattern.search(job_title) for pattern in patterns):
                job_url = urljoin(INRIA_BASE_URL, href)
                if job_url not in job_dict:
                    job_dict[job_url] = job_title

    print(f"Found {len(job_dict)} strictly relevant jobs matching your keywords. Starting deep scrape...\n")

    # 2. Scrape full details ONLY for the filtered jobs
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

        time.sleep(0.5)
        
    return job_listings