import sqlite3, sys, json, re
from collections import Counter

DB = r'D:\Wellfound_Scrape\wellfound_ds.db'
EXCLUDE_SKILLS = {'hiring contact'}

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

def parse_experience(raw):
    if not raw:
        return None
    nums = re.findall(r'(\d+)', raw)
    nums = [int(n) for n in nums if 0 <= int(n) <= 40]
    if not nums:
        return None
    return min(nums)

def bucketize(exp):
    if exp is None:
        return 'Unknown'
    if exp <= 1:
        return 'Entry (0-1)'
    if exp <= 3:
        return 'Junior (2-3)'
    if exp <= 5:
        return 'Mid (4-5)'
    if exp <= 8:
        return 'Senior (6-8)'
    if exp <= 12:
        return 'Staff (9-12)'
    return 'Principal (13+)'

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute('SELECT skills_listed, ml_domain, seniority_level, experience_raw, salary_min, salary_max FROM jobs')
rows = c.fetchall()
conn.close()

total = len(rows)
skill_counter = Counter()
domain_counter = Counter()
level_counter = Counter()
exp_values = []
salary_by_bucket = {}

for skills_raw, domains_raw, level, exp_raw, smin, smax in rows:
    for s in parse_list(skills_raw):
        s_lower = s.lower()
        if s_lower not in EXCLUDE_SKILLS:
            skill_counter[s_lower] += 1
    for d in parse_list(domains_raw):
        domain_counter[d] += 1
    if level:
        level_counter[level] += 1
    exp = parse_experience(exp_raw)
    if exp is not None:
        exp_values.append(exp)
    if smin and smin > 0 and smax and smax > 0:
        b = bucketize(exp)
        if b not in salary_by_bucket:
            salary_by_bucket[b] = []
        salary_by_bucket[b].append((smin, smax))

print(f'=== DATA SCIENTIST SKILLS ({total} jobs) ===')
for s, ct in skill_counter.most_common(25):
    pct = ct / total * 100
    print(f'  {s:30s} {ct:4d} ({pct:.0f}%)')

print(f'\n=== DATA SCIENTIST DOMAINS ===')
for d, ct in domain_counter.most_common(20):
    pct = ct / total * 100
    print(f'  {d:30s} {ct:4d} ({pct:.0f}%)')

print(f'\n=== DATA SCIENTIST EXPERIENCE LEVELS ===')
for l, ct in level_counter.most_common():
    pct = ct / total * 100
    print(f'  {l:15s} {ct:4d} ({pct:.0f}%)')

# Bucketized experience
buckets = Counter()
for e in exp_values:
    buckets[bucketize(e)] += 1
print(f'\n=== BUCKETIZED EXPERIENCE ({len(exp_values)} with data) ===')
order = ['Entry (0-1)', 'Junior (2-3)', 'Mid (4-5)', 'Senior (6-8)', 'Staff (9-12)', 'Principal (13+)']
for b in order:
    ct = buckets.get(b, 0)
    if ct:
        pct = ct / total * 100
        print(f'  {b:20s} {ct:4d} ({pct:.0f}%)')
if exp_values:
    print(f'  Avg experience: {sum(exp_values)/len(exp_values):.1f} years')

# Salary by experience
if salary_by_bucket:
    print(f'\n=== SALARY BY EXPERIENCE ({sum(len(v) for v in salary_by_bucket.values())} with salary data) ===')
    for b in order:
        if b in salary_by_bucket:
            data = salary_by_bucket[b]
            avg_min = sum(s for s, _ in data) / len(data)
            avg_max = sum(s for _, s in data) / len(data)
            avg_mid = (avg_min + avg_max) / 2
            print(f'  {b:20s} {len(data):3d} jobs | avg ${avg_min:.0f}k-${avg_max:.0f}k (mid ${avg_mid:.0f}k)')
