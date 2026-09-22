"""
Wellfound ML Jobs Pipeline - Orchestrator
Run: python run_pipeline.py --pages 1
"""
import argparse
import sys
import asyncio

sys.stdout.reconfigure(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Wellfound ML Jobs Pipeline")
    parser.add_argument("--pages", type=int, default=1, help="Pages to scrape (default: 1)")
    parser.add_argument("--delay", type=float, default=2.5, help="Delay between requests (seconds)")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip scraping, just launch UI")
    args = parser.parse_args()

    # Step 1: Init DB
    from database import init_db, get_job_count
    init_db()

    # Step 2: Scrape (unless skipped)
    if not args.skip_scrape:
        from scraper import scrape_all
        from database import insert_jobs_batch

        print(f"\n{'='*60}")
        print(f"  WELLFOUND ML JOBS SCRAPER - {args.pages} page(s)")
        print(f"{'='*60}\n")

        records = asyncio.run(scrape_all(max_pages=args.pages, delay=args.delay))
        if records:
            insert_jobs_batch(records)
            print(f"\n[PIPELINE] {len(records)} jobs saved to database")
        else:
            print("\n[PIPELINE] No jobs scraped")

    # Step 3: Summary
    count = get_job_count()
    print(f"\n{'='*60}")
    print(f"  DATABASE: {count} total jobs")
    print(f"{'='*60}")

    if count == 0:
        print("\n[PIPELINE] No data. Run without --skip-scrape first.")
        return

    # Step 4: Launch Streamlit
    print("\n[PIPELINE] Launching Streamlit UI...")
    import subprocess
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", "8501",
        "--server.headless", "true",
    ])


if __name__ == "__main__":
    main()
