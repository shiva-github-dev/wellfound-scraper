# Wellfound Job Scraper — Project Documentation

## 1. Overview

End-to-end pipeline that scrapes AI/ML job listings from [Wellfound](https://wellfound.com), extracts structured data, enriches it via text analysis, stores it in SQLite, and presents it through an interactive Streamlit frontend.

**Flow:** Scrape → Parse → Classify → Enrich → Store → Present

**Current datasets:**
| Role | Jobs Scraped | DB File | CSV Export |
|------|-------------|---------|------------|
| ML Engineer | 258 | `wellfound_jobs.db` | `wellfound_ml_jobs_enriched.csv` |
| Data Scientist | 243 | `wellfound_ds.db` | `wellfound_ds_jobs_enriched.csv` |

---

## 2. Tech Stack

| Component | Library | Version |
|-----------|---------|---------|
| Web Scraping | Crawl4AI | ≥ 0.9.0 |
| Browser Engine | Playwright (via Crawl4AI) | bundled |
| Database | SQLite3 | stdlib |
| Data Processing | pandas | ≥ 2.0.0 |
| Frontend | Streamlit | ≥ 1.30.0 |
| Charts | Altair | (Streamlit dependency) |
| Language | Python | 3.10+ |

**Anti-bot measures:** Crawl4AI stealth mode (`enable_stealth=True`), custom user agent, `--disable-blink-features=AutomationControlled` Chrome arg.

---

## 3. Project Structure

```
D:\Wellfound_Scrape\
├── scraper.py              # Main scraper — listing parser, detail parser, enrichment, CLI
├── database.py             # SQLite schema, CRUD operations, filter/query helpers
├── app.py                  # Streamlit frontend — Job Explorer + Summary Dashboard
│
├── wellfound_jobs.db       # ML Engineer SQLite database
├── wellfound_ds.db         # Data Scientist SQLite database
│
├── wellfound_ml_jobs_enriched.csv   # ML Engineer CSV export
├── wellfound_ds_jobs_enriched.csv   # Data Scientist CSV export
│
├── requirements.txt        # Python dependencies
├── CONTEXT.md              # Quick-reference context for other agents
├── PROJECT_DOCS.md         # This file
│
├── analyze_ds_full.py      # DS skills/domains/experience/salary analysis
├── analyze_skills.py       # Skills frequency analysis
├── analyze_experience.py   # Experience bucketization
├── analyze_exp_salary.py   # Combined experience + salary analysis
├── export_ds.py            # Export DS DB to CSV
├── enrich_existing.py      # Enrich existing DB records + CSV export
└── run_pipeline.py         # Combined scrape + enrich pipeline runner
```

---

## 4. Data Pipeline (End-to-End)

### 4.1 Scraping (`scraper.py`)

**Entry point:** `python scraper.py --pages 20 --delay 2.5 --role data-scientist`

1. **Listing pages** — Fetches `https://wellfound.com/role/{role}?page={N}`
   - Parses markdown to extract job cards: title, URL, company, salary, location, remote status, experience, posted date
   - Filters by role-specific title keywords (e.g., ML roles filter for "machine learning", "ai engineer", etc.)

2. **Detail pages** — For each job URL, fetches the full job posting
   - Extracts: visa, relocation, remote policy, skills section, response rate, about_job, about_company, requirements, responsibilities, education, benefits, company info (domain, market, stage, funding, business model)

3. **Anti-bot:** Cloudflare blocks rapid requests to higher page numbers (typically pages 20+). Mitigated by:
   - `--delay` parameter (default 2.5s, recommended 3-4s)
   - Stealth mode + custom user agent
   - Data commits per page via `on_page_done` callback (survives timeout/block)

### 4.2 Storage (`database.py`)

**Schema:** 55 columns in `jobs` table with `job_url UNIQUE` for deduplication.

Key operations:
- `INSERT OR REPLACE` — deduplicates by `job_url`
- `insert_jobs_batch()` — inserts list of job dicts
- `get_all_jobs(filters)` — retrieves with optional filter dict
- Indexes on: `company_name`, `is_remote`, `salary_min/max`, `seniority_level`, `ml_domain`, `posted_date_raw`, `response_rate_score`

### 4.3 Classification (`scraper.py` → `build_full_record()`)

| Field | Method |
|-------|--------|
| `seniority_level` | Title keyword match ("senior" → Senior, "staff" → Staff, etc.) + experience years fallback |
| `ml_domain` | Keyword matching across title + skills + about_job text → "NLP", "Computer Vision", "MLOps", etc. |
| `is_remote` | Keyword match on remote_policy + location |
| `response_rate_score` | Tier text → numeric (Top 1% → 100, Top 5% → 90, Top 10% → 75) |
| `is_ai_native` | Company domain contains AI/ML keywords |
| `visa_friendly` | Visa sponsorship text contains "available" and not "not" |
| `relocation_support` | Relocation text contains "allowed" and not "not" |
| `growth_signal` | About company contains "growing fast" or "hiring growth" |

### 4.4 Enrichment (`scraper.py` → `enrich_from_about_job()`)

Parses `about_job` free text to fill missing fields:

- **Experience** — Regex patterns: "5-7 years", "5+ years", "at least 3 years"
- **Requirements** — Extracts section under headers like "Who You Are", "Qualifications", "Requirements"
- **Responsibilities** — Extracts section under "What You'll Do", "Responsibilities", "The Role"
- **Education** — Regex for "BS/MS/PhD in CS/Engineering/..."
- **Benefits** — Extracts section under "Benefits", "Perks", "What We Offer"

### 4.5 Skills Extraction (dual-source)

1. **Skills section** — Parsed from the dedicated "Skills" section on the job page
2. **Text extraction** — Matches `TECH_SKILLS` list (~150 known skills) against `about_job` + `requirements` + `responsibilities` text

Skills from both sources are merged and deduplicated.

---

## 5. Database Schema

**55 columns** in `jobs` table. Key columns:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment primary key |
| `job_url` | TEXT | Unique job URL (dedup key) |
| `job_title` | TEXT | Job title |
| `company_name` | TEXT | Company name |
| `salary_raw` | TEXT | Raw salary string (e.g., "$160k - $225k") |
| `salary_min` | INTEGER | Parsed minimum salary in $K |
| `salary_max` | INTEGER | Parsed maximum salary in $K |
| `experience_raw` | TEXT | Raw experience string (e.g., "5+ years") |
| `skills_listed` | TEXT | JSON array of skills |
| `ml_domain` | TEXT | Comma-separated ML domains |
| `seniority_level` | TEXT | Junior/Mid/Senior/Staff/Principal |
| `about_job` | TEXT | Full job description text |
| `about_company` | TEXT | Company description |
| `requirements` | TEXT | Extracted requirements |
| `responsibilities` | TEXT | Extracted responsibilities |
| `education_requirements` | TEXT | Extracted education requirements |
| `benefits` | TEXT | Extracted benefits |
| `is_remote` | TEXT | Yes/No/Hybrid/Unknown |
| `visa_friendly` | INTEGER | 1 if visa sponsorship available |
| `relocation_support` | INTEGER | 1 if relocation supported |
| `response_rate_score` | INTEGER | 0-100 response rate score |
| `is_ai_native` | INTEGER | 1 if company is AI-focused |
| `scraped_at` | TIMESTAMP | When the job was scraped |

---

## 6. Scraper Details

### CLI Arguments

```bash
python scraper.py --pages 20 --delay 3.0 --role data-scientist --db path/to/db.db
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--pages` | 1 | Number of listing pages to scrape |
| `--delay` | 2.5 | Seconds between requests |
| `--role` | `machine-learning-engineer` | Wellfound role slug |
| `--db` | `wellfound_jobs.db` | SQLite database path |
| `--csv` | None | CSV output path |

### Role Configuration

Each role has a title filter list to exclude irrelevant jobs:

```python
ROLE_FILTERS = {
    "machine-learning-engineer": ["machine learning", "ml engineer", "ai engineer", ...],
    "data-scientist": ["data scientist", "data science", "analytics", ...],
}
```

### Anti-Bot Workarounds

- **Stealth mode:** `enable_stealth=True` in `BrowserConfig`
- **Custom user agent:** Chrome 120 UA string
- **Chrome args:** `--disable-blink-features=AutomationControlled`
- **Rate limiting:** `--delay` between requests (3-4s recommended)
- **Incremental commits:** `on_page_done` callback saves data per page — survives Cloudflare blocks or timeouts
- **Page range limit:** Cloudflare typically blocks after ~15-20 pages; stay within accessible range

---

## 7. Frontend Architecture (`app.py`)

**Launch:** `streamlit run app.py --server.port 8501 --server.headless true`

### Tab 1: Job Explorer

**Sidebar filters** (all AND-combined):
| Filter | Type | Logic |
|--------|------|-------|
| Job Role | Multiselect | ANY match (ML Engineer, Data Scientist) |
| Search | Text input | Matches job_title, company_name, skills_listed, about_job |
| ML Domain | Multiselect | ANY match against parsed domain list |
| Skills | Multiselect | ANY match against parsed skill list |
| Seniority | Multiselect | Exact match |
| Remote Policy | Multiselect | Exact match |
| Max Salary | Slider | Shows jobs with salary_max ≤ slider |
| Company | Multiselect | Exact match |
| Visa/Relocation | Checkboxes | AND filter |

**Pagination:** 20 jobs per page with page number input.

**Sort:** Newest (by `posted_date_raw` parsed from relative dates), Highest Salary, Lowest Salary.

**Job cards:** Title, company, salary, location, remote badge, role badge, tags, expandable details (3 tabs: Job Details, Company, Classification).

### Tab 2: Summary Dashboard

Two sub-tabs: **ML Engineer** and **Data Scientist**. Each shows:
- Top Skills (horizontal bar chart, sorted descending)
- Top Domains (horizontal bar chart)
- Seniority Distribution (horizontal bar chart)
- Salary by Seniority (dataframe + horizontal bar chart)
- Experience Requirements (bucketized horizontal bar chart)
- Remote Policy (horizontal bar chart)

---

## 8. Commands Reference

### Scraping
```bash
# ML Engineer (default)
python scraper.py --pages 20 --delay 3.0

# Data Scientist
python scraper.py --pages 20 --delay 3.0 --role data-scientist --db wellfound_ds.db
```

### Enrichment & Export
```bash
# Enrich existing DB + export CSV
python enrich_existing.py

# Export DS to CSV
python export_ds.py
```

### Analysis
```bash
# Full DS analysis (skills, domains, experience, salary)
python analyze_ds_full.py

# Skills frequency
python analyze_skills.py

# Experience bucketization
python analyze_experience.py

# Combined experience + salary
python analyze_exp_salary.py
```

### Frontend
```bash
# Launch Streamlit
streamlit run app.py --server.port 8501 --server.headless true
```

---

## 9. Known Limitations

| Issue | Details |
|-------|---------|
| **Cloudflare blocking** | Pages 15-20+ get blocked. Workaround: stay within ~15 pages with delays. |
| **Relative dates only** | `posted_date_raw` is relative ("3 days ago"), not exact. Converted to approximate datetime for sorting. |
| **Salary precision** | Stored as integers in $K (e.g., 160 = $160k). No sub-$K precision. |
| **Skills false positives** | Some non-skill items ("hiring contact", image URLs) occasionally appear in skills list. |
| **Duplicate listings** | Same job may appear under different URLs. Deduplication is by `job_url` only. |
| **No authentication** | Cannot access logged-in content or application pages. |

---

## 10. Future Improvements

- [ ] **Retry logic** — Automatic retry with exponential backoff on Cloudflare blocks
- [ ] **Proxy rotation** — Rotate IPs to avoid rate limiting
- [ ] **Historical tracking** — Track job posting/removal over time for trend analysis
- [ ] **Salary normalization** — Handle non-USD currencies, equity, bonus breakdowns
- [ ] **Skills taxonomy** — Map related skills (e.g., "pytorch" → "deep learning frameworks")
- [ ] **Company enrichment** — Pull company data from Crunchbase or LinkedIn
- [ ] **Export formats** — JSON, Excel export options
- [ ] **Saved searches** — Let users save filter combinations
- [ ] **Email alerts** — Notify when new matching jobs appear
- [ ] **More roles** — Expand to Software Engineer, Product Manager, etc.
