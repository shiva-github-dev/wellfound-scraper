# Wellfound ML Jobs Scraper - Project Context

## Goal
Scrape all ML engineer job listings from Wellfound (all 23 pages, ~838 jobs), extract structured data from listing and detail pages, classify/bucketize jobs, store in SQLite, and present via a Streamlit frontend with advanced filters.

**Current status:** Page 1 scraped (22 jobs). `about_company` field is broken — returns `NULL` for all jobs. Everything else works. Needs fix before scaling to all pages.

---

## Project Structure

```
D:\Wellfound_Scrape\
├── app.py                  # Streamlit frontend (filters, cards, CSV export)
├── database.py             # SQLite schema + CRUD operations
├── scraper.py              # Listing parser + detail parser + classification
├── run_pipeline.py         # Orchestrator (scraper → DB → CSV)
├── inspect_db.py           # Debug: inspect DB content row by row
├── verify_db.py            # Debug: verify DB state
├── debug_about.py          # Debug: fetch raw markdown for a detail page
├── debug_detail.py         # Debug: earlier detail page exploration
├── debug_detail2.py        # Debug: earlier detail page exploration
├── requirements.txt        # Python dependencies
├── wellfound_jobs.db       # SQLite database (currently 22 jobs)
└── CONTEXT.md              # THIS FILE
```

---

## Setup

### Environment
- **OS:** Windows (PowerShell 5.1)
- **User:** Shivaji Niranjan
- **Python:** standard `python` command

### Install dependencies
```powershell
cd D:\Wellfound_Scrape
pip install -r requirements.txt
python -m playwright install chromium
```

### Run
```powershell
# Scrape page 1 only (for testing)
python scraper.py --pages 1 --delay 2.5

# Scrape all 23 pages (~838 jobs, ~15 min)
python scraper.py --pages 23 --delay 3

# Launch Streamlit frontend
python -m streamlit run app.py
```

**IMPORTANT:** Use `;` not `&&` in PowerShell. F-strings with backslashes don't work in inline Python on Windows — use multi-line scripts or string concatenation.

---

## Data Flow

```
Listing page (crawl4ai)
    ↓ parse_listing_page() → list of {job_url, job_title, company_name, ...}
    ↓ ML relevance filter (keywords in title)
Detail pages (crawl4ai, one per job)
    ↓ parse_detail_page() → about_job, skills, company metadata, etc.
    ↓ build_full_record() → merge + classify + compute scores
SQLite DB (wellfound_jobs.db)
    ↓ Streamlit app reads with query_jobs() + filters
Streamlit frontend → CSV download
```

---

## Database Schema (jobs table — key fields)

| Field | Type | Notes |
|-------|------|-------|
| `job_url` | TEXT | Unique per job |
| `job_title` | TEXT | |
| `company_name` | TEXT | |
| `company_one_liner` | TEXT | From listing page |
| `company_size` | TEXT | e.g. "1-10 Employees" |
| `salary_raw` | TEXT | Raw salary text |
| `location_raw` | TEXT | |
| `remote_policy_raw` | TEXT | e.g. "Remote in USA" |
| `skills_listed` | TEXT | JSON array — merged from Skills section + text extraction |
| `about_job` | TEXT | Full job description text (cleaned) |
| `about_company` | TEXT | **BROKEN — always NULL** |
| `company_domain` | TEXT | e.g. "SaaS, Artificial Intelligence" |
| `company_market` | TEXT | e.g. "Robotics, Artificial Intelligence" |
| `company_type` | TEXT | e.g. "Startup, SaaS" |
| `company_stage` | TEXT | e.g. "Growth Stage" |
| `company_business_model` | TEXT | e.g. "B2B" |
| `company_size` | TEXT | e.g. "1-10 Employees" |
| `seniority_level` | TEXT | Classified: junior/mid/senior/staff/principal |
| `ml_domain` | TEXT | Classified: nlp, cv, llm, general, etc. |
| `salary_min` | INTEGER | Parsed from salary_raw |
| `salary_max` | INTEGER | Parsed from salary_raw |
| `equity_min` | REAL | Parsed from salary_raw |
| `equity_max` | REAL | Parsed from salary_raw |
| `visa_friendly` | INTEGER | 0/1 |
| `relocation_support` | INTEGER | 0/1 |
| `response_rate_score` | INTEGER | 0-100 scale (100=top 1%, 90=top 5%, 75=top 10%, 50=average, 0=unknown) |

Full schema: 55 columns. See `database.py` for complete definition.

---

## Parser Details

### Listing Page Parser (`parse_listing_page`)
- Source: `result.markdown` from crawl4ai on `https://wellfound.com/role/machine-learning-engineer?page={N}`
- Regex pattern: `\[(.+?)\]\((https://wellfound\.com/jobs/[^)]+)\)` to find job links
- Extracts: job_title, company_name, salary_raw, location_raw, remote_policy_raw, experience_raw, posted/reposted dates, visa, relocation, recruiter_active
- ML filter: `ML_KEYWORDS` list checks if job title contains ML-related terms
- Returns ~30 jobs per page, ~22 after ML filter

### Detail Page Parser (`parse_detail_page`)
- Source: `result.markdown` from crawl4ai on individual job URL
- Sections detected by `##` headers: About the job, About the company, Skills, Benefits, Compensation, Interview Process
- Company metadata: parsed from `![Company Type](icon)` / `![Company Industries](icon)` icon lines — value is on the NEXT line after the icon
- **`about_job`**: Extracted from `## About the job` section through to `## Skills`. Works correctly.
- **`about_company`**: **BROKEN** — always returns NULL. See Known Issues below.

### Classification (`build_full_record`)
- `seniority_level`: from job_title keywords (junior/mid/senior/staff/principal)
- `ml_domain`: from title, skills, about_job text (nlp, cv, llm, general, robotics, etc.)
- `salary_min/max`: regex on salary_raw ($120k-$180k format)
- `equity_min/max`: regex on equity text (0.1%, 0.5%, etc.)
- `visa_friendly`: 1 if visa_sponsorship contains "available" and not "not"
- `relocation_support`: 1 if relocation contains "allowed" and not "not"
- `response_rate_score`: tier mapping (Top 1% → 100, Top 5% → 90, Top 10% → 75, Average → 50, Unknown → 0)

### Skills Extraction (dual-source)
1. **Skills section**: `### Skills` header → lines starting with `*` → cleaned of markdown
2. **About Job text**: keyword matching against `TECH_SKILLS` list (~100 terms)
3. Both sources merged (deduplicated) into `skills_listed` as JSON array

---

## Known Issues

### 🔴 CRITICAL: `about_company` is always NULL
**Location:** `scraper.py`, `parse_detail_page()` function, `# --- About company` section

**Root cause:** The company section in crawl4ai markdown looks like this:
```
## About the company
[![Zenos company logo](...)](url)
### [Zenos](url)
AI productivity for the physical world1-10 Employees    ← one-liner + size concatenated
![Company Location](icon)
[San Francisco Bay Area](url)
![Company Size](icon)
1-10
![Company Type](icon)
Artificial Intelligence
...
```

The one-liner and employee count are on the **same line** with no separator (e.g. `AI productivity for the physical world1-10 Employees`). The current parser should split this with regex but it's not working — likely the `_is_junk_line()` filter or other filter is catching it before the split logic runs.

**What to do:**
1. Re-run `debug_about.py` to see raw markdown for a detail page
2. Examine the exact lines between `## About the company` and the next `##` header
3. Fix the parser to extract the one-liner (everything before the `N-N Employees` pattern) and the response rate text
4. Re-run `python scraper.py --pages 1 --delay 2.5` and verify with `python inspect_db.py`

### 🟡 MINOR: Some skills are false positives
The `TECH_SKILLS` keyword list matches substrings. E.g. "ros" matches inside words. Consider using word boundaries or a more precise matching approach.

### 🟡 MINOR: company_domain/type sometimes show "Private Company" or "Startup"
This is the actual value from Wellfound, not a parsing error. Some companies just label themselves that way.

---

## Pagination Info
- URL pattern: `https://wellfound.com/role/machine-learning-engineer?page={1..23}`
- 838 total results, ~36 per page (before ML filter)
- ~22 ML-relevant jobs per page after filter
- Estimated ~500-600 total ML jobs across all pages
- Crawl4AI has no issues with pagination (tested page 1)

---

## Crawl4AI Configuration
```python
BrowserConfig(
    headless=True,
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    extra_args=["--disable-blink-features=AutomationControlled"],  # NOTE: extra_args not args
    enable_stealth=True,  # Available in v0.9.3
)
CrawlerRunConfig(
    cache_mode=CacheMode.BYPASS,
    wait_for="css:body",
    delay_before_return_html=3.0,
)
```

---

## Streamlit Frontend (`app.py`)
- Runs at `http://localhost:8501`
- Sidebar filters: search, remote, ML domain, seniority, salary range, company, visa, relocation, response rate
- Sort: by salary, seniority, posted date, company, response rate
- Expandable job cards with tabs: About, Skills, Company, Salary, Compensation
- CSV download button
- Uses `query_jobs()` from `database.py` which supports all filter parameters

---

## OpenCode MCP Config
File: `C:\Users\Shivaji Niranjan\.config\opencode\opencode.jsonc`
- crawl4ai MCP server added (disabled — needs API token for cloud, or local SSE at `localhost:11235/mcp/sse`)
- langchain-docs MCP server connected

---

## Next Steps (Priority Order)

1. **Fix `about_company`** — Most important. The parser needs to extract the company description from the line that has one-liner + size concatenated. See Known Issues above.
2. **Re-run page 1** — After fixing, verify all fields populated correctly
3. **Scale to all 23 pages** — `python scraper.py --pages 23 --delay 3`
4. **Optional improvements:**
   - Better skill matching (word boundaries instead of substring)
   - Add company_funding parsing (currently raw text)
   - Add benefits parsing (currently raw text)
   - Improve about_job to strip markdown formatting more aggressively
