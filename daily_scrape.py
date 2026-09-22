"""
Daily Wellfound Scraper
=======================
Scrapes the first 3 pages of ML Engineer and Data Scientist roles,
adding only new jobs to the database. Designed to run daily via scheduler.

Usage:
    python daily_scrape.py                          # Scrape both roles
    python daily_scrape.py --role machine-learning-engineer  # ML only
    python daily_scrape.py --role data-scientist            # DS only
"""

import asyncio
import sys
import os
import sqlite3
import argparse
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from database import DB_PATH, SCHEMA, get_conn
from scraper import scrape_all

# --- Role configs ---
ROLES = {
    "machine-learning-engineer": {
        "db": "wellfound_jobs.db",
        "filter": [
            "machine learning", "ml engineer", "ml researcher", "ai engineer",
            "deep learning", "nlp", "computer vision", "data scientist",
            "applied scientist", "research scientist", "ai ml", "ml ops",
        ],
    },
    "data-scientist": {
        "db": "wellfound_ds.db",
        "filter": [
            "data scientist", "data science", "machine learning", "ml engineer",
            "ai engineer", "analytics", "applied scientist", "research scientist",
        ],
    },
}


def get_existing_urls(db_path):
    """Get all existing job URLs from the database."""
    if not os.path.exists(db_path):
        return set()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT job_url FROM jobs")
    urls = {row[0] for row in c.fetchall()}
    conn.close()
    return urls


def insert_new_jobs(db_path, records):
    """Insert only new jobs (skip existing URLs). Returns count of new jobs inserted."""
    if not records:
        return 0
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Ensure schema exists
    conn.executescript(SCHEMA)

    new_count = 0
    for rec in records:
        url = rec.get("job_url")
        if not url:
            continue
        c.execute("SELECT 1 FROM jobs WHERE job_url = ?", (url,))
        if c.fetchone():
            continue  # Already exists, skip

        cols = [
            "job_url", "job_title", "company_name",
            "company_one_liner", "company_size",
            "salary_raw", "location_raw", "remote_policy_raw",
            "is_remote", "experience_raw", "posted_date_raw",
            "reposted_date_raw", "job_type", "recruiter_active",
            "visa_sponsorship", "relocation", "remote_work_policy_detail",
            "company_domain", "company_market", "company_type",
            "company_funding", "company_funding_rounds",
            "company_employee_backgrounds", "company_stage",
            "company_business_model", "response_rate_tier",
            "response_time", "response_rate_raw", "response_rate_score",
            "skills_listed", "required_skills", "nice_to_have_skills",
            "about_company", "about_job", "requirements",
            "responsibilities", "education_requirements",
            "benefits", "compensation_details", "interview_process",
            "ml_domain", "seniority_level", "salary_min", "salary_max",
            "equity_min", "equity_max", "total_comp_estimate",
            "is_ai_native", "remote_friendly_score", "visa_friendly",
            "relocation_support", "growth_signal",
        ]
        vals = [rec.get(c_name) for c_name in cols]
        placeholders = ", ".join(["?"] * len(cols))
        sql = f"INSERT OR REPLACE INTO jobs ({', '.join(cols)}) VALUES ({placeholders})"
        c.execute(sql, vals)
        new_count += 1

    conn.commit()
    conn.close()
    return new_count


async def daily_scrape_role(role, max_pages=3, delay=3.0):
    """Scrape a role and return new job count."""
    config = ROLES[role]
    db_path = os.path.join(os.path.dirname(__file__), config["db"])

    existing_urls = get_existing_urls(db_path)
    print(f"\n{'='*60}")
    print(f"[{role}] Existing jobs in DB: {len(existing_urls)}")

    records = await scrape_all(
        max_pages=max_pages,
        delay=delay,
        role=role,
        role_filter=config["filter"],
    )

    # Filter out existing URLs
    new_records = [r for r in records if r.get("job_url") not in existing_urls]
    print(f"[{role}] Scraped: {len(records)} | New: {len(new_records)} | Skipped: {len(records) - len(new_records)}")

    # Insert new jobs
    inserted = insert_new_jobs(db_path, new_records)
    print(f"[{role}] Inserted: {inserted} new jobs to {config['db']}")

    # Log new jobs
    if new_records:
        print(f"\n[{role}] New jobs found:")
        for i, rec in enumerate(new_records, 1):
            title = rec.get("job_title", "?")
            company = rec.get("company_name", "?")
            salary = rec.get("salary_raw", "N/A")
            print(f"  {i:3d}. {title} @ {company} | {salary}")
    else:
        print(f"[{role}] No new jobs found.")

    return inserted


async def main(roles=None, max_pages=3, delay=3.0):
    """Run daily scrape for specified roles."""
    start = datetime.now()
    print(f"[DAILY SCRAPE] Started at {start.strftime('%Y-%m-%d %H:%M:%S')}")

    if roles is None:
        roles = list(ROLES.keys())

    total_new = 0
    for role in roles:
        if role not in ROLES:
            print(f"[WARN] Unknown role: {role}, skipping")
            continue
        new = await daily_scrape_role(role, max_pages=max_pages, delay=delay)
        total_new += new

    end = datetime.now()
    elapsed = (end - start).total_seconds()
    print(f"\n{'='*60}")
    print(f"[DAILY SCRAPE] Completed at {end.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[DAILY SCRAPE] Total new jobs: {total_new} | Duration: {elapsed:.0f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily Wellfound Job Scraper")
    parser.add_argument("--role", nargs="*", choices=list(ROLES.keys()),
                        help="Roles to scrape (default: all)")
    parser.add_argument("--pages", type=int, default=3,
                        help="Pages per role (default: 3)")
    parser.add_argument("--delay", type=float, default=3.0,
                        help="Delay between requests in seconds")
    args = parser.parse_args()

    asyncio.run(main(roles=args.role, max_pages=args.pages, delay=args.delay))
