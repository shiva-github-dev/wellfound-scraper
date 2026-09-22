"""
Enrich existing DB rows by parsing about_job text.
Updates only empty fields — no data loss.
Exports enriched data to CSV.
"""
import sqlite3, json, sys, csv, os
sys.stdout.reconfigure(encoding="utf-8")

# Import the enrichment function from scraper
sys.path.insert(0, "D:\\Wellfound_Scrape")
from scraper import enrich_from_about_job

DB_PATH = "D:\\Wellfound_Scrape\\wellfound_jobs.db"
CSV_PATH = "D:\\Wellfound_Scrape\\wellfound_ml_jobs_enriched.csv"

# Fields that enrichment can populate
ENRICH_FIELDS = [
    "experience_raw", "requirements", "responsibilities",
    "education_requirements", "benefits",
]

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM jobs")
    rows = c.fetchall()
    print(f"Loaded {len(rows)} jobs from DB")

    updated = 0
    for row in rows:
        rec = dict(row)
        old_vals = {f: rec.get(f) for f in ENRICH_FIELDS}
        rec = enrich_from_about_job(rec)
        new_vals = {f: rec.get(f) for f in ENRICH_FIELDS}

        # Check if anything changed
        changed = False
        for f in ENRICH_FIELDS:
            if old_vals[f] != new_vals[f] and new_vals[f]:
                changed = True
                break

        if changed:
            updated += 1
            sets = []
            params = []
            for f in ENRICH_FIELDS:
                if new_vals[f] and new_vals[f] != old_vals[f]:
                    sets.append(f"{f} = ?")
                    params.append(new_vals[f])
            if sets:
                params.append(rec["id"])
                c.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?", params)

    conn.commit()
    print(f"Enriched {updated}/{len(rows)} jobs")

    # Show enrichment stats
    for f in ENRICH_FIELDS:
        c.execute(f"SELECT COUNT(*) FROM jobs WHERE {f} IS NOT NULL AND {f} != ''")
        n = c.fetchone()[0]
        print(f"  {f}: {n}/{len(rows)} populated")

    # Export to CSV
    c.execute("SELECT * FROM jobs")
    cols = [d[0] for d in c.description]
    all_rows = c.fetchall()

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        for r in all_rows:
            writer.writerow(list(r))

    print(f"\nCSV exported: {CSV_PATH}")
    print(f"File size: {os.path.getsize(CSV_PATH):,} bytes")
    conn.close()

if __name__ == "__main__":
    main()
