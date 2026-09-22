"""
Combined analysis: experience buckets + salary ranges.
"""
import sqlite3, re, sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = "D:\\Wellfound_Scrape\\wellfound_jobs.db"

BUCKETS = [
    ("Entry (0-2 yrs)",    0,   2),
    ("Mid (3-5 yrs)",      3,   5),
    ("Senior (5-8 yrs)",   5,   8),
    ("Staff (8-12 yrs)",   8,  12),
    ("Principal (12+ yrs)", 12, 99),
]


def parse_exp(raw):
    if not raw:
        return None
    text = raw.lower().strip()
    m = re.search(r"(\d+)\s*[-\u2013to]+\s*(\d+)\s*years?", text)
    if m: return (int(m.group(1)) + int(m.group(2))) / 2
    m = re.search(r"(\d+)\s*\+?\s*years?", text)
    if m: return int(m.group(1))
    m = re.search(r"(?:at\s+least|minimum|over)\s+(\d+)\s*years?", text)
    if m: return int(m.group(1))
    return None


def bucketize(y):
    if y is None: return "Unknown"
    for label, lo, hi in BUCKETS:
        if lo <= y <= hi: return label
    return BUCKETS[-1][0]


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT experience_raw, salary_min, salary_max, seniority_level, ml_domain FROM jobs")
    rows = c.fetchall()
    conn.close()

    total = len(rows)
    exp_buckets = Counter()
    sal_by_exp = defaultdict(list)
    seniority_by_exp = defaultdict(Counter)
    domain_by_exp = defaultdict(Counter)

    for exp_raw, sal_min, sal_max, seniority, domain in rows:
        y = parse_exp(exp_raw)
        b = bucketize(y)
        exp_buckets[b] += 1

        if sal_max:
            sal_by_exp[b].append(sal_max)
        if seniority:
            seniority_by_exp[b][seniority] += 1
        if domain:
            for d in domain.split(","):
                d = d.strip()
                if d:
                    domain_by_exp[b][d] += 1

    # --- Experience Distribution ---
    print(f"{'='*65}")
    print(f" EXPERIENCE DISTRIBUTION — {total} jobs")
    print(f"{'='*65}")
    print(f"{'Bucket':<25}{'Count':<8}{'%':<8}{'Avg Salary':<12}{'Top Seniority'}")
    print(f"{'-'*65}")

    for label, _, _ in BUCKETS:
        count = exp_buckets.get(label, 0)
        pct = 100 * count / total
        salaries = sal_by_exp.get(label, [])
        avg_sal = f"${sum(salaries)//len(salaries)}k" if salaries else "N/A"
        top_sen = seniority_by_exp[label].most_common(1)[0][0] if seniority_by_exp[label] else "N/A"
        bar = '#' * int(pct / 2)
        print(f"{label:<25}{count:<8}{pct:>5.1f}%  {avg_sal:<12}{top_sen}  {bar}")

    unknown = exp_buckets.get("Unknown", 0)
    print(f"{'Unknown':<25}{unknown:<8}{100*unknown/total:>5.1f}%")

    # --- Top Domains per Experience Level ---
    print(f"\n{'='*65}")
    print(f" TOP DOMAINS BY EXPERIENCE LEVEL")
    print(f"{'='*65}")
    for label, _, _ in BUCKETS:
        if label in domain_by_exp:
            top3 = domain_by_exp[label].most_common(3)
            domains_str = ", ".join(f"{d}({c})" for d, c in top3)
            print(f"  {label:<25} {domains_str}")

    # --- Summary ---
    all_salaries = [s for sals in sal_by_exp.values() for s in sals]
    print(f"\n{'='*65}")
    print(f" SUMMARY")
    print(f"{'='*65}")
    print(f"Total jobs:              {total}")
    print(f"With experience data:    {total - unknown}")
    print(f"Avg experience:          {sum(parse_exp(r[0]) or 0 for r in rows if parse_exp(r[0])) / max(1, total - unknown):.1f} years")
    if all_salaries:
        print(f"Avg max salary (overall): ${sum(all_salaries)//len(all_salaries)}k")


if __name__ == "__main__":
    main()
