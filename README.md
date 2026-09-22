# Wellfound Job Scraper

Scrape, analyze, and explore AI/ML job listings from [Wellfound](https://wellfound.com) — built with Crawl4AI, SQLite, and Streamlit.

## What It Does

- **Scrapes** ML Engineer and Data Scientist roles from Wellfound (listings + full job details)
- **Extracts** skills, experience requirements, salary, domains, seniority levels
- **Enriches** jobs by parsing free-text descriptions for requirements, responsibilities, education, benefits
- **Presents** everything in an interactive dashboard with filters, pagination, and summary charts

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt
playwright install

# Scrape ML Engineer jobs (20 pages)
python scraper.py --pages 20 --delay 3.0

# Scrape Data Scientist jobs
python scraper.py --pages 20 --delay 3.0 --role data-scientist --db wellfound_ds.db

# Launch frontend
streamlit run app.py --server.port 8501
```

## Project Structure

```
scraper.py          # Crawl4AI scraper — listing/detail parsers, classification, enrichment
database.py         # SQLite schema (55 columns), CRUD operations, query helpers
app.py              # Streamlit frontend — Job Explorer + Summary Dashboard
requirements.txt    # Python dependencies
PROJECT_DOCS.md     # Full technical documentation
CONTEXT.md          # Quick-reference context for agents
```

## Frontend

Two tabs:

| Job Explorer | Summary Dashboard |
|-------------|-------------------|
| Filter by role, skills, domain, seniority, salary, company, remote | Top skills & domains (horizontal bar charts) |
| Sort by newest / salary | Salary breakdown by seniority |
| 20 jobs per page | Experience distribution |
| Expandable job details | Remote policy breakdown |
| CSV download | Separate ML Engineer & Data Scientist views |

## Commands

| Action | Command |
|--------|---------|
| Scrape ML jobs | `python scraper.py --pages 20 --delay 3.0` |
| Scrape DS jobs | `python scraper.py --pages 20 --delay 3.0 --role data-scientist --db wellfound_ds.db` |
| Run analysis | `python analyze_ds_full.py` |
| Export CSV | `python export_ds.py` |
| Launch app | `streamlit run app.py --server.port 8501` |

## Tech Stack

Crawl4AI · Playwright · SQLite · Streamlit · Altair · pandas

## Documentation

See [PROJECT_DOCS.md](PROJECT_DOCS.md) for full technical details — data pipeline, database schema, scraper internals, anti-bot measures, and more.
