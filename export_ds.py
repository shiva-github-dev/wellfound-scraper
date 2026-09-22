import sqlite3, csv, sys

DB = r'D:\Wellfound_Scrape\wellfound_ds.db'
CSV_OUT = r'D:\Wellfound_Scrape\wellfound_ds_jobs_enriched.csv'

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute('SELECT * FROM jobs ORDER BY id')
rows = c.fetchall()
cols = [d[0] for d in c.description]
conn.close()

with open(CSV_OUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow(dict(r))

print(f'Exported {len(rows)} jobs to {CSV_OUT}')
