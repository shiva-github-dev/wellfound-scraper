import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_PATH = Path(__file__).parent / "wellfound_jobs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_url TEXT UNIQUE NOT NULL,
    job_title TEXT NOT NULL,
    company_name TEXT NOT NULL,

    company_one_liner TEXT,
    company_size TEXT,
    salary_raw TEXT,
    location_raw TEXT,
    remote_policy_raw TEXT,
    is_remote TEXT,
    experience_raw TEXT,
    posted_date_raw TEXT,
    reposted_date_raw TEXT,
    job_type TEXT,
    recruiter_active INTEGER,

    visa_sponsorship TEXT,
    relocation TEXT,
    remote_work_policy_detail TEXT,

    company_domain TEXT,
    company_market TEXT,
    company_type TEXT,
    company_funding TEXT,
    company_funding_rounds TEXT,
    company_employee_backgrounds TEXT,
    company_stage TEXT,
    company_business_model TEXT,

    response_rate_tier TEXT,
    response_time TEXT,
    response_rate_raw TEXT,
    response_rate_score INTEGER,

    skills_listed TEXT,
    required_skills TEXT,
    nice_to_have_skills TEXT,

    about_company TEXT,
    about_job TEXT,
    requirements TEXT,
    responsibilities TEXT,
    education_requirements TEXT,
    benefits TEXT,
    compensation_details TEXT,
    interview_process TEXT,

    ml_domain TEXT,
    seniority_level TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    equity_min REAL,
    equity_max REAL,
    total_comp_estimate INTEGER,
    is_ai_native INTEGER,
    remote_friendly_score INTEGER,
    visa_friendly INTEGER,
    relocation_support INTEGER,
    growth_signal INTEGER,

    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_name);
CREATE INDEX IF NOT EXISTS idx_jobs_remote ON jobs(is_remote);
CREATE INDEX IF NOT EXISTS idx_jobs_salary ON jobs(salary_min, salary_max);
CREATE INDEX IF NOT EXISTS idx_jobs_seniority ON jobs(seniority_level);
CREATE INDEX IF NOT EXISTS idx_jobs_domain ON jobs(ml_domain);
CREATE INDEX IF NOT EXISTS idx_jobs_posted ON jobs(posted_date_raw);
CREATE INDEX IF NOT EXISTS idx_jobs_response ON jobs(response_rate_score);
"""


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH}")


def insert_job(job: Dict[str, Any]) -> int:
    conn = get_conn()
    c = conn.cursor()
    cols = [
        "job_url", "job_title", "company_name",
        "company_one_liner", "company_size",
        "salary_raw", "location_raw", "remote_policy_raw",
        "is_remote", "experience_raw", "posted_date_raw",
        "reposted_date_raw", "job_type", "recruiter_active",
        "visa_sponsorship", "relocation", "remote_work_policy_detail",
        "company_domain", "company_market", "company_type",
        "company_funding", "company_funding_rounds",
        "company_employee_backgrounds", "company_stage",
        "company_business_model", "response_rate_tier",
        "response_time", "response_rate_raw", "response_rate_score",
        "skills_listed", "required_skills", "nice_to_have_skills",
        "about_company", "about_job", "requirements",
        "responsibilities", "education_requirements",
        "benefits", "compensation_details", "interview_process",
        "ml_domain", "seniority_level", "salary_min", "salary_max",
        "equity_min", "equity_max", "total_comp_estimate",
        "is_ai_native", "remote_friendly_score", "visa_friendly",
        "relocation_support", "growth_signal",
    ]
    vals = [job.get(c) for c in cols]
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT OR REPLACE INTO jobs ({', '.join(cols)}) VALUES ({placeholders})"
    c.execute(sql, vals)
    conn.commit()
    job_id = c.lastrowid
    conn.close()
    return job_id


def insert_jobs_batch(jobs: List[Dict[str, Any]]) -> int:
    count = 0
    for job in jobs:
        insert_job(job)
        count += 1
    print(f"[DB] Inserted {count} jobs")
    return count


def get_all_jobs(filters: Dict = None) -> List[Dict]:
    conn = get_conn()
    c = conn.cursor()
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []

    if filters:
        if filters.get("is_remote"):
            ph = ",".join(["?"] * len(filters["is_remote"]))
            query += f" AND is_remote IN ({ph})"
            params.extend(filters["is_remote"])
        if filters.get("ml_domain"):
            ph = ",".join(["?"] * len(filters["ml_domain"]))
            query += f" AND ml_domain IN ({ph})"
            params.extend(filters["ml_domain"])
        if filters.get("seniority_level"):
            ph = ",".join(["?"] * len(filters["seniority_level"]))
            query += f" AND seniority_level IN ({ph})"
            params.extend(filters["seniority_level"])
        if filters.get("salary_min") is not None:
            query += " AND salary_max >= ?"
            params.append(filters["salary_min"])
        if filters.get("salary_max") is not None:
            query += " AND salary_min <= ?"
            params.append(filters["salary_max"])
        if filters.get("visa_friendly"):
            query += " AND visa_friendly = 1"
        if filters.get("relocation_support"):
            query += " AND relocation_support = 1"
        if filters.get("response_rate_min") is not None:
            query += " AND response_rate_score >= ?"
            params.append(filters["response_rate_min"])
        if filters.get("company_name"):
            ph = ",".join(["?"] * len(filters["company_name"]))
            query += f" AND company_name IN ({ph})"
            params.extend(filters["company_name"])
        if filters.get("search_text"):
            q = f"%{filters['search_text']}%"
            query += " AND (job_title LIKE ? OR about_job LIKE ? OR requirements LIKE ? OR company_name LIKE ?)"
            params.extend([q] * 4)

    query += " ORDER BY scraped_at DESC"
    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_job_count():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM jobs")
    count = c.fetchone()[0]
    conn.close()
    return count


def get_filter_options():
    conn = get_conn()
    c = conn.cursor()
    opts = {}
    opts["ml_domains"] = [r[0] for r in c.execute(
        "SELECT DISTINCT ml_domain FROM jobs WHERE ml_domain IS NOT NULL ORDER BY ml_domain"
    ).fetchall()]
    opts["seniority_levels"] = [r[0] for r in c.execute(
        "SELECT DISTINCT seniority_level FROM jobs WHERE seniority_level IS NOT NULL ORDER BY seniority_level"
    ).fetchall()]
    opts["remote_options"] = [r[0] for r in c.execute(
        "SELECT DISTINCT is_remote FROM jobs WHERE is_remote IS NOT NULL ORDER BY is_remote"
    ).fetchall()]
    opts["company_names"] = [r[0] for r in c.execute(
        "SELECT DISTINCT company_name FROM jobs ORDER BY company_name"
    ).fetchall()]
    sal = c.execute(
        "SELECT MIN(salary_min), MAX(salary_max) FROM jobs WHERE salary_min IS NOT NULL"
    ).fetchone()
    opts["salary_range"] = (sal[0] or 0, sal[1] or 500)
    conn.close()
    return opts


if __name__ == "__main__":
    init_db()
    print(f"[DB] Job count: {get_job_count()}")
