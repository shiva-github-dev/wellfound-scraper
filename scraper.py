import asyncio
import json
import re
import sys
import time
from typing import Dict, Any, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2022", "•")
        .replace("\n", " ")
        .strip()
    )


def parse_salary(raw: str) -> Tuple[Optional[int], Optional[int]]:
    if not raw:
        return None, None
    nums = re.findall(r"[\$€£](\d{1,3})[kK]", raw)
    if len(nums) >= 2:
        return int(nums[0]), int(nums[1])
    if len(nums) == 1:
        return int(nums[0]), int(nums[0])
    return None, None


def parse_equity(raw: str) -> Tuple[Optional[float], Optional[float]]:
    if not raw:
        return None, None
    m = re.search(r"(\d+\.?\d*)%\s*[-–]\s*(\d+\.?\d*)%", raw)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def classify_seniority(title: str, exp_raw: str) -> str:
    t = title.lower()
    if any(w in t for w in ["principal", "distinguished"]):
        return "Principal"
    if any(w in t for w in ["staff", "lead"]):
        return "Staff"
    if "senior" in t or "sr." in t:
        return "Senior"
    if "junior" in t or "jr." in t or "entry" in t or "graduate" in t:
        return "Junior"
    if exp_raw:
        nums = re.findall(r"(\d+)", exp_raw)
        if nums:
            years = int(nums[0])
            if years <= 2:
                return "Junior"
            if years <= 5:
                return "Mid"
            if years <= 8:
                return "Senior"
            return "Staff"
    return "Mid"


def classify_ml_domain(title: str, skills: str, about: str) -> str:
    text = f"{title} {skills} {about}".lower()
    domains = {
        "NLP": ["nlp", "natural language", "llm", "transformer", "bert", "gpt", "text", "language model", "chatbot"],
        "Computer Vision": ["computer vision", " cv ", "image", "detection", "segmentation", "yolo", "object detection"],
        "MLOps": ["mlops", "mlflow", "kubeflow", "pipeline", "deployment", "serving", "monitoring", "infrastructure"],
        "Generative AI": ["generative", "diffusion", "gan", "stable diffusion", "midjourney", "text-to-image"],
        "Robotics": ["robotics", "robot", "autonomous", "navigation", "perception", "lidar"],
        "AI Safety": ["safety", "alignment", "adversarial", "red team", "security", "robustness"],
        "Recommender Systems": ["recommendation", "recommender", "ranking", "personalization", "collaborative filtering"],
        "Time Series": ["time series", "forecasting", "anomaly detection", "temporal"],
        "Data Science": ["data science", "analytics", "insights", "dashboard", "reporting"],
        "Applied ML": ["applied", "production", "deploy", "scale", "pipeline"],
    }
    matched = []
    for domain, keywords in domains.items():
        if any(kw in text for kw in keywords):
            matched.append(domain)
    return ", ".join(matched) if matched else "General ML"


def classify_remote(remote_policy: str, location: str) -> str:
    combined = f"{remote_policy} {location}".lower()
    if "remote" in combined and "in office" not in combined:
        return "Yes"
    if "hybrid" in combined:
        return "Hybrid"
    if "in office" in combined or "in-office" in combined:
        return "No"
    return "Unknown"


def parse_response_score(tier: str) -> int:
    if not tier:
        return 0
    t = tier.lower()
    if "top 1%" in t:
        return 100
    if "top 5%" in t:
        return 90
    if "top 10%" in t:
        return 75
    return 50


def parse_company_stage(raw: str) -> str:
    if not raw:
        return ""
    r = raw.lower()
    if "early" in r:
        return "Early Stage"
    if "growth" in r:
        return "Growth Stage"
    if "scale" in r:
        return "Scale Stage"
    if "public" in r:
        return "Public"
    return raw


def is_ai_native(domain: str) -> int:
    if not domain:
        return 0
    ai_keywords = ["artificial intelligence", "machine learning", "ai ", "ml ", "deep learning", "nlp", "computer vision", "robotics"]
    d = domain.lower()
    if any(kw in d for kw in ai_keywords):
        return 1
    return 0


def remote_score(remote_policy: str, location: str) -> int:
    combined = f"{remote_policy} {location}".lower()
    if "remote only" in combined or "fully remote" in combined or "anywhere" in combined:
        return 100
    if "remote" in combined and "hybrid" not in combined:
        return 80
    if "hybrid" in combined or "flexible" in combined:
        return 60
    if "in office" in combined:
        return 20
    return 50


# ---------------------------------------------------------------------------
# Listing page parser
# ---------------------------------------------------------------------------

def parse_listing_page(markdown: str) -> List[Dict[str, Any]]:
    lines = markdown.split("\n")
    jobs = []
    current_company = None
    current_one_liner = ""
    current_size = ""

    i = 0
    while i < len(lines):
        line = clean(lines[i].strip())

        # Company header
        cm = re.match(r"##\s*\[([^\]]+)\]\(([^)]+)\)", line)
        if cm:
            current_company = cm.group(1)
            current_one_liner = ""
            current_size = ""
            j = i + 1
            while j < len(lines):
                nl = clean(lines[j].strip())
                if not nl:
                    j += 1
                    continue
                if nl.startswith("*") or nl.startswith("Actively Hiring"):
                    j += 1
                    continue
                if "Employees" in nl:
                    sm = re.search(r"(\d+-\d+\s*Employees?|\d+\+?\s*Employees?)", nl)
                    if sm:
                        current_size = sm.group(1)
                        current_one_liner = nl[: sm.start()].strip()
                    else:
                        current_one_liner = nl
                else:
                    current_one_liner = nl
                break
            i = j
            continue

        # Job line
        jm = re.match(
            r"\[([^\]]+)\]\((https://wellfound\.com/jobs/[^)]+|/jobs/[^)]+)\)"
            r"(Full-time|Part-time|Contract|Internship)?",
            line,
        )
        if jm and current_company:
            title = clean(jm.group(1))
            url = jm.group(2)
            if not url.startswith("http"):
                url = f"https://wellfound.com{url}"
            job_type = jm.group(3) or "Full-time"

            salary = location = remote = exp = posted = ""
            j = i + 1
            while j < len(lines) and j < i + 8:
                nl = clean(lines[j].strip())
                if not nl:
                    j += 1
                    continue
                if re.match(
                    r"\[([^\]]+)\]\((https://wellfound\.com/jobs/|/jobs/)", nl
                ) or re.match(r"##\s*\[", nl) or re.match(r"!\[", nl):
                    break
                if re.search(r"[\$€£]\d+k", nl) and not salary:
                    salary = nl
                elif any(kw in nl for kw in ["Remote", "In office", "Hybrid"]) and not remote:
                    remote = nl
                    location = nl
                elif not location and not remote and not salary and not exp and not posted:
                    if len(nl) < 50 and not re.search(r"\d+k", nl) and "year" not in nl.lower():
                        location = nl
                if "years of exp" in nl.lower() or "year of exp" in nl.lower():
                    exp = nl
                if re.match(r"^(today|yesterday|\d+\s+(day|week|month|year)s?\s+ago)$", nl, re.I):
                    posted = nl
                j += 1

            jobs.append({
                "company_name": current_company,
                "company_one_liner": current_one_liner,
                "company_size": current_size,
                "job_title": title,
                "job_url": url,
                "salary_raw": salary,
                "location_raw": location,
                "remote_policy_raw": remote,
                "is_remote": classify_remote(remote, location),
                "experience_raw": exp,
                "posted_date_raw": posted,
                "job_type": job_type,
            })
            i = j
            continue
        i += 1

    return jobs


# ---------------------------------------------------------------------------
# Detail page parser
# ---------------------------------------------------------------------------

def _is_junk_line(l: str) -> bool:
    """Return True if line is an image/link label junk line."""
    if not l:
        return True
    if l.startswith("!["):
        return True
    if l.startswith("[!["):
        return True
    if l.startswith("Learn more"):
        return True
    if l in ["Apply", "Apply Now", "Save", "Actively Hiring"]:
        return True
    if l.startswith("Copyright"):
        return True
    if l.startswith("Browse by"):
        return True
    return False


def _extract_next_value(lines: list, idx: int) -> str:
    """Look at lines[idx+1:] for the actual value after an icon line."""
    for j in range(idx + 1, min(idx + 4, len(lines))):
        nl = clean(lines[j].strip())
        if nl and not nl.startswith("![") and not nl.startswith("[!["):
            return nl
    return ""


def parse_detail_page(markdown: str) -> Dict[str, Any]:
    d: Dict[str, Any] = {}
    lines = markdown.split("\n")

    # --- Visa / Relocation / Remote detail / Reposted / Recruiter ---
    for i, line in enumerate(lines):
        l = clean(line.strip())
        if "Visa Sponsorship" in l:
            for j in range(i + 1, min(i + 3, len(lines))):
                nl = clean(lines[j].strip())
                if nl and nl not in ["Visa Sponsorship"]:
                    d["visa_sponsorship"] = nl
                    break
        if l.startswith("Relocation"):
            val = l.replace("Relocation", "").strip()
            d["relocation"] = val if val else "Unknown"
        if "Remote Work Policy" in l:
            for j in range(i + 1, min(i + 3, len(lines))):
                nl = clean(lines[j].strip())
                if nl and nl not in ["Remote Work Policy"]:
                    d["remote_work_policy_detail"] = nl
                    break
        if "Reposted:" in l:
            d["reposted_date_raw"] = l.replace("Reposted:", "").split("•")[0].strip()
        if "Recruiter recently active" in l:
            d["recruiter_active"] = 1

    # --- Skills from Skills section ---
    skills = []
    in_skills = False
    for line in lines:
        l = clean(line.strip())
        if l == "Skills":
            in_skills = True
            continue
        if in_skills:
            if l.startswith("##") or l.startswith("About"):
                break
            if l and not l.startswith("*") and not l.startswith("Apply") and not l.startswith("["):
                skills.append(l)
    d["skills_listed"] = json.dumps(skills) if skills else None

    # --- Response rate tags ---
    for line in lines:
        l = clean(line.strip())
        if "top 1%" in l.lower():
            d["response_rate_tier"] = "Top 1% of responders"
            d["response_rate_raw"] = l
        elif "top 5%" in l.lower():
            d["response_rate_tier"] = "Top 5% of responders"
            d["response_rate_raw"] = l
        elif "top 10%" in l.lower():
            d["response_rate_tier"] = "Top 10% of responders"
            d["response_rate_raw"] = l
        if "Responds within" in l:
            d["response_time"] = l

    # --- About the job (full text) ---
    # Some jobs have "## About the job", others jump straight to sub-headers
    about_job = []
    in_about_job = False
    for line in lines:
        l = clean(line.strip())
        if "About the job" in l and l.startswith("#"):
            in_about_job = True
            continue
        if in_about_job:
            if l.startswith("## About the company") or l.startswith("## Similar Jobs"):
                break
            if l and not _is_junk_line(l):
                about_job.append(l)
    d["about_job"] = "\n".join(about_job) if about_job else None

    # --- About company (clean, readable text) ---
    # Extract from "## About the company" through to next "##" header
    about_company_parts = []
    in_about_co = False
    for i, line in enumerate(lines):
        l = clean(line.strip())
        if l.startswith("## About the company"):
            in_about_co = True
            continue
        if in_about_co:
            # Skip company name header like "### [CompanyName](url)" BEFORE ## check
            # (### starts with ## so must be handled first)
            if l.startswith("### ["):
                continue
            # Stop at next ## section (e.g. "## Skills", "## Similar Jobs")
            if l.startswith("##"):
                break
            # Skip empty lines
            if not l:
                continue
            # Skip all image/link markdown (logos, icons, avatars)
            if l.startswith("![") or l.startswith("[!["):
                continue
            # Skip "Learn more" links
            if l.startswith("[Learn more") or l.startswith("[View the team"):
                continue
            # Skip standalone links to profiles/locations/industries
            if re.match(r"^\[.+\]\(https://wellfound\.com/(location|startups/industry|p)/", l):
                continue
            # The one-liner line has "X-Y Employees" appended (no space)
            # e.g. "AI productivity for the physical world1-10 Employees"
            emp_match = re.search(r"(\d+[-\u2013]\d+)\s*Employees?", l)
            if emp_match:
                desc = l[: emp_match.start()].strip()
                if desc:
                    about_company_parts.append(f"Description: {desc}")
                about_company_parts.append(f"Size: {emp_match.group(1)} Employees")
                continue
            # Response rate bullet lines
            if l.startswith("* "):
                about_company_parts.append(l)
                continue
            # Everything else: plain text (response details, descriptions)
            about_company_parts.append(l)
    d["about_company"] = "\n".join(about_company_parts) if about_company_parts else None

    # --- Requirements / Education / Benefits / Responsibilities ---
    requirements = []
    in_req = False
    for line in lines:
        l = clean(line.strip())
        if l in ["Requirements", "Who You Are", "Experience", "Core Technical Skills", "Qualifications"]:
            in_req = True
            continue
        if in_req:
            if l.startswith("##") or l.startswith("Apply Now") or l.startswith("Benefits") or l.startswith("Perks") or l.startswith("Compensation"):
                break
            if l.startswith("*"):
                requirements.append(l.lstrip("* ").strip())
    d["requirements"] = "\n".join(requirements) if requirements else None

    education = []
    in_edu = False
    for line in lines:
        l = clean(line.strip())
        if l == "Education":
            in_edu = True
            continue
        if in_edu:
            if l.startswith("##") or l.startswith("Experience") or l.startswith("Core"):
                break
            if l.startswith("*"):
                education.append(l.lstrip("* ").strip())
    d["education_requirements"] = "\n".join(education) if education else None

    benefits = []
    in_ben = False
    for line in lines:
        l = clean(line.strip())
        if l in ["Benefits", "The Perks", "Compensation & Benefits", "What We Offer", "What We Provide"]:
            in_ben = True
            continue
        if in_ben:
            if l.startswith("##") or l.startswith("Apply Now") or l.startswith("Typical Interview"):
                break
            if l.startswith("*"):
                benefits.append(l.lstrip("* ").strip())
    d["benefits"] = "\n".join(benefits) if benefits else None

    responsibilities = []
    in_resp = False
    for line in lines:
        l = clean(line.strip())
        if l in ["What You'll Do", "What We're Looking For", "What you'll do",
                 "Responsibilities", "The Role", "Your Impact"]:
            in_resp = True
            continue
        if in_resp:
            if l.startswith("##") or l.startswith("Who You Are") or l.startswith("Apply Now") or l.startswith("Requirements"):
                break
            if l.startswith("*"):
                responsibilities.append(l.lstrip("* ").strip())
    d["responsibilities"] = "\n".join(responsibilities) if responsibilities else None

    # --- Company domain / market / stage / type / funding ---
    # Structure in markdown:
    #   ![Company Type](icon)        <-- icon line
    #   Artificial Intelligence      <-- value on NEXT line
    #   ![Company Industries](icon)
    #   [Robotics](url)              <-- value wrapped in link
    company_domain = []
    company_market = []
    company_type = []
    company_stage = None
    biz_model = None

    for i, line in enumerate(lines):
        l = clean(line.strip())

        # Company Type: icon line followed by plain text value
        if l.startswith("![Company Type]"):
            val = _extract_next_value(lines, i)
            if val:
                company_type.append(val)
                # Check for B2B/B2C from these lines
                if val == "B2B" and not biz_model:
                    biz_model = "B2B"
                elif val == "B2C" and not biz_model:
                    biz_model = "B2C"

        # Company Industries: icon line followed by [link](url) or plain text
        if l.startswith("![Company Industries]"):
            val = _extract_next_value(lines, i)
            if val:
                # Extract from [text](url) format
                m = re.search(r"\[([^\]]+)\]", val)
                if m:
                    company_market.append(m.group(1))
                elif val and not val.startswith("["):
                    company_market.append(val)

        # Company domain: look for known domain names after Company Type icons
        if l.startswith("![Company Type]"):
            val = _extract_next_value(lines, i)
            if val and val not in ["B2B", "B2C", "B2B2C"]:
                if val not in company_domain:
                    company_domain.append(val)

        # Funding
        if "AMOUNT RAISED" in l:
            for j in range(i + 1, min(i + 3, len(lines))):
                nl = clean(lines[j].strip())
                if nl and "$" in nl:
                    d["company_funding"] = nl
                    break

        # Stage badges
        if "Early Stage" in l and not company_stage:
            company_stage = "Early Stage"
        elif "Growth Stage" in l and not company_stage:
            company_stage = "Growth Stage"
        elif "Scale Stage" in l and not company_stage:
            company_stage = "Scale Stage"
        elif "Public Stage" in l and not company_stage:
            company_stage = "Public"

        # B2B/B2C from bullet badges
        if re.match(r"\s*\*\s*B2B", l) and not biz_model:
            biz_model = "B2B"
        elif re.match(r"\s*\*\s*B2C", l) and not biz_model:
            biz_model = "B2C"

    d["company_domain"] = ", ".join(company_domain) if company_domain else None
    d["company_market"] = ", ".join(company_market) if company_market else None
    d["company_type"] = ", ".join(company_type) if company_type else None
    if company_stage:
        d["company_stage"] = company_stage
    if biz_model:
        d["company_business_model"] = biz_model

    return d


# ---------------------------------------------------------------------------
# Extract skills from free-text (about_job, requirements, etc.)
# ---------------------------------------------------------------------------

TECH_SKILLS = [
    "python", "pytorch", "tensorflow", "keras", "jax", "scikit-learn",
    "hugging face", "huggingface", "transformers", "langchain", "llamaindex",
    "opencv", "cuda", "c++", "java", "scala", "rust", "go", "javascript",
    "sql", "spark", "kafka", "airflow", "dbt", "docker", "kubernetes",
    "aws", "gcp", "azure", "mlflow", "kubeflow", "wandb", "neptune",
    "fastapi", "django", "flask", "react", "next.js",
    "bert", "gpt", "llm", "transformer", "diffusion", "gan", "vae",
    "cnn", "rnn", "lstm", "attention", "self-attention",
    "reinforcement learning", "rl", "dqn", "ppo",
    "computer vision", "nlp", "natural language processing",
    "deep learning", "machine learning", "data science",
    "neural network", "gradient descent", "backpropagation",
    "docker", "kubernetes", "terraform", "ci/cd",
    "postgresql", "mongodb", "redis", "elasticsearch",
    "pandas", "numpy", "scipy", "matplotlib",
    "git", "linux", "bash",
    "rest api", "graphql", "grpc",
    "stripe", "twilio", "sendgrid",
    "openai", "anthropic", "claude", "gemini", "gpt-4", "gpt-3",
    "rag", "retrieval augmented generation", "vector database",
    "pinecone", "weaviate", "chromadb", "milvus", "qdrant", "faiss",
    "llamaindex", "langchain", "semantic kernel",
    "mlops", "feature store", "model serving", "onnx", "tensorrt",
    "xgboost", "lightgbm", "catboost",
    "time series", "arima", "prophet",
    "yolo", "resnet", "vit", "clip", "whisper",
    "stable diffusion", "midjourney", "dall-e",
    "robotics", "ros", "slam", "lidar",
]


def extract_skills_from_text(text: str) -> List[str]:
    """Extract known tech skills from free-form text."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for skill in TECH_SKILLS:
        if skill in text_lower and skill not in found:
            found.append(skill)
    return found


# ---------------------------------------------------------------------------
# Enrich missing fields from about_job text
# ---------------------------------------------------------------------------

# Section header patterns for requirements
# Matches: ### Header, **Header**, ### **Header**
_REQ_HEADERS = re.compile(
    r"(?:#{2,3}\s+|\*\*)(Who You Are|What We[']re Looking For|What we[']re looking for|"
    r"What we're looking for\.\.\.|What You Bring|You May Be a Good Fit|We expect you to have|"
    r"Core Technical Skills|Requirements|Qualifications|About You|"
    r"Your Background|What We Need|What You Need|What we need|"
    r"Nice to Have|Bonus Points If You Have|Bonus if you)[\*\s]*$",
    re.IGNORECASE | re.MULTILINE,
)

# Section header patterns for responsibilities
_RESP_HEADERS = re.compile(
    r"(?:#{2,3}\s+|\*\*)(What You[']ll Do|What You[']ll Own|How You Will Make a Difference|"
    r"What you[']ll do|What you'll do\.\.\.|You will|Responsibilities|The Role|About the Role|"
    r"What You Will Do|Your Impact|What You[']ll Be Doing|"
    r"What makes this role special)[\*\s]*$",
    re.IGNORECASE | re.MULTILINE,
)

# Section header patterns for education
_EDU_HEADERS = re.compile(
    r"(?:#{2,3}\s+|\*\*)(Education|Educational Requirements|Academic Requirements)[\*\s]*$",
    re.IGNORECASE | re.MULTILINE,
)

# Section header patterns for benefits
_BEN_HEADERS = re.compile(
    r"(?:#{2,3}\s+|\*\*)(Benefits|Perks|What We Offer|Compensation & Benefits|"
    r"Benefits & Perks|Our Benefits|Job Benefits|The Perks|"
    r"What We Provide|Our Perks)[\*\s]*$",
    re.IGNORECASE | re.MULTILINE,
)

# Any ## / ### header or **bold** line (used to detect section boundaries)
_ANY_HEADER = re.compile(r"^(?:#{2,3}\s+|\*\*[^*]+\*\*)")


def _extract_section(text: str, start_pattern: re.Pattern) -> str:
    """Extract text between a matching header and the next ## header."""
    m = start_pattern.search(text)
    if not m:
        return ""
    start = m.end()
    # Find next ## header after start
    rest = text[start:]
    next_header = _ANY_HEADER.search(rest)
    if next_header:
        section = rest[: next_header.start()]
    else:
        section = rest
    # Clean: strip markdown bullets, extra whitespace
    lines = []
    for line in section.strip().split("\n"):
        l = line.strip()
        if not l:
            continue
        # Remove leading bullet markers
        l = re.sub(r"^[\*\-\•]\s+", "", l)
        if l:
            lines.append(l)
    return "\n".join(lines)


def _extract_experience(text: str) -> str:
    """Extract experience years from text like '5-7 years', '5+ years', 'at least 3 years'."""
    patterns = [
        r"(\d+[\s]*[-\u2013to]+\s*\d+)\s+years?\b",
        r"(\d+\+?)\s+years?\b",
        r"(?:at\s+least|minimum\s+of|over|>\s*)\s*(\d+)\s+years?\b",
        r"(\d+)\s+years?\s+(?:of\s+)?(?:relevant|related|industry|hands-on)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return ""


def _extract_education(text: str) -> str:
    """Extract education requirements from text."""
    patterns = [
        r"(?:BS|MS|PhD|Bachelor[']s|Master[']s|Doctorate|B\.S\.|M\.S\.|B\.A\.|M\.A\.)(?:'s)?\s+degree\s+in\s+[\w\s,/&]+",
        r"(?:BS|MS|PhD|Bachelor[']s|Master[']s|Doctorate)\s+in\s+(?:Computer Science|Engineering|Mathematics|Physics|Data Science|ML|AI|Statistics|related)[\w\s,/&]*",
        r"(?:degree|diploma)\s+in\s+(?:Computer Science|Engineering|Mathematics|Physics|Data Science|ML|AI|Statistics|related)[\w\s,/&]*",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return ""


def enrich_from_about_job(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich empty fields by parsing the about_job text."""
    about = rec.get("about_job", "")
    if not about:
        return rec

    # --- Experience ---
    if not rec.get("experience_raw"):
        exp = _extract_experience(about)
        if exp:
            rec["experience_raw"] = exp

    # --- Requirements ---
    if not rec.get("requirements"):
        req = _extract_section(about, _REQ_HEADERS)
        if req:
            rec["requirements"] = req

    # --- Responsibilities ---
    if not rec.get("responsibilities"):
        resp = _extract_section(about, _RESP_HEADERS)
        if resp:
            rec["responsibilities"] = resp

    # --- Education ---
    if not rec.get("education_requirements"):
        edu = _extract_education(about)
        if edu:
            rec["education_requirements"] = edu

    # --- Benefits ---
    if not rec.get("benefits"):
        ben = _extract_section(about, _BEN_HEADERS)
        if ben:
            rec["benefits"] = ben

    return rec


# ---------------------------------------------------------------------------
# Merge listing + detail → full job record
# ---------------------------------------------------------------------------

def build_full_record(listing: Dict, detail: Dict) -> Dict[str, Any]:
    rec = {**listing, **detail}

    # --- Combine skills from Skills section + about_job text ---
    skills_from_section = []
    if rec.get("skills_listed"):
        try:
            skills_from_section = json.loads(rec["skills_listed"])
        except Exception:
            pass

    text_for_skills = " ".join([
        rec.get("about_job", "") or "",
        rec.get("requirements", "") or "",
        rec.get("responsibilities", "") or "",
    ])
    skills_from_text = extract_skills_from_text(text_for_skills)

    # Merge: section skills first, then text-extracted (deduplicated)
    all_skills = list(skills_from_section)
    for s in skills_from_text:
        if s.lower() not in [x.lower() for x in all_skills]:
            all_skills.append(s)
    rec["skills_listed"] = json.dumps(all_skills) if all_skills else None

    # --- Parse salary ---
    smin, smax = parse_salary(rec.get("salary_raw", ""))
    rec["salary_min"] = smin
    rec["salary_max"] = smax

    # --- Parse equity ---
    emin, emax = parse_equity(rec.get("salary_raw", ""))
    rec["equity_min"] = emin
    rec["equity_max"] = emax

    # --- Total comp estimate ---
    rec["total_comp_estimate"] = smax if smax else None

    # --- Enrich empty fields from about_job text ---
    rec = enrich_from_about_job(rec)

    # --- Classification ---
    rec["seniority_level"] = classify_seniority(rec.get("job_title", ""), rec.get("experience_raw", ""))
    rec["ml_domain"] = classify_ml_domain(
        rec.get("job_title", ""),
        rec.get("skills_listed", ""),
        rec.get("about_job", ""),
    )
    rec["is_remote"] = classify_remote(rec.get("remote_policy_raw", ""), rec.get("location_raw", ""))
    rec["response_rate_score"] = parse_response_score(rec.get("response_rate_tier", ""))
    rec["company_stage"] = parse_company_stage(rec.get("company_stage", ""))
    rec["is_ai_native"] = is_ai_native(rec.get("company_domain", "") or rec.get("company_one_liner", ""))
    rec["remote_friendly_score"] = remote_score(rec.get("remote_policy_raw", ""), rec.get("location_raw", ""))
    rec["visa_friendly"] = 1 if "available" in (rec.get("visa_sponsorship", "") or "").lower() and "not" not in (rec.get("visa_sponsorship", "") or "").lower() else 0
    rec["relocation_support"] = 1 if "allowed" in (rec.get("relocation", "") or "").lower() and "not" not in (rec.get("relocation", "") or "").lower() else 0
    rec["growth_signal"] = 1 if "growing fast" in (rec.get("about_company", "") or "").lower() or "hiring growth" in (rec.get("about_company", "") or "").lower() else 0

    return rec


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

async def scrape_page(page_num: int, crawler, delay: float = 2.5, role: str = "machine-learning-engineer", role_filter: list = None) -> List[Dict]:
    url = f"https://wellfound.com/role/{role}?page={page_num}"
    print(f"\n[SCRAPE] Page {page_num} ...")

    result = await crawler.arun(
        url=url,
        config=CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_for="css:body",
            delay_before_return_html=3.0,
        ),
    )
    if not result.markdown:
        print(f"[SCRAPE] Page {page_num}: no markdown returned")
        return []

    listings = parse_listing_page(result.markdown)
    print(f"[SCRAPE] Page {page_num}: found {len(listings)} jobs")

    # Filter only relevant titles
    if role_filter:
        listings = [j for j in listings if any(kw in j["job_title"].lower() for kw in role_filter)]
    print(f"[SCRAPE] Page {page_num}: {len(listings)} after filter")

    records = []
    for idx, listing in enumerate(listings):
        job_url = listing["job_url"]
        print(f"  [{idx+1}/{len(listings)}] {listing['job_title']} @ {listing['company_name']} ...")

        try:
            detail_result = await crawler.arun(
                url=job_url,
                config=CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    wait_for="css:body",
                    delay_before_return_html=2.0,
                ),
            )
            detail = parse_detail_page(detail_result.markdown or "")
        except Exception as e:
            print(f"    [WARN] Detail page failed: {e}")
            detail = {}

        rec = build_full_record(listing, detail)
        records.append(rec)
        await asyncio.sleep(delay)

    return records


async def scrape_all(max_pages: int = 1, delay: float = 2.5, on_page_done=None, role: str = "machine-learning-engineer", role_filter: list = None) -> List[Dict]:
    browser_config = BrowserConfig(
        headless=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        extra_args=["--disable-blink-features=AutomationControlled"],
        enable_stealth=True,
    )

    all_records = []
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for page in range(1, max_pages + 1):
            records = await scrape_page(page, crawler, delay=delay, role=role, role_filter=role_filter)
            all_records.extend(records)
            if on_page_done:
                on_page_done(page, records, all_records)
            if page < max_pages:
                await asyncio.sleep(delay)

    print(f"\n[SCRAPE] Total: {len(all_records)} jobs scraped across {max_pages} page(s)")
    return all_records


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    from database import init_db, insert_jobs_batch

    parser = argparse.ArgumentParser(description="Wellfound Job Scraper")
    parser.add_argument("--pages", type=int, default=1, help="Number of pages to scrape (default: 1)")
    parser.add_argument("--delay", type=float, default=2.5, help="Delay between requests in seconds")
    parser.add_argument("--role", type=str, default="machine-learning-engineer", help="Wellfound role slug (default: machine-learning-engineer)")
    parser.add_argument("--db", type=str, default=None, help="SQLite database path (default: wellfound_jobs.db in script dir)")
    parser.add_argument("--csv", type=str, default=None, help="CSV output path")
    args = parser.parse_args()

    # Set DB path if specified
    if args.db:
        import database
        database.DB_PATH = args.db

    # Role-specific title filters (None = no filter, accept all)
    ROLE_FILTERS = {
        "machine-learning-engineer": [
            "machine learning", "ml engineer", "ml researcher", "ai engineer",
            "deep learning", "nlp", "computer vision", "data scientist",
            "applied scientist", "research scientist", "ai ml", "ml ops",
        ],
        "data-scientist": [
            "data scientist", "data science", "machine learning", "ml engineer",
            "ai engineer", "analytics", "applied scientist", "research scientist",
        ],
    }
    role_filter = ROLE_FILTERS.get(args.role)

    init_db()
    _total_inserted = [0]

    def _on_page_done(page, page_records, all_records):
        if page_records:
            insert_jobs_batch(page_records)
            _total_inserted[0] += len(page_records)
            print(f"  [DB] Inserted {len(page_records)} jobs from page {page} (total: {_total_inserted[0]})")

    all_records = asyncio.run(scrape_all(
        max_pages=args.pages, delay=args.delay,
        on_page_done=_on_page_done, role=args.role, role_filter=role_filter,
    ))
    print(f"\n[DONE] {_total_inserted[0]} jobs saved to database")
