import sqlite3, sys, json
from collections import Counter

DB = r'D:\Wellfound_Scrape\wellfound_ds.db'

def parse_list(s):
    if not s:
        return []
    try:
        v = json.loads(s)
        if isinstance(v, list):
            return v
    except:
        pass
    return [x.strip().strip('"') for x in s.strip('[]').split(',') if x.strip() and x.strip() != 'null']

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute('SELECT skills_listed, ml_domain, seniority_level FROM jobs')
rows = c.fetchall()
conn.close()

# Merge duplicate skills (Python vs python)
skill_counter = Counter()
domain_counter = Counter()
level_counter = Counter()
for skills_raw, domains_raw, level in rows:
    for s in parse_list(skills_raw):
        skill_counter[s.lower()] += 1
    for d in parse_list(domains_raw):
        domain_counter[d] += 1
    if level:
        level_counter[level] += 1

total = len(rows)
print(f'=== DATA SCIENTIST SKILLS ({total} jobs) ===')
for s, ct in skill_counter.most_common(30):
    pct = ct / total * 100
    print(f'  {s:30s} {ct:4d} ({pct:.0f}%)')

print(f'\n=== DATA SCIENTIST DOMAINS ===')
for d, ct in domain_counter.most_common(25):
    pct = ct / total * 100
    print(f'  {d:30s} {ct:4d} ({pct:.0f}%)')

print(f'\n=== DATA SCIENTIST EXPERIENCE LEVELS ===')
total_levels = sum(level_counter.values())
for l, ct in level_counter.most_common():
    pct = ct / total * 100
    print(f'  {l:15s} {ct:4d} ({pct:.0f}%)')
unknown = total - total_levels
if unknown:
    print(f'  {"Unknown":15s} {unknown:4d} ({unknown/total*100:.0f}%)')
