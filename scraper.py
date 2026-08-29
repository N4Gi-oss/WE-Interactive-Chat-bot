"""
Scraper for te.eg (Telecom Egypt) service pages.
Extracted from the original prototyping notebook, unchanged in logic —
only reorganized into a reusable module.
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from collections import Counter

BASE_URL = "https://te.eg"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

NOISE_KEYWORDS = [
    "Copyright", "حقوق النشر", "NTRA", "الرجوع الي الأعلي",
    "Return To Top", "تواصل معنا", "حمل التطبيق",
    "الفروع", "أسئلة متكرره", "اتصل بنا", "155",
]


def is_noise(text: str) -> bool:
    return any(keyword in text for keyword in NOISE_KEYWORDS)


def discover_service_links(category_url: str) -> set[str]:
    """Get all sub-service links from a category page."""
    response = requests.get(category_url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(response.content, "html.parser")

    links = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if "/w/" in href:
            links.add(urljoin(BASE_URL, href))
    return links


def extract_raw_lines(page_url: str) -> list[str]:
    """Get all unique text lines from a single page (dedup within the same page)."""
    response = requests.get(page_url, headers=HEADERS, timeout=15)
    if response.status_code != 200:
        return []
    soup = BeautifulSoup(response.content, "html.parser")

    lines = []
    seen = set()
    for tag in soup.find_all(["h1", "h2", "h3", "p", "li"]):
        text = re.sub(r"\s+", " ", tag.get_text(strip=True, separator=" "))
        if len(text) > 10 and text not in seen:
            lines.append(text)
            seen.add(text)
    return lines


def build_boilerplate_set(pages_raw_lines) -> set[str]:
    """Lines repeated across more than one page are nav/footer boilerplate."""
    counter = Counter()
    for lines in pages_raw_lines:
        counter.update(set(lines))
    return {line for line, count in counter.items() if count > 1}


def chunk_page(content: str, max_chars: int = 500, min_chars: int = 50) -> list[str]:
    """Split page content into chunks, keeping sentences intact.
    Merges a too-short trailing chunk into the previous one instead of
    leaving an orphan chunk."""
    sentences = re.split(r"(?<=[.!؟?])\s+", content)

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_chars:
            current_chunk += (" " if current_chunk else "") + sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk)

    if len(chunks) > 1 and len(chunks[-1]) < min_chars:
        chunks[-2] = chunks[-2] + " " + chunks[-1]
        chunks.pop()

    return chunks


def scrape_category(category_url: str, category_name: str) -> list[dict]:
    """
    Full pipeline for one category page: discover -> extract -> clean -> chunk.
    Returns a list of chunk dicts ready to be embedded.
    """
    service_links = discover_service_links(category_url)

    all_pages_lines = {link: extract_raw_lines(link) for link in service_links}
    boilerplate = build_boilerplate_set(all_pages_lines.values())

    knowledge_base = []
    for url, lines in all_pages_lines.items():
        clean_lines = [l for l in lines if l not in boilerplate and not is_noise(l)]
        if clean_lines:
            knowledge_base.append({"url": url, "content": " ".join(clean_lines)})

    final_chunks = []
    for item in knowledge_base:
        page_chunks = chunk_page(item["content"])
        for i, chunk_text in enumerate(page_chunks):
            final_chunks.append({
                "chunk_id": f"{category_name}_{item['url'].split('/')[-1]}_{i}",
                "url": item["url"],
                "text": chunk_text,
                "category": category_name,
                "source_type": "website",
            })

    return final_chunks
