import streamlit as st
import pandas as pd
import sqlite3
import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta
import altair as alt

st.set_page_config(page_title="Wellfound Jobs", layout="wide", page_icon=":material/work:")

# --- Database paths ---
ML_DB = r"D:\Wellfound_Scrape\wellfound_jobs.db"
DS_DB = r"D:\Wellfound_Scrape\wellfound_ds.db"

def load_jobs_from_db(db_path, role_label):
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    df = pd.read_sql("SELECT * FROM jobs", conn)
    conn.close()
    if len(df):
        df["role"] = role_label
    return df

@st.cache_data(ttl=60)
def load_all_data():
    ml = load_jobs_from_db(ML_DB, "ML Engineer")
    ds = load_jobs_from_db(DS_DB, "Data Scientist")
    combined = pd.concat([ml, ds], ignore_index=True)
    # Parse skills into lists for filtering
    combined["skills_parsed"] = combined["skills_listed"].apply(_parse_json_list)
    combined["domains_parsed"] = combined["ml_domain"].apply(_parse_json_list)
    return combined

def _parse_json_list(val):
    if not val or (isinstance(val, float) and pd.isna(val)):
        return []
    try:
        v = json.loads(val)
        if isinstance(v, list):
            return [x.lower().strip() for x in v if x]
    except:
        pass
    return [x.lower().strip() for x in str(val).split(",") if x.strip() and x.strip() != "null"]

def _parse_relative_date(text, reference_date=None):
    """Convert '3 days ago', '2 weeks ago', '1 month ago' etc to datetime.
    
    Uses reference_date (scraped_at) as the anchor instead of datetime.now(),
    so the result reflects when the job was actually posted.
    """
    if not text or (isinstance(text, float) and pd.isna(text)):
        return None
    text = str(text).lower().strip()
    m = re.match(r'(\d+)\s+(day|week|month|year)s?\s+ago', text)
    if not m:
        return None
    num = int(m.group(1))
    unit = m.group(2)
    ref = reference_date if reference_date else datetime.now()
    if isinstance(ref, str):
        try:
            ref = datetime.strptime(ref, "%Y-%m-%d %H:%M:%S")
        except:
            ref = datetime.now()
    if unit == "day":
        return ref - timedelta(days=num)
    elif unit == "week":
        return ref - timedelta(weeks=num)
    elif unit == "month":
        return ref - timedelta(days=num * 30)
    elif unit == "year":
        return ref - timedelta(days=num * 365)
    return None

def get_all_skills(df):
    skills = Counter()
    for lst in df["skills_parsed"]:
        for s in lst:
            if s and s not in ("hiring contact",) and "image" not in s:
                skills[s] += 1
    return skills

def get_all_domains(df):
    domains = Counter()
    for lst in df["domains_parsed"]:
        for d in lst:
            if d:
                domains[d] += 1
    return domains

# --- Load data ---
df_raw = load_all_data()

# ==================== TABS ====================
tab_jobs, tab_summary = st.tabs(["Job Explorer", "Summary Dashboard"])

# ==================== TAB 1: JOB EXPLORER ====================
with tab_jobs:
    st.title(":material/work: Wellfound Jobs Explorer")

    # --- Sidebar Filters ---
    st.sidebar.header(":material/filter_list: Filters")

    # Role
    role_options = sorted(df_raw["role"].dropna().unique().tolist())
    selected_roles = st.sidebar.multiselect("Job Role", role_options, default=role_options, key="role_filter")

    # Search
    search_text = st.sidebar.text_input(":material/search: Search", placeholder="Job title, company, skills...", key="search")

    # ML Domain
    all_domains = get_all_domains(df_raw)
    domain_labels = [f"{d} ({c})" for d, c in all_domains.most_common(30)]
    selected_domain_labels = st.sidebar.multiselect("ML Domain", domain_labels, default=[], key="domain_filter")
    selected_domains = [d.split(" (")[0] for d in selected_domain_labels]

    # Skills
    all_skills = get_all_skills(df_raw)
    skill_labels = [f"{s} ({c})" for s, c in all_skills.most_common(30)]
    selected_skill_labels = st.sidebar.multiselect("Skills", skill_labels, default=[], key="skill_filter")
    selected_skills = [s.split(" (")[0] for s in selected_skill_labels]

    # Seniority
    seniority_options = sorted(df_raw["seniority_level"].dropna().unique().tolist())
    selected_seniority = st.sidebar.multiselect("Seniority Level", seniority_options, default=[], key="seniority_filter")

    # Remote
    remote_options = sorted(df_raw["is_remote"].dropna().unique().tolist())
    selected_remote = st.sidebar.multiselect("Remote Policy", remote_options, default=[], key="remote_filter")

    # Salary max slider
    sal_data = df_raw[df_raw["salary_max"] > 0]["salary_max"]
    sal_max_val = int(sal_data.max()) if len(sal_data) else 500
    salary_max = st.sidebar.slider("Max Salary ($K)", 0, sal_max_val, sal_max_val, key="salary_filter")

    # Company
    company_options = sorted(df_raw["company_name"].dropna().unique().tolist())
    selected_companies = st.sidebar.multiselect("Company", company_options, default=[], key="company_filter")

    # Visa / Relocation
    visa_only = st.sidebar.checkbox("Visa Sponsorship Available", key="visa_filter")
    relocation_only = st.sidebar.checkbox("Relocation Supported", key="relocation_filter")

    # --- Apply Filters ---
    df = df_raw.copy()

    if selected_roles and len(selected_roles) < len(role_options):
        df = df[df["role"].isin(selected_roles)]

    if search_text:
        mask = (
            df["job_title"].str.contains(search_text, case=False, na=False) |
            df["company_name"].str.contains(search_text, case=False, na=False) |
            df["skills_listed"].str.contains(search_text, case=False, na=False) |
            df["about_job"].str.contains(search_text, case=False, na=False)
        )
        df = df[mask]

    if selected_domains:
        mask = df["domains_parsed"].apply(lambda lst: any(d in lst for d in selected_domains))
        df = df[mask]

    if selected_skills:
        mask = df["skills_parsed"].apply(lambda lst: any(s in lst for s in selected_skills))
        df = df[mask]

    if selected_seniority:
        df = df[df["seniority_level"].isin(selected_seniority)]

    if selected_remote:
        df = df[df["is_remote"].isin(selected_remote)]

    if salary_max < sal_max_val:
        df = df[(df["salary_max"] <= salary_max) | (df["salary_max"].isna()) | (df["salary_max"] == 0)]

    if selected_companies:
        df = df[df["company_name"].isin(selected_companies)]

    if visa_only:
        df = df[df["visa_friendly"] == 1]

    if relocation_only:
        df = df[df["relocation_support"] == 1]

    # --- Sort ---
    st.caption(f"Showing **{len(df)}** of {len(df_raw)} jobs")
    sort_by = st.selectbox("Sort by", ["Newest", "Highest Salary", "Lowest Salary"], index=0, key="sort_filter")
    if sort_by == "Highest Salary":
        df = df.sort_values("salary_max", ascending=False, na_position="last")
    elif sort_by == "Lowest Salary":
        df = df.sort_values("salary_min", ascending=True, na_position="last")
    else:
        df["_parsed_date"] = df.apply(
            lambda row: _parse_relative_date(row["posted_date_raw"], row.get("scraped_at")),
            axis=1
        )
        df = df.sort_values("_parsed_date", ascending=False, na_position="last")
        df = df.drop(columns=["_parsed_date"])

    # --- Pagination ---
    PAGE_SIZE = 20
    total_pages = max(1, (len(df) - 1) // PAGE_SIZE + 1)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key="page_num")
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_df = df.iloc[start:end]

    st.caption(f"Page {page} of {total_pages} | Showing {start+1}-{min(end, len(df))} of {len(df)} jobs")

    # --- Job Cards ---
    for idx, job in page_df.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1])

            with c1:
                st.markdown(f"**[{job['job_title']}]({job['job_url']})**")
                st.caption(f"{job['company_name']} • {job.get('company_one_liner', '') or ''}")

            with c2:
                sal = job.get("salary_raw", "N/A") or "N/A"
                loc = job.get("location_raw", "N/A") or "N/A"
                remote_badge = job.get("is_remote", "") or ""
                st.markdown(f"**{sal}**")
                st.caption(f":material/location_on: {loc} • :material/home: {remote_badge}")

            with c3:
                role_badge = ":material/science: ML Eng" if job.get("role") == "ML Engineer" else ":material/analytics: DS"
                st.caption(role_badge)
                resp = job.get("response_rate_score", 0) or 0
                if resp >= 90:
                    st.success(f":material/star: {job.get('response_rate_tier', '') or ''}")
                elif resp >= 75:
                    st.info(f":material/thumb_up: {job.get('response_rate_tier', '') or ''}")

            # Tags row
            tags = []
            if job.get("ml_domain"):
                tags.append(f":material/science: {job['ml_domain']}")
            if job.get("seniority_level"):
                tags.append(f":material/person: {job['seniority_level']}")
            if job.get("visa_friendly"):
                tags.append(":material/work: Visa OK")
            if job.get("relocation_support"):
                tags.append(":material/moving: Relocation OK")
            if job.get("posted_date_raw"):
                tags.append(f":material/schedule: {job['posted_date_raw']}")
            if tags:
                st.caption(" | ".join(tags))

            # Expandable detail
            with st.expander(":material/info: Full Details"):
                tab1, tab2, tab3 = st.tabs(["Job Details", "Company", "Classification"])

                with tab1:
                    if job.get("about_job"):
                        st.markdown("**About the Job**")
                        st.text_area("about_job", job["about_job"], height=200, disabled=True, key=f"aj_{idx}", label_visibility="collapsed")
                    if job.get("skills_listed"):
                        st.markdown("**Skills Listed**")
                        try:
                            skills = json.loads(job["skills_listed"])
                            st.write(", ".join(skills))
                        except:
                            st.write(job["skills_listed"])
                    if job.get("requirements"):
                        st.markdown("**Requirements**")
                        st.text_area("req", job["requirements"], height=150, disabled=True, key=f"req_{idx}", label_visibility="collapsed")
                    if job.get("benefits"):
                        st.markdown("**Benefits**")
                        st.text_area("ben", job["benefits"], height=100, disabled=True, key=f"ben_{idx}", label_visibility="collapsed")

                with tab2:
                    if job.get("about_company"):
                        st.markdown("**About the Company**")
                        st.text_area("about_co", job["about_company"], height=200, disabled=True, key=f"aco_{idx}", label_visibility="collapsed")
                    info_cols = st.columns(3)
                    info_cols[0].markdown(f"**Domain:** {job.get('company_domain', 'N/A')}")
                    info_cols[0].markdown(f"**Market:** {job.get('company_market', 'N/A')}")
                    info_cols[1].markdown(f"**Stage:** {job.get('company_stage', 'N/A')}")
                    info_cols[1].markdown(f"**Size:** {job.get('company_size', 'N/A')}")
                    info_cols[2].markdown(f"**Business Model:** {job.get('company_business_model', 'N/A')}")
                    info_cols[2].markdown(f"**Funding:** {job.get('company_funding', 'N/A')}")
                    st.markdown(f"**Remote Policy:** {job.get('remote_work_policy_detail', job.get('remote_policy_raw', 'N/A'))}")
                    st.markdown(f"**Visa:** {job.get('visa_sponsorship', 'N/A')} | **Relocation:** {job.get('relocation', 'N/A')}")

                with tab3:
                    c1, c2 = st.columns(2)
                    c1.markdown(f"**Role:** {job.get('role', 'N/A')}")
                    c1.markdown(f"**ML Domain:** {job.get('ml_domain', 'N/A')}")
                    c1.markdown(f"**Seniority:** {job.get('seniority_level', 'N/A')}")
                    c1.markdown(f"**Salary Range:** ${job.get('salary_min', 'N/A')}K - ${job.get('salary_max', 'N/A')}K")
                    c2.markdown(f"**Response Score:** {job.get('response_rate_score', 0)}/100")
                    c2.markdown(f"**Remote Score:** {job.get('remote_friendly_score', 'N/A')}/100")
                    c2.markdown(f"**AI Native:** {'Yes' if job.get('is_ai_native') else 'No'}")
                    c2.markdown(f"**Posted:** {job.get('posted_date_raw', 'N/A')}")

    # --- Download ---
    st.divider()
    if len(df):
        csv = df.drop(columns=["skills_parsed", "domains_parsed"]).to_csv(index=False)
        st.download_button(
            ":material/download: Download Filtered CSV",
            csv,
            "wellfound_jobs_filtered.csv",
            "text/csv",
        )


# ==================== TAB 2: SUMMARY DASHBOARD ====================
with tab_summary:
    st.title(":material/analytics: Summary Dashboard")

    role_tab1, role_tab2 = st.tabs(["ML Engineer", "Data Scientist"])

    for role_label, tab in [("ML Engineer", role_tab1), ("Data Scientist", role_tab2)]:
        with tab:
            rdf = df_raw[df_raw["role"] == role_label].copy()
            st.caption(f"**{len(rdf)}** {role_label} jobs")

            if len(rdf) == 0:
                st.info(f"No {role_label} jobs in database.")
                continue

            # --- Skills ---
            st.subheader("Top Skills")
            skills = get_all_skills(rdf)
            top_skills = skills.most_common(20)
            if top_skills:
                skill_df = pd.DataFrame(top_skills, columns=["Skill", "Count"])
                skill_df["Pct"] = (skill_df["Count"] / len(rdf) * 100).round(0).astype(int)
                chart = alt.Chart(skill_df).mark_bar().encode(
                    x=alt.X("Pct", title="% of Jobs"),
                    y=alt.Y("Skill", sort="-x", title=None),
                    tooltip=["Skill", "Pct", "Count"],
                ).properties(height=400)
                st.altair_chart(chart, use_container_width=True)

            # --- Domains ---
            st.subheader("Top Domains")
            domains = get_all_domains(rdf)
            top_domains = domains.most_common(15)
            if top_domains:
                dom_df = pd.DataFrame(top_domains, columns=["Domain", "Count"])
                dom_df["Pct"] = (dom_df["Count"] / len(rdf) * 100).round(0).astype(int)
                chart = alt.Chart(dom_df).mark_bar().encode(
                    x=alt.X("Pct", title="% of Jobs"),
                    y=alt.Y("Domain", sort="-x", title=None),
                    tooltip=["Domain", "Pct", "Count"],
                ).properties(height=350)
                st.altair_chart(chart, use_container_width=True)

            # --- Seniority ---
            st.subheader("Seniority Distribution")
            sen_counts = rdf["seniority_level"].dropna().value_counts()
            if len(sen_counts):
                sen_df = sen_counts.reset_index()
                sen_df.columns = ["Level", "Count"]
                sen_df["Pct"] = (sen_df["Count"] / len(rdf) * 100).round(0).astype(int)
                chart = alt.Chart(sen_df).mark_bar().encode(
                    x=alt.X("Pct", title="% of Jobs"),
                    y=alt.Y("Level", sort="-x", title=None),
                    tooltip=["Level", "Pct", "Count"],
                ).properties(height=250)
                st.altair_chart(chart, use_container_width=True)

            # --- Salary by Seniority ---
            st.subheader("Salary by Seniority")
            sal_rdf = rdf[rdf["salary_max"] > 0].copy()
            if len(sal_rdf):
                sal_by_level = sal_rdf.groupby("seniority_level").agg(
                    avg_min=("salary_min", "mean"),
                    avg_max=("salary_max", "mean"),
                    count=("salary_min", "count"),
                ).dropna(subset=["avg_min"])
                sal_by_level["avg_mid"] = ((sal_by_level["avg_min"] + sal_by_level["avg_max"]) / 2).round(0).astype(int)
                sal_by_level = sal_by_level.sort_values("avg_mid", ascending=False)
                st.dataframe(
                    sal_by_level[["count", "avg_min", "avg_max", "avg_mid"]].rename(
                        columns={"count": "Jobs", "avg_min": "Avg Min ($K)", "avg_max": "Avg Max ($K)", "avg_mid": "Avg Mid ($K)"}
                    ).style.format("{:.0f}", subset=["Avg Min ($K)", "Avg Max ($K)", "Avg Mid ($K)"]),
                    use_container_width=True,
                )
                sal_chart_df = sal_by_level.reset_index()
                chart = alt.Chart(sal_chart_df).mark_bar().encode(
                    x=alt.X("avg_mid", title="Avg Mid Salary ($K)"),
                    y=alt.Y("seniority_level", sort="-x", title=None),
                    tooltip=["seniority_level", "avg_mid", "count"],
                ).properties(height=200)
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No salary data available.")

            # --- Experience ---
            st.subheader("Experience Requirements")
            def parse_exp(raw):
                if not raw or (isinstance(raw, float) and pd.isna(raw)):
                    return None
                nums = re.findall(r'(\d+)', str(raw))
                nums = [int(n) for n in nums if 0 <= int(n) <= 40]
                return min(nums) if nums else None

            rdf["exp_val"] = rdf["experience_raw"].apply(parse_exp)
            exp_vals = rdf["exp_val"].dropna()
            if len(exp_vals):
                def bucketize(e):
                    if e <= 1: return "Entry (0-1)"
                    if e <= 3: return "Junior (2-3)"
                    if e <= 5: return "Mid (4-5)"
                    if e <= 8: return "Senior (6-8)"
                    if e <= 12: return "Staff (9-12)"
                    return "Principal (13+)"

                rdf["exp_bucket"] = rdf["exp_val"].apply(lambda x: bucketize(x) if pd.notna(x) else None)
                bucket_order = ["Entry (0-1)", "Junior (2-3)", "Mid (4-5)", "Senior (6-8)", "Staff (9-12)", "Principal (13+)"]
                exp_counts = rdf["exp_bucket"].dropna().value_counts()
                exp_counts = exp_counts.reindex([b for b in bucket_order if b in exp_counts.index])
                if len(exp_counts):
                    exp_df = exp_counts.reset_index()
                    exp_df.columns = ["Experience", "Count"]
                    exp_df["Pct"] = (exp_df["Count"] / len(rdf) * 100).round(0).astype(int)
                    chart = alt.Chart(exp_df).mark_bar().encode(
                        x=alt.X("Pct", title="% of Jobs"),
                        y=alt.Y("Experience", sort=bucket_order, title=None),
                        tooltip=["Experience", "Pct", "Count"],
                    ).properties(height=250)
                    st.altair_chart(chart, use_container_width=True)
                st.caption(f"Average: **{exp_vals.mean():.1f}** years | Median: **{exp_vals.median():.0f}** years")
            else:
                st.info("No experience data available.")

            # --- Remote ---
            st.subheader("Remote Policy")
            remote_counts = rdf["is_remote"].dropna().value_counts()
            if len(remote_counts):
                remote_df = remote_counts.reset_index()
                remote_df.columns = ["Policy", "Count"]
                chart = alt.Chart(remote_df).mark_bar().encode(
                    x=alt.X("Count", title="Jobs"),
                    y=alt.Y("Policy", sort="-x", title=None),
                    tooltip=["Policy", "Count"],
                ).properties(height=150)
                st.altair_chart(chart, use_container_width=True)
