"""
Run this once (or whenever the site content changes) to (re)build the
knowledge base. Replaces manually running notebook cells top to bottom.

Usage:
    python ingest.py

Add each teammate's category URL to CATEGORIES below so everyone's
scraped data lands in the same persistent collection.
"""

from scraper import scrape_category
from vector_store import add_chunks

# category_name -> category_url. Add one entry per teammate's section.
CATEGORIES = {
    "entertainment": "https://te.eg/web/guest/personal/services/entertainment",
    # "mobile": "https://te.eg/web/guest/personal/services/mobile",
    # "internet": "https://te.eg/web/guest/personal/services/internet",
    # "landline": "https://te.eg/web/guest/personal/services/landline",
    # ... add the rest as teammates finish their parts
}


def main():
    for category_name, category_url in CATEGORIES.items():
        print(f"\n=== Scraping category: {category_name} ===")
        chunks = scrape_category(category_url, category_name)
        print(f"Got {len(chunks)} chunks")
        add_chunks(chunks)

    print("\nIngest complete.")


if __name__ == "__main__":
    main()
