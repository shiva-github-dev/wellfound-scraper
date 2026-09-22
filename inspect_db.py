import sys
sys.stdout.reconfigure(encoding="utf-8")
import sqlite3

conn = sqlite3.connect("D:/Wellfound_Scrape/wellfound_jobs.db")
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM jobs LIMIT 5").fetchall()

for r in rows:
    title = r["job_title"]
    company = r["company_name"]
    print(f"--- {title} @ {company} ---")
    print(f"skills_listed: {r['skills_listed']}")
    print(f"company_domain: {r['company_domain']}")
    print(f"company_market: {r['company_market']}")
    print(f"company_type: {r['company_type']}")
    print(f"company_stage: {r['company_stage']}")
    print(f"company_business_model: {r['company_business_model']}")
    print(f"company_size: {r['company_size']}")
    ac = r["about_company"]
    print(f"about_company (raw, first 400): {ac[:400] if ac else None}")
    aj = r["about_job"]
    print(f"about_job (first 300): {aj[:300] if aj else None}")
    print()

conn.close()
