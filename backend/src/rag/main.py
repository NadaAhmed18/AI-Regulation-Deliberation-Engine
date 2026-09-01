# python -m src.rag.main --url "https://en.wikipedia.org/wiki/Ethics_of_artificial_intelligence"
# python -m src.rag.main --links-file data/seed_links.txt

import argparse
import asyncio
import os

from src.rag.stages.scraper import ingest_batch
from src.rag.stages.ingestion import ingest_documents

async def run_from_urls(urls: list, batch_size: int = 10, save_html: bool = False):
    """
    Runs the scraper first, then passes data to the pipeline.
    Processes URLs in batches to prevent rate limits or memory overload.
    """
    print(f"\n[*] Starting end-to-end pipeline for {len(urls)} URLs...")
    
    all_scraped_docs = []
    
    # Process in batches of 10
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i + batch_size]
        print(f"\n[>>>] Processing Batch {i//batch_size + 1}/{(len(urls) + batch_size - 1)//batch_size} ({len(batch)} URLs)...")
        
        # Pass the save_html flag down to the scraper
        scraped_docs = await ingest_batch(batch, save_html=save_html)
        if scraped_docs:
            all_scraped_docs.extend(scraped_docs)
            
            # Immediately ingest this batch into Neo4j to keep memory usage low
            print(f"[*] Moving batch {i//batch_size + 1} to Database Ingestion...")
            ingest_documents(scraped_docs)
        else:
            print(f"[-] No valid documents retrieved in batch {i//batch_size + 1}.")

    print(f"\n[+] Finished entirely! Total documents processed and saved: {len(all_scraped_docs)}")


def run_from_links_file(filepath: str, save_html: bool = False):
    """Reads a text file of URLs, ignoring comments and empty lines."""
    filepath = os.path.join(os.getcwd(), filepath)
    print(f"\n[*] Reading URLs from {filepath}...")
    if not os.path.exists(filepath):
        print(f"[-] Error: File {filepath} not found.")
        return
        
    urls = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Ignore empty lines and comments
            if line and not line.startswith("#"):
                urls.append(line)
                
    if not urls:
        print("[-] No valid URLs found in file.")
        return
        
    print(f"[*] Found {len(urls)} valid URLs.")
    asyncio.run(run_from_urls(urls, save_html=save_html))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Regulation RAG Pipeline Orchestrator")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", type=str, help="A single URL to scrape and ingest")
    group.add_argument("--links-file", type=str, help="Path to a TXT file containing a list of URLs")
    parser.add_argument("--save-html", action="store_true", help="Save raw HTML files to data/raw/ directory for reviewer verification.")
    
    args = parser.parse_args()

    if args.url:
        asyncio.run(run_from_urls([args.url], save_html=args.save_html))
    elif args.links_file:
        run_from_links_file(args.links_file, save_html=args.save_html)