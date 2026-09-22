"""
Analyze most in-demand skills and ML domains from scraped job data.
Reads directly from the SQLite database — no re-scraping.
"""
import sqlite3, json, sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = "D:\\Wellfound_Scrape\\wellfound_jobs.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT skills_listed, ml_domain FROM jobs")
    rows = c.fetchall()
    conn.close()

    skill_counter = Counter()
    domain_counter = Counter()
    total_jobs = len(rows)

    for row in rows:
        # --- Skills ---
        skills_raw = row["skills_listed"]
        if skills_raw:
            try:
                skills = json.loads(skills_raw)
                for s in skills:
                    skill_counter[s.strip().lower()] += 1
            except (json.JSONDecodeError, TypeError):
                pass

        # --- ML Domain ---
        domain_raw = row["ml_domain"]
        if domain_raw:
            for d in domain_raw.split(","):
                d = d.strip()
                if d:
                    domain_counter[d] += 1

    # --- Print Skills ---
    print(f"{'='*60}")
    print(f" SKILL DEMAND — {total_jobs} jobs analyzed")
    print(f"{'='*60}")
    print(f"{'Rank':<6}{'Skill':<35}{'Count':<8}{'%':<8}")
    print(f"{'-'*57}")
    for rank, (skill, count) in enumerate(skill_counter.most_common(30), 1):
        pct = 100 * count / total_jobs
        bar = '#' * int(pct / 2)
        print(f"{rank:<6}{skill:<35}{count:<8}{pct:>5.1f}%  {bar}")

    # --- Print Domains ---
    print(f"\n{'='*60}")
    print(f" ML DOMAIN DEMAND — {total_jobs} jobs analyzed")
    print(f"{'='*60}")
    print(f"{'Rank':<6}{'Domain':<35}{'Count':<8}{'%':<8}")
    print(f"{'-'*57}")
    for rank, (domain, count) in enumerate(domain_counter.most_common(20), 1):
        pct = 100 * count / total_jobs
        bar = '#' * int(pct / 2)
        print(f"{rank:<6}{domain:<35}{count:<8}{pct:>5.1f}%  {bar}")

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f" SUMMARY")
    print(f"{'='*60}")
    print(f"Total jobs analyzed:    {total_jobs}")
    print(f"Unique skills found:    {len(skill_counter)}")
    print(f"Unique domains found:   {len(domain_counter)}")
    print(f"Top skill:              {skill_counter.most_common(1)[0][0]} ({skill_counter.most_common(1)[0][1]} jobs)")
    print(f"Top domain:             {domain_counter.most_common(1)[0][0]} ({domain_counter.most_common(1)[0][1]} jobs)")


if __name__ == "__main__":
    main()
