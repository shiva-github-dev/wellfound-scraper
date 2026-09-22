"""
Bucketize experience years from experience_raw field.
Parses patterns like "5-7 years", "3+ years", "at least 5 years" into numeric ranges.
"""
import sqlite3, re, sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = "D:\\Wellfound_Scrape\\wellfound_jobs.db"

# Buckets: (label, min_years, max_years)
BUCKETS = [
    ("Entry (0-2 yrs)",    0,   2),
    ("Mid (3-5 yrs)",      3,   5),
    ("Senior (5-8 yrs)",   5,   8),
    ("Staff (8-12 yrs)",   8,  12),
    ("Principal (12+ yrs)", 12, 99),
]


def parse_experience_years(raw: str):
    """Extract min and max years from experience_raw text."""
    if not raw:
        return None, None

    text = raw.lower().strip()

    # Pattern: "5-7 years" or "5 – 7 years" or "5 to 7 years"
    m = re.search(r"(\d+)\s*[-–to]+\s*(\d+)\s*years?", text)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Pattern: "5+ years" or "5 years minimum"
    m = re.search(r"(\d+)\s*\+?\s*years?", text)
    if m:
        return int(m.group(1)), int(m.group(1))

    # Pattern: "at least 5 years" or "minimum 5 years" or "over 5 years"
    m = re.search(r"(?:at\s+least|minimum|over|>\s*)(\d+)\s*years?", text)
    if m:
        return int(m.group(1)), int(m.group(1))

    # Pattern: "3, 5 years" or "3,5 years"
    m = re.search(r"(\d+)\s*,\s*(\d+)\s*years?", text)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Pattern: just a number like "5 years"
    m = re.search(r"(\d+)\s*years?", text)
    if m:
        return int(m.group(1)), int(m.group(1))

    return None, None


def bucketize(years):
    """Assign years to a bucket. Returns bucket label."""
    if years is None:
        return "Unknown"
    for label, lo, hi in BUCKETS:
        if lo <= years <= hi:
            return label
    # If above all buckets, last bucket
    return BUCKETS[-1][0]


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT experience_raw FROM jobs")
    rows = c.fetchall()
    conn.close()

    total = len(rows)
    bucket_counter = Counter()
    parsed_values = []
    unparsed = []

    for (raw,) in rows:
        lo, hi = parse_experience_years(raw)
        if lo is not None:
            avg = (lo + hi) / 2
            parsed_values.append(avg)
            bucket = bucketize(avg)
            bucket_counter[bucket] += 1
        else:
            unparsed.append(raw)
            bucket_counter["Unknown"] += 1

    # --- Print Results ---
    print(f"{'='*60}")
    print(f" EXPERIENCE DISTRIBUTION — {total} jobs")
    print(f"{'='*60}")
    print(f"{'Bucket':<25}{'Count':<8}{'%':<8}")
    print(f"{'-'*41}")

    for label, _, _ in BUCKETS:
        count = bucket_counter.get(label, 0)
        pct = 100 * count / total
        bar = '#' * int(pct / 2)
        print(f"{label:<25}{count:<8}{pct:>5.1f}%  {bar}")

    unknown = bucket_counter.get("Unknown", 0)
    pct_unk = 100 * unknown / total
    print(f"{'Unknown':<25}{unknown:<8}{pct_unk:>5.1f}%")

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f" SUMMARY")
    print(f"{'='*60}")
    print(f"Total jobs:           {total}")
    print(f"With experience data: {total - unknown}")
    print(f"Without:              {unknown}")

    if parsed_values:
        avg_exp = sum(parsed_values) / len(parsed_values)
        min_exp = min(parsed_values)
        max_exp = max(parsed_values)
        print(f"Avg experience:       {avg_exp:.1f} years")
        print(f"Min:                  {min_exp:.0f} years")
        print(f"Max:                  {max_exp:.0f} years")

    # --- Unparsed samples ---
    if unparsed:
        print(f"\nUnparsed experience_raw samples (first 10):")
        for s in unparsed[:10]:
            print(f"  '{s}'")


if __name__ == "__main__":
    main()
