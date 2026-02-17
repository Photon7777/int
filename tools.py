import re
import requests
from bs4 import BeautifulSoup

def fetch_job_post(url: str, timeout: int = 15) -> str:
    """
    Basic HTML fetch + text extraction.
    Works for many sites, but some (LinkedIn, etc.) may block scraping.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Remove scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    # Clean excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:20000]  # keep it manageable

def safe_clip(text: str, limit: int = 20000) -> str:
    return (text or "")[:limit]