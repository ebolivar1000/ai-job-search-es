#!/usr/bin/env python3
"""Daily Job Digest & Notification for Everth Bolivar (Dual Profile).

Executes 2 independent daily job searches tailored to Everth Bolivar's CVs:
1. "SENIOR DATA ENGINEER | CLOUD (AWS), ETL, DATA WAREHOUSING & BI" (CV_BA_SDE_ESP.pdf)
   -> Email / Issue: "SENIOR DATA ENGINEER VACANTES <fecha>"
2. "AI PRODUCT & AGENTIC ENGINEER | ARQUITECTURA DE SISTEMAS IA, APIS Y AUTOMATIZACIÓN" (CV_BB_AI_PAE_ESP.pdf)
   -> Email / Issue: "AGENTIC ENGINEER VACANTES <fecha>"

Enforces strict English language filters (discards advanced/fluent/bilingual English requirements)
and delivers alerts via Gmail SMTP or guaranteed GitHub Issue assignments.
"""

import argparse
import datetime
import json
import os
import re
import smtplib
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
SEEN_JOBS_FILE = REPO_ROOT / "job_scraper" / "seen_jobs.json"
LINKEDIN_CLI = REPO_ROOT / ".agents" / "skills" / "linkedin-search" / "cli" / "src" / "cli.ts"

# Geographic filters for Spanish-speaking / LATAM roles
ALLOWED_LOCATIONS = {
    "argentina", "buenos aires", "córdoba", "cordoba", "rosario", "mendoza", "santa fe",
    "spain", "españa", "madrid", "barcelona", "valencia", "sevilla",
    "mexico", "méxico", "cdmx", "guadalajara", "monterrey",
    "colombia", "bogota", "bogotá", "medellin", "medellín", "cali",
    "chile", "santiago",
    "uruguay", "montevideo",
    "peru", "perú", "lima",
    "latin america", "latam", "américa latina", "sudamérica", "south america",
    "ecuador", "quito", "guayaquil",
    "costa rica", "san jose", "san josé",
    "panama", "panamá",
    "venezuela", "caracas",
    "bolivia", "paraguay", "guatemala", "dominican republic", "república dominicana"
}

DISALLOWED_LOCATIONS = {
    "india", "bengaluru", "bangalore", "mumbai", "delhi", "hyderabad", "pune", "noida", "chennai", "gurugram",
    "china", "beijing", "shanghai", "shenzhen",
    "canada", "toronto", "vancouver", "ontario", "montreal", "quebec", "ottawa", "alberta", "calgary",
    "united states", "usa", "us", "california", "new york", "texas", "washington", "chicago",
    "united kingdom", "uk", "london", "england", "scotland", "manchester",
    "australia", "sydney", "melbourne", "brisbane",
    "germany", "deutschland", "berlin", "munich", "frankfurt",
    "poland", "polska", "warsaw", "krakow", "wroclaw", "gdansk",
    "france", "paris",
    "japan", "tokyo",
    "netherlands", "amsterdam",
    "ireland", "dublin",
    "singapore", "new zealand", "switzerland", "sweden", "austria", "belgium", "denmark", "norway", "finland"
}

# Patterns for jobs requiring advanced/fluent/conversational/bilingual English
ADVANCED_ENGLISH_PATTERNS = [
    r"\b(advanced|fluent|fluency|proficient|conversational|bilingual|upper[- ]intermediate|native|mandatory)\s+(in\s+|proficiency\s+in\s+)?english\b",
    r"\benglish\s*[:\-–—]?\s*(advanced|fluent|fluency|proficient|conversational|bilingual|c1|c2|upper[- ]intermediate|native|mandatory|required|a\s+must)\b",
    r"\benglish\s+(fluency|proficiency|speaker[s]?|is\s+a\s+must|is\s+required)\b",
    r"\b(professional\s+working\s+proficiency\s+in\s+english)\b",
    r"\b(strong\s+english\s+skills|good\s+command\s+of\s+english)\b",
    r"\b(ingl[eé]s)\s*[:\-–—]?\s*(avanzado|fluido|biling[uü]e|conversacional|c1|c2|excluyente|obligatorio|mandatorio|nativo|requerido)\b",
    r"\b(avanzado|fluido|biling[uü]e|conversacional|excluyente|obligatorio|mandatorio|nativo)\s+(en\s+)?ingl[eé]s\b",
    r"\b(nivel\s+de\s+ingl[eé]s|dominio\s+de\s+ingl[eé]s)\s*[:\-–—]?\s*(avanzado|fluido|biling[uü]e|conversacional|c1|c2|excluyente)\b",
    r"\b(c1|c2)\s+(english|ingl[eé]s)\b",
    r"\b(english\s+level)\s*[:\-–—]?\s*(advanced|fluent|c1|c2|upper[- ]intermediate)\b",
    r"\b(bilingual|biling[uü]e)\b",
]

# Negative patterns that disqualify or heavily penalize junior/unrelated roles
COMMON_NEGATIVE_PATTERNS = [
    r"\b(junior|jr|trainee|intern|practicante|pasante)\b",
    r"\b(php|wordpress|ruby|rails|\.net|c#|flutter|swift|ios|android)\b",
    r"\b(qa\s*tester|qa\s*manual|scrum\s*master|ux\s*designer|ui\s*designer)\b",
]

# Profile Definitions
PROFILES = {
    "sde": {
        "id": "sde",
        "name": "SENIOR DATA ENGINEER | CLOUD (AWS), ETL, DATA WAREHOUSING & BI",
        "subtitle": "Cloud (AWS), ETL, Data Warehousing, Snowflake, Databricks, Airflow, PySpark & BI",
        "email_subject": "SENIOR DATA ENGINEER VACANTES {date}",
        "issue_title": "SENIOR DATA ENGINEER VACANTES {date} ({count} nuevas vacantes)",
        "issue_label": "job-digest-sde",
        "html_file": "daily_digest_sde.html",
        "theme_color_primary": "#1e3a8a",
        "theme_color_secondary": "#2563eb",
        "theme_gradient": "linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #2563eb 100%)",
        "theme_icon": "🏢",
        "linkedin_queries": [
            # Argentina
            {"query": "Senior Data Engineer", "location": "Argentina", "remote": "remote"},
            {"query": "Data Engineer", "location": "Argentina", "remote": "remote"},
            {"query": "ETL Developer", "location": "Argentina", "remote": "remote"},
            {"query": "AWS Data Engineer", "location": "Argentina", "remote": "remote"},
            {"query": "Data Warehouse Engineer", "location": "Argentina", "remote": "remote"},
            # Latinoamérica Remoto
            {"query": "Senior Data Engineer", "location": "Latin America", "remote": "remote"},
            {"query": "Data Engineer", "location": "Latin America", "remote": "remote"},
            {"query": "Snowflake Data Engineer", "location": "Latin America", "remote": "remote"},
            {"query": "Databricks Engineer", "location": "Latin America", "remote": "remote"},
            {"query": "AWS Data Engineer", "location": "Latin America", "remote": "remote"},
            {"query": "Analytics Engineer", "location": "Latin America", "remote": "remote"},
            {"query": "ETL Developer", "location": "Latin America", "remote": "remote"},
            # España Remoto
            {"query": "Data Engineer", "location": "Spain", "remote": "remote"},
            {"query": "Ingeniero de Datos", "location": "Spain", "remote": "remote"},
            {"query": "Senior Data Engineer", "location": "Spain", "remote": "remote"},
            # Colombia & México
            {"query": "Data Engineer", "location": "Colombia", "remote": "remote"},
            {"query": "Senior Data Engineer", "location": "Colombia", "remote": "remote"},
            {"query": "Data Engineer", "location": "Mexico", "remote": "remote"},
            {"query": "Senior Data Engineer", "location": "Mexico", "remote": "remote"},
        ],
        "gob_categories": ["data-science-analytics", "programming"],
        "gob_keywords": [
            "data engineer", "ingeniero de datos", "analytics engineer", "etl",
            "snowflake", "databricks", "aws glue", "redshift", "airflow",
            "spark", "pyspark", "data warehouse", "powercenter", "teradata", "sql"
        ],
        "skills_patterns": [
            ("Snowflake", r"\bsnowflake\b"),
            ("Databricks", r"\bdatabricks\b"),
            ("AWS / Cloud", r"\b(aws|glue|redshift|s3|emr)\b"),
            ("Airflow", r"\bairflow\b"),
            ("Spark / PySpark", r"\b(spark|pyspark)\b"),
            ("Python", r"\bpython\b"),
            ("ETL / Pipelines", r"\b(etl|elt|pipeline[s]?)\b"),
            ("Data Warehouse", r"\b(data\s*warehouse|dwh|data\s*mart)\b"),
            ("Informatica / PowerCenter", r"\b(informatica|powercenter)\b"),
            ("SQL / Relacional", r"\b(sql|postgresql|postgres|oracle|teradata)\b"),
            ("Analytics Engineer", r"\banalytics\s*engineer\b"),
            ("Data Engineer", r"\b(data\s*engineer|ingeniero\s*de\s*datos)\b"),
            ("BI / Reporting", r"\b(power\s*bi|microstrategy|tableau|cognos)\b"),
            ("Big Data", r"\bbig\s*data\b"),
            ("Docker", r"\bdocker\b"),
        ],
        "role_regex": r"\b(data\s*engineer|ingeniero\s*de\s*datos|analytics\s*engineer|etl\s*developer|data\s*architect|arquitecto\s*de\s*datos)\b",
        "primary_skills": ["Snowflake", "Databricks", "AWS / Cloud", "Airflow", "Spark / PySpark"],
        "secondary_skills": ["Python", "ETL / Pipelines", "Data Warehouse", "Informatica / PowerCenter", "SQL / Relacional"],
    },
    "agentic": {
        "id": "agentic",
        "name": "AI PRODUCT & AGENTIC ENGINEER | ARQUITECTURA DE SISTEMAS IA, APIS Y AUTOMATIZACIÓN",
        "subtitle": "Flujos Agénticos Multi-LLM, APIs de LLMs, Python FastAPI, Chatbots, OCR & AWS Cloud",
        "email_subject": "AGENTIC ENGINEER VACANTES {date}",
        "issue_title": "AGENTIC ENGINEER VACANTES {date} ({count} nuevas vacantes)",
        "issue_label": "job-digest-agentic",
        "html_file": "daily_digest_agentic.html",
        "theme_color_primary": "#4f46e5",
        "theme_color_secondary": "#7c3aed",
        "theme_gradient": "linear-gradient(135deg, #09090b 0%, #311042 40%, #6d28d9 100%)",
        "theme_icon": "🤖",
        "linkedin_queries": [
            # Argentina
            {"query": "AI Engineer", "location": "Argentina", "remote": "remote"},
            {"query": "Agentic Engineer", "location": "Argentina", "remote": "remote"},
            {"query": "AI Product Engineer", "location": "Argentina", "remote": "remote"},
            {"query": "Generative AI", "location": "Argentina", "remote": "remote"},
            {"query": "Python FastAPI", "location": "Argentina", "remote": "remote"},
            {"query": "AI Backend Engineer", "location": "Argentina", "remote": "remote"},
            {"query": "Inteligencia Artificial", "location": "Argentina", "remote": "remote"},
            # Latinoamérica Remoto
            {"query": "AI Engineer", "location": "Latin America", "remote": "remote"},
            {"query": "Agentic Engineer", "location": "Latin America", "remote": "remote"},
            {"query": "Generative AI Engineer", "location": "Latin America", "remote": "remote"},
            {"query": "LLM Engineer", "location": "Latin America", "remote": "remote"},
            {"query": "AI Solutions Architect", "location": "Latin America", "remote": "remote"},
            {"query": "Python FastAPI", "location": "Latin America", "remote": "remote"},
            {"query": "AI Developer", "location": "Latin America", "remote": "remote"},
            # España Remoto
            {"query": "AI Engineer", "location": "Spain", "remote": "remote"},
            {"query": "Ingeniero Inteligencia Artificial", "location": "Spain", "remote": "remote"},
            {"query": "Generative AI", "location": "Spain", "remote": "remote"},
            {"query": "Python FastAPI", "location": "Spain", "remote": "remote"},
            # Colombia & México
            {"query": "AI Engineer", "location": "Colombia", "remote": "remote"},
            {"query": "Generative AI", "location": "Colombia", "remote": "remote"},
            {"query": "AI Engineer", "location": "Mexico", "remote": "remote"},
            {"query": "Generative AI", "location": "Mexico", "remote": "remote"},
        ],
        "gob_categories": ["machine-learning-ai", "programming", "data-science-analytics"],
        "gob_keywords": [
            "ai", "ia", "artificial intelligence", "inteligencia artificial",
            "agent", "agente", "agentic", "llm", "genai", "generative ai",
            "fastapi", "python", "chatbot", "rag", "langchain", "llamaindex",
            "openai", "claude", "ocr", "computer vision", "machine learning"
        ],
        "skills_patterns": [
            ("Flujos Agénticos / Multi-Agent", r"\b(agentic|agent[s]?\s*de\s*ia|ai\s*agent[s]?|multi[- ]agent|langchain|llamaindex|crewai|autogen)\b"),
            ("Generative AI & LLMs", r"\b(llm[s]?|generative\s*ai|genai|ia\s*generativa|prompt\s*engineering|rag|vector\s*db|fine[- ]tuning)\b"),
            ("LLM Providers (Claude/OpenAI)", r"\b(openai|anthropic|claude|gemini|llama|mistral|ollama|deepseek|hugging\s*face)\b"),
            ("Chatbots & WhatsApp", r"\b(chatbot[s]?|whatsapp\s*api|conversational\s*ai|telegram\s*bot)\b"),
            ("Visión Computacional & OCR", r"\b(ocr|computer\s*vision|visi[oó]n\s*artificial|image\s*recognition)\b"),
            ("FastAPI & Python", r"\b(fastapi|python\s*backend|python)\b"),
            ("APIs RESTful & Backend", r"\b(rest\s*api|apis\s*restful|express|node\.?js|jwt|rbac)\b"),
            ("Frontend (React/TypeScript)", r"\b(react|typescript|javascript|pwa)\b"),
            ("Cloud AWS & DevOps", r"\b(aws|docker|ci[/-]cd|github\s*actions|linux)\b"),
            ("Bases de Datos & SQL", r"\b(postgresql|postgres|mysql|sql|redis|mongodb|qdrant|chroma|pinecone)\b"),
            ("Automatización de Procesos", r"\b(automatizaci[oó]n|process\s*automation|workflow)\b"),
            ("AI Architecture", r"\b(ai\s*architect|arquitecto\s*de\s*ia|solution[s]?\s*architect)\b"),
        ],
        "role_regex": r"\b(agentic\s*engineer|ai\s*product\s*engineer|ai\s*engineer|ingeniero\s*de\s*ia|ingeniero\s*de\s*inteligencia\s*artificial|generative\s*ai\s*engineer|llm\s*engineer|ai\s*backend\s*engineer|ai\s*developer|desarrollador\s*ia|ai\s*solutions\s*architect)\b",
        "primary_skills": [
            "Flujos Agénticos / Multi-Agent",
            "Generative AI & LLMs",
            "LLM Providers (Claude/OpenAI)",
            "Chatbots & WhatsApp",
            "FastAPI & Python",
            "AI Architecture",
        ],
        "secondary_skills": [
            "Visión Computacional & OCR",
            "APIs RESTful & Backend",
            "Cloud AWS & DevOps",
            "Bases de Datos & SQL",
            "Automatización de Procesos",
        ],
    },
}


def has_advanced_english_requirement(text: str) -> tuple[bool, str]:
    """Check if text contains explicit advanced/fluent English requirements."""
    if not text:
        return False, ""
    text_lower = text.lower()
    for pat in ADVANCED_ENGLISH_PATTERNS:
        m = re.search(pat, text_lower)
        if m:
            return True, m.group(0)
    return False, ""


def score_and_enrich_job(job: dict, profile_key: str) -> tuple[int, str, list[str]]:
    """Score a job against the selected candidate profile (sde or agentic)."""
    p_cfg = PROFILES[profile_key]
    title = (job.get("title") or "").strip()
    company = (job.get("company") or "").strip()
    location = (job.get("location") or "").strip()
    description = (job.get("description") or "").strip()
    text = f"{title} {company} {location} {description}".lower()

    # Disqualification if advanced English required
    has_eng, _ = has_advanced_english_requirement(text)
    if has_eng:
        return 10, "BAJO", []

    # Disqualification / heavy penalty for junior or completely unrelated stacks
    for neg in COMMON_NEGATIVE_PATTERNS:
        if re.search(neg, text):
            return 10, "BAJO", []

    score = 40  # Base score for remote tech role in Hispanic / LATAM region

    # Seniority bonus
    if re.search(r"\b(senior|sr|lead|principal|architect|arquitecto|staff|head|founder)\b", text):
        score += 25
    elif re.search(r"\b(semi[- ]?senior|ssr|mid|middle)\b", text):
        score += 10

    # Direct Role Match
    if re.search(p_cfg["role_regex"], text):
        score += 25

    matched_skills = []
    primary_skills = set(p_cfg.get("primary_skills", []))
    secondary_skills = set(p_cfg.get("secondary_skills", []))

    for skill_name, pattern in p_cfg["skills_patterns"]:
        if re.search(pattern, text):
            matched_skills.append(skill_name)
            if skill_name in primary_skills:
                score += 15
            elif skill_name in secondary_skills:
                score += 10
            else:
                score += 5

    # Cap between 10 and 100
    final_score = max(10, min(100, score))

    if final_score >= 80:
        fit_level = "EXCELENTE"
    elif final_score >= 65:
        fit_level = "ALTO"
    elif final_score >= 45:
        fit_level = "BUENO"
    else:
        fit_level = "GENERAL"

    return final_score, fit_level, matched_skills


def is_hispanic_or_latam_job(job: dict) -> bool:
    """Ensure the job belongs to a Spanish-speaking country or Latin America."""
    portal = job.get("portal", "")
    if portal == "Get on Board":
        return True

    loc = (job.get("location") or "").lower()
    has_disallowed = any(d in loc for d in DISALLOWED_LOCATIONS)
    has_allowed = any(a in loc for a in ALLOWED_LOCATIONS)

    if has_disallowed and not has_allowed:
        return False
    if has_allowed:
        return True
    return False


def find_bun() -> str:
    """Locate Bun executable on the system."""
    import shutil
    bun_path = shutil.which("bun")
    if bun_path:
        return bun_path
    home = Path.home()
    windows_bun = home / ".bun" / "bin" / "bun.exe"
    if windows_bun.exists():
        return str(windows_bun)
    return "bun"


def load_seen_jobs() -> dict:
    """Load existing seen jobs dictionary, initializing dual-profile namespaces."""
    if not SEEN_JOBS_FILE.exists():
        return {"seen": {}, "seen_sde": {}, "seen_agentic": {}}
    try:
        data = json.loads(SEEN_JOBS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"seen": {}, "seen_sde": {}, "seen_agentic": {}}

        # Migrate or ensure profile keys exist
        if "seen_sde" not in data:
            data["seen_sde"] = dict(data.get("seen", {}))
        if "seen_agentic" not in data:
            data["seen_agentic"] = {}
        if "seen" not in data:
            data["seen"] = {}

        return data
    except Exception as e:
        print(f"[WARN] Error loading seen_jobs.json: {e}, starting fresh.", file=sys.stderr)
        return {"seen": {}, "seen_sde": {}, "seen_agentic": {}}


def save_seen_jobs(data: dict):
    """Save seen jobs dictionary atomically."""
    SEEN_JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = SEEN_JOBS_FILE.with_suffix(".tmp")
    temp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_file.replace(SEEN_JOBS_FILE)


def run_linkedin_search(bun_bin: str, query: str, location: str, remote: str = "remote", limit: int = 15) -> list:
    """Run a single search query via the linkedin-search CLI."""
    cmd = [
        bun_bin,
        "run",
        str(LINKEDIN_CLI),
        "search",
        "-q",
        query,
        "-l",
        location,
        "--remote",
        remote,
        "--jobage",
        "7",
        "--limit",
        str(limit),
        "--format",
        "json",
    ]
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            cwd=REPO_ROOT,
        )
        data = json.loads(res.stdout)
        results = data.get("results", [])
        formatted = []
        if isinstance(results, list):
            for r in results:
                r["portal"] = "LinkedIn"
                formatted.append(r)
        return formatted
    except subprocess.CalledProcessError as e:
        print(f"[WARN] LinkedIn search failed for '{query}' in '{location}': {e.stderr}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[WARN] Unexpected error in LinkedIn search '{query}': {e}", file=sys.stderr)
        return []


def fetch_linkedin_description(bun_bin: str, job_id: str) -> str:
    """Fetch description for a LinkedIn job ID to inspect language and tech requirements."""
    if not job_id or not str(job_id).isdigit():
        return ""
    cmd = [bun_bin, "run", str(LINKEDIN_CLI), "detail", str(job_id), "--format", "json"]
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            cwd=REPO_ROOT,
        )
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            return data.get("description") or ""
    except Exception:
        pass
    return ""


def run_getonboard_search(categories: list, keywords: list) -> list:
    """Fetch remote positions from Get on Board API for given categories & keywords."""
    print(f"[INFO] Buscando vacantes en Get on Board ({', '.join(categories)})...")
    results = []
    headers = {"User-Agent": "AIJobSearch/2.0 (+https://github.com/ebolivar1000/ai-job-search-es)"}

    for cat in categories:
        url = f"https://www.getonbrd.com/api/v0/categories/{cat}/jobs?per_page=50&expand[]=company"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
                for item in payload.get("data", []):
                    attrs = item.get("attributes", {})
                    # Solo vacantes remotas
                    if not attrs.get("remote"):
                        continue

                    title = attrs.get("title", "")
                    title_lower = title.lower()

                    if any(kw in title_lower for kw in keywords):
                        comp = attrs.get("company", {}).get("data", {}).get("attributes", {}).get("name") or "Empresa Confidencial"
                        link = item.get("links", {}).get("public_url") or f"https://www.getonbrd.com/jobs/{item.get('id')}"
                        zone = attrs.get("remote_zone") or "LATAM / 100% Remoto"
                        pub_ts = attrs.get("published_at")
                        date_str = datetime.date.today().strftime("%Y-%m-%d")
                        if pub_ts:
                            try:
                                date_str = datetime.date.fromtimestamp(pub_ts).strftime("%Y-%m-%d")
                            except Exception:
                                pass

                        desc_parts = [
                            attrs.get("description", ""),
                            attrs.get("functions", ""),
                            attrs.get("desirable", ""),
                            attrs.get("description_headline", ""),
                        ]
                        full_desc = " ".join(p for p in desc_parts if p)

                        job_dict = {
                            "id": f"gob_{item.get('id')}",
                            "title": title,
                            "company": comp,
                            "location": f"100% Remoto ({zone})",
                            "url": link,
                            "date": date_str,
                            "description": full_desc,
                            "portal": "Get on Board",
                        }
                        results.append(job_dict)
        except Exception as e:
            print(f"[WARN] Error fetching Get on Board category '{cat}': {e}", file=sys.stderr)

    print(f"[INFO] Get on Board: {len(results)} posiciones remotas obtenidas.")
    return results


def generate_html_email(new_jobs: list, today_str: str, profile_key: str) -> str:
    """Build a modern HTML email tailored to the selected profile."""
    p_cfg = PROFILES[profile_key]
    job_cards_html = ""
    excellent_count = sum(1 for j in new_jobs if j.get("fit_score", 0) >= 80)
    high_count = sum(1 for j in new_jobs if 65 <= j.get("fit_score", 0) < 80)

    for j in new_jobs:
        title = j.get("title", "Posición sin título")
        company = j.get("company", "Empresa no especificada")
        loc = j.get("location", "Remoto")
        url = j.get("url", "#")
        date_posted = j.get("date", "Reciente")
        portal = j.get("portal", "LinkedIn")
        score = j.get("fit_score", 50)
        fit_level = j.get("fit_level", "BUENO")
        skills = j.get("matched_skills", [])

        portal_bg = "#0077b5" if portal == "LinkedIn" else "#00b493"

        if fit_level == "EXCELENTE":
            fit_badge = f'<span style="background-color: #fef08a; color: #854d0e; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 9999px; border: 1px solid #fde047; margin-right: 6px;">🌟 Match {score}% · Excelente</span>'
            border_left = "4px solid #eab308"
        elif fit_level == "ALTO":
            fit_badge = f'<span style="background-color: #dbeafe; color: #1e40af; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 9999px; border: 1px solid #bfdbfe; margin-right: 6px;">⭐ Match {score}% · Alto</span>'
            border_left = "4px solid #3b82f6"
        else:
            fit_badge = f'<span style="background-color: #f1f5f9; color: #334155; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 9999px; margin-right: 6px;">🎯 Match {score}%</span>'
            border_left = "4px solid #cbd5e1"

        skills_pills_html = ""
        if skills:
            pills = "".join(
                f'<span style="display: inline-block; background-color: #f8fafc; color: #475569; font-size: 11px; font-weight: 500; padding: 2px 8px; border-radius: 4px; border: 1px solid #e2e8f0; margin-right: 4px; margin-bottom: 4px;">{s}</span>'
                for s in skills[:6]
            )
            skills_pills_html = f'<div style="margin-top: 8px; margin-bottom: 10px;">{pills}</div>'

        btn_bg = p_cfg.get("theme_color_secondary", "#2563eb")

        job_cards_html += f"""
        <div style="background-color: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; border-left: {border_left}; padding: 18px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; flex-wrap: wrap; gap: 6px;">
                <h3 style="margin: 0; color: #1e293b; font-size: 17px; font-weight: 600; flex: 1; min-width: 250px;">{title}</h3>
                <div>
                    {fit_badge}
                    <span style="background-color: {portal_bg}; color: #ffffff; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 9999px; margin-right: 4px;">{portal}</span>
                    <span style="background-color: #e0f2fe; color: #0369a1; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 9999px;">100% Remoto</span>
                </div>
            </div>
            <p style="margin: 0 0 4px 0; color: #475569; font-size: 14px;">
                🏢 <strong>{company}</strong> &nbsp;|&nbsp; 📍 {loc} &nbsp;|&nbsp; 📅 {date_posted}
            </p>
            {skills_pills_html}
            <div style="margin-top: 10px;">
                <a href="{url}" target="_blank" style="display: inline-block; background-color: {btn_bg}; color: #ffffff; text-decoration: none; padding: 8px 14px; border-radius: 6px; font-size: 13px; font-weight: 500;">
                    Ver Vacante en {portal} &rarr;
                </a>
            </div>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{p_cfg['name']} - Everth Bolivar</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #334155;">
        <div style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
            <div style="background: {p_cfg['theme_gradient']}; padding: 28px 24px; color: #ffffff;">
                <h1 style="margin: 0 0 6px 0; font-size: 21px; font-weight: 700;">{p_cfg['theme_icon']} {p_cfg['name']}</h1>
                <p style="margin: 0; font-size: 14px; opacity: 0.95;">
                    Búsqueda activa para <strong>Everth Bolivar</strong> &bull; {today_str}
                </p>
                <p style="margin: 4px 0 0 0; font-size: 12px; opacity: 0.85;">
                    {p_cfg['subtitle']}
                </p>
                <div style="margin-top: 14px;">
                    <span style="display: inline-block; background-color: rgba(255,255,255,0.2); padding: 4px 10px; border-radius: 6px; font-size: 12px; margin-right: 6px;">📊 Total nuevas: <strong>{len(new_jobs)}</strong></span>
                    <span style="display: inline-block; background-color: rgba(254,240,138,0.3); color: #fef08a; padding: 4px 10px; border-radius: 6px; font-size: 12px; margin-right: 6px;">🌟 Calce Excelente: <strong>{excellent_count}</strong></span>
                    <span style="display: inline-block; background-color: rgba(219,234,254,0.3); color: #dbeafe; padding: 4px 10px; border-radius: 6px; font-size: 12px;">⭐ Calce Alto: <strong>{high_count}</strong></span>
                </div>
            </div>
            <div style="padding: 24px; background-color: #f1f5f9;">
                <p style="margin: 0 0 18px 0; font-size: 15px; color: #334155;">
                    Se encontraron <strong>{len(new_jobs)} nuevas vacantes</strong> filtradas (sin inglés excluyente) y ordenadas por compatibilidad:
                </p>
                {job_cards_html}
            </div>
            <div style="padding: 16px 24px; background-color: #ffffff; text-align: center; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8;">
                Generado automáticamente por AI Job Search &bull; Santa Fe, Argentina
            </div>
        </div>
    </body>
    </html>
    """
    return html


def write_github_step_summary(new_jobs: list, today_str: str, profile_key: str):
    """Write an interactive Markdown summary table to $GITHUB_STEP_SUMMARY if available."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    p_cfg = PROFILES[profile_key]
    try:
        lines = [
            f"# {p_cfg['theme_icon']} {p_cfg['name']} - {today_str}",
            "",
            f"Se encontraron **{len(new_jobs)} nuevas vacantes remotas** acordes al perfil de **Everth Bolivar** ({p_cfg['subtitle']}).",
            "",
            "| Calce | Posición | Empresa | Portal | Ubicación | Tags Tecnológicos |",
            "|:---:|:---|:---|:---:|:---|:---|",
        ]
        for j in new_jobs:
            score = j.get("fit_score", 50)
            fit_level = j.get("fit_level", "BUENO")
            title = j.get("title", "Posición")
            url = j.get("url", "#")
            company = j.get("company", "Empresa")
            portal = j.get("portal", "LinkedIn")
            loc = j.get("location", "Remoto")
            skills = ", ".join(f"`{s}`" for s in j.get("matched_skills", [])) or "-"

            if fit_level == "EXCELENTE":
                badge = f"🌟 **{score}%**"
            elif fit_level == "ALTO":
                badge = f"⭐ **{score}%**"
            else:
                badge = f"🎯 {score}%"

            lines.append(f"| {badge} | [{title}]({url}) | {company} | **{portal}** | {loc} | {skills} |")

        lines.append("")
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"[INFO] Resumen de {len(new_jobs)} vacantes ({profile_key}) agregado a GITHUB_STEP_SUMMARY.")
    except Exception as e:
        print(f"[WARN] Error al escribir en GITHUB_STEP_SUMMARY: {e}", file=sys.stderr)


def send_email(subject: str, html_content: str, recipient: str) -> bool:
    """Send HTML email via Gmail SMTP using App Password with IPv4, SSL/TLS, and retries."""
    smtp_user = os.environ.get("GMAIL_USER", "ebolivar1000@gmail.com").strip()
    raw_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    smtp_password = raw_password.replace(" ", "").strip()

    if not smtp_password:
        print("[WARN] GMAIL_APP_PASSWORD no está configurado en las variables de entorno ni en GitHub Secrets.", file=sys.stderr)
        print(f"[INFO] Resumen preparado: '{subject}' para {recipient} (envío omitido por falta de contraseña).")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"AI Job Search <{smtp_user}>"
    msg["To"] = recipient

    part = MIMEText(html_content, "html", "utf-8")
    msg.attach(part)

    # Force IPv4 resolution
    original_getaddrinfo = socket.getaddrinfo

    def ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    ssl_context = ssl.create_default_context()
    configs = [
        {"port": 465, "ssl": True, "name": "Puerto 465 (SSL)"},
        {"port": 587, "ssl": False, "name": "Puerto 587 (STARTTLS)"},
    ]
    max_attempts_per_config = 3

    try:
        socket.getaddrinfo = ipv4_getaddrinfo
        for cfg in configs:
            for attempt in range(1, max_attempts_per_config + 1):
                try:
                    print(f"[INFO] Intentando enviar correo '{subject}' vía {cfg['name']} (intento {attempt}/{max_attempts_per_config})...")
                    if cfg["ssl"]:
                        with smtplib.SMTP_SSL("smtp.gmail.com", cfg["port"], context=ssl_context, timeout=30) as server:
                            server.ehlo()
                            server.login(smtp_user, smtp_password)
                            server.sendmail(smtp_user, recipient, msg.as_string())
                    else:
                        with smtplib.SMTP("smtp.gmail.com", cfg["port"], timeout=30) as server:
                            server.ehlo()
                            server.starttls(context=ssl_context)
                            server.ehlo()
                            server.login(smtp_user, smtp_password)
                            server.sendmail(smtp_user, recipient, msg.as_string())

                    print(f"[OK] Correo enviado exitosamente a {recipient}: '{subject}'")
                    return True
                except smtplib.SMTPAuthenticationError as auth_err:
                    print(f"[ERROR] Error de autenticación SMTP de Gmail (535): {auth_err}", file=sys.stderr)
                    return False
                except Exception as e:
                    print(f"[WARN] Falló intento {attempt} con {cfg['name']}: {type(e).__name__} - {e}", file=sys.stderr)
                    if attempt < max_attempts_per_config:
                        time.sleep(2 * attempt)
    finally:
        socket.getaddrinfo = original_getaddrinfo

    print(f"[ERROR] No se pudo enviar el correo a {recipient} tras agotar todos los protocolos y reintentos.", file=sys.stderr)
    return False


def create_github_issue_digest(new_jobs: list, today_str: str, recipient: str, profile_key: str) -> bool:
    """Fallback notification: create a GitHub Issue assigned to repo owner.

    GitHub automatically dispatches an email notification with the full issue body
    directly to the owner's email (ebolivar1000@gmail.com).
    """
    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "ebolivar1000/ai-job-search-es")
    p_cfg = PROFILES[profile_key]

    if not gh_token:
        print("[WARN] No hay GH_TOKEN disponible para enviar notificación mediante GitHub Issue.", file=sys.stderr)
        return False

    title = p_cfg["issue_title"].format(date=today_str, count=len(new_jobs))
    print(f"[INFO] Enviando notificación de vacantes mediante GitHub Issue a {repo}: '{title}'...")

    lines = [
        f"## {p_cfg['theme_icon']} {p_cfg['name']} - {today_str}",
        "",
        f"Se encontraron **{len(new_jobs)} nuevas vacantes** filtradas (sin inglés excluyente) y ordenadas por compatibilidad con el perfil de **Everth Bolivar** ({p_cfg['subtitle']}).",
        "",
        "| Calce | Posición | Empresa | Portal | Ubicación | Tecnologías |",
        "|:---:|:---|:---|:---:|:---|:---|",
    ]
    for j in new_jobs[:60]:
        score = j.get("fit_score", 50)
        fit_level = j.get("fit_level", "BUENO")
        j_title = j.get("title", "Posición")
        url = j.get("url", "#")
        company = j.get("company", "Empresa")
        portal = j.get("portal", "LinkedIn")
        loc = j.get("location", "Remoto")
        skills = ", ".join(f"`{s}`" for s in j.get("matched_skills", [])) or "-"

        if fit_level == "EXCELENTE":
            badge = f"🌟 **{score}%**"
        elif fit_level == "ALTO":
            badge = f"⭐ **{score}%**"
        else:
            badge = f"🎯 {score}%"

        lines.append(f"| {badge} | [{j_title}]({url}) | {company} | **{portal}** | {loc} | {skills} |")

    lines.append("")
    lines.append("---")
    lines.append(f"💡 *Notificación generada automáticamente por [AI Job Search](https://github.com/{repo}) para el perfil {p_cfg['name']}.*")
    body = "\n".join(lines)

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {gh_token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AIJobSearch-Digest",
    }

    issue_label = p_cfg["issue_label"]

    # 1. Cerrar issues antiguos de este mismo perfil para mantener limpio el repositorio
    try:
        req_list = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/issues?labels={issue_label}&state=open",
            headers=headers
        )
        with urllib.request.urlopen(req_list, timeout=10) as resp:
            old_issues = json.loads(resp.read().decode("utf-8"))
            for old_iss in old_issues:
                iss_num = old_iss.get("number")
                close_payload = json.dumps({"state": "closed"}).encode("utf-8")
                req_close = urllib.request.Request(
                    f"https://api.github.com/repos/{repo}/issues/{iss_num}",
                    data=close_payload,
                    headers=headers,
                    method="PATCH"
                )
                urllib.request.urlopen(req_close, timeout=10)
    except Exception as e:
        print(f"[WARN] No se pudieron cerrar issues antiguos con label '{issue_label}': {e}", file=sys.stderr)

    # 2. Crear nuevo issue asignado al usuario
    payload = json.dumps({
        "title": title,
        "body": body,
        "assignees": ["ebolivar1000"],
        "labels": [issue_label]
    }).encode("utf-8")

    req_create = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=payload,
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req_create, timeout=15) as resp:
            created = json.loads(resp.read().decode("utf-8"))
            iss_url = created.get("html_url")
            print(f"[OK] Notificación publicada en GitHub Issue: {iss_url}")
            print(f"[OK] GitHub enviará la notificación por correo directamente a {recipient}!")
            return True
    except Exception as e:
        print(f"[ERROR] Error al crear GitHub Issue ({profile_key}): {e}", file=sys.stderr)
        return False


def execute_profile_search(profile_key: str, bun_bin: str, seen_dict: dict, dry_run: bool = False, force_save: bool = False) -> tuple[list, dict]:
    """Execute search, filtering, scoring and delivery for a specific profile."""
    p_cfg = PROFILES[profile_key]
    print("\n" + "=" * 70)
    print(f"🚀 INICIANDO BÚSQUEDA PARA: {p_cfg['name']}")
    print("=" * 70)

    all_found = []
    seen_urls_in_batch = set()

    # 1. Búsqueda en Get on Board
    gob_jobs = run_getonboard_search(p_cfg["gob_categories"], p_cfg["gob_keywords"])
    for r in gob_jobs:
        url = r.get("url", "").rstrip("/")
        if url and url not in seen_urls_in_batch:
            seen_urls_in_batch.add(url)
            all_found.append(r)

    # 2. Búsqueda en LinkedIn
    for item in p_cfg["linkedin_queries"]:
        q = item["query"]
        l = item["location"]
        rem = item["remote"]
        print(f"[INFO] [{profile_key.upper()}] LinkedIn: '{q}' en '{l}' (remoto)...")
        results = run_linkedin_search(bun_bin, q, l, rem)
        for r in results:
            if not is_hispanic_or_latam_job(r):
                continue
            url = r.get("url", "").rstrip("/")
            if url and url not in seen_urls_in_batch:
                seen_urls_in_batch.add(url)
                all_found.append(r)

    print(f"[INFO] [{profile_key.upper()}] Total posiciones obtenidas (en región hispanohablante): {len(all_found)}")

    # Deduplicar contra el historial del perfil
    stored_urls = {v.get("url", "").rstrip("/") for v in seen_dict.values() if isinstance(v, dict)}
    stored_pairs = {(v.get("company", "").strip().lower(), v.get("title", "").strip().lower()) for v in seen_dict.values() if isinstance(v, dict)}

    new_jobs = []
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    today_str = datetime.date.today().strftime("%d/%m/%Y")
    discarded_english_count = 0

    for j in all_found:
        url = j.get("url", "").rstrip("/")
        comp = j.get("company", "").strip().lower()
        tit = j.get("title", "").strip().lower()

        if url in stored_urls or (comp, tit) in stored_pairs:
            continue

        # Filtro de inglés en título y datos básicos
        basic_text = f"{j.get('title', '')} {j.get('company', '')} {j.get('location', '')}"
        has_eng, eng_term = has_advanced_english_requirement(basic_text)
        if has_eng:
            print(f"[FILTRO INGLÉS - {profile_key.upper()}] Descartada '{j.get('title')}' ({j.get('company')}) por título: '{eng_term}'")
            discarded_english_count += 1
            continue

        # Si no tiene descripción (LinkedIn) y parece vacante prometedora, consultar detalle
        description = j.get("description", "")
        if not description and j.get("portal") == "LinkedIn":
            j_id = j.get("id")
            if j_id and str(j_id).isdigit():
                description = fetch_linkedin_description(bun_bin, str(j_id))
                j["description"] = description

        # Filtro profundo de inglés en descripción
        if description:
            has_eng_desc, eng_desc_term = has_advanced_english_requirement(description)
            if has_eng_desc:
                print(f"[FILTRO INGLÉS - {profile_key.upper()}] Descartada '{j.get('title')}' ({j.get('company')}) por requisito en descripción: '{eng_desc_term}'")
                discarded_english_count += 1
                continue

        # Puntuar la vacante según el perfil activo
        fit_score, fit_level, matched_skills = score_and_enrich_job(j, profile_key)

        # Filtrar vacantes no afines (< 35% fit)
        if fit_score < 35:
            continue

        j["fit_score"] = fit_score
        j["fit_level"] = fit_level
        j["matched_skills"] = matched_skills

        job_id = j.get("id") or str(len(seen_dict) + 1)
        j_record = {
            "title": j.get("title"),
            "company": j.get("company"),
            "location": j.get("location"),
            "url": j.get("url"),
            "date": j.get("date"),
            "first_seen": now_iso,
            "status": "new",
            "fit": fit_level.lower(),
            "fit_score": fit_score,
            "matched_skills": matched_skills,
            "portal": j.get("portal", "LinkedIn"),
            "profile": profile_key,
        }
        seen_dict[job_id] = j_record
        stored_urls.add(url)
        stored_pairs.add((comp, tit))
        new_jobs.append(j)

    # Ordenar por afinidad
    new_jobs.sort(key=lambda x: x.get("fit_score", 0), reverse=True)

    print(f"[INFO] [{profile_key.upper()}] Vacantes descartadas por exigir inglés avanzado/fluido: {discarded_english_count}")
    print(f"[INFO] [{profile_key.upper()}] Nuevas vacantes acordes encontradas: {len(new_jobs)}")

    if new_jobs:
        # 1. Guardar archivo HTML local
        digest_html_file = REPO_ROOT / "job_scraper" / p_cfg["html_file"]
        digest_html_file.parent.mkdir(parents=True, exist_ok=True)
        html_body = generate_html_email(new_jobs, today_str, profile_key)
        digest_html_file.write_text(html_body, encoding="utf-8")
        print(f"[INFO] [{profile_key.upper()}] Reporte HTML guardado en {digest_html_file}")

        # 2. Agregar a GITHUB_STEP_SUMMARY
        write_github_step_summary(new_jobs, today_str, profile_key)

        # 3. Título del email según el requerimiento del usuario
        email_subject = p_cfg["email_subject"].format(date=today_str)
        recipient = os.environ.get("GMAIL_USER", "ebolivar1000@gmail.com")

        if dry_run:
            print(f"[DRY-RUN] Simulación [{profile_key.upper()}]: se enviarían {len(new_jobs)} vacantes a {recipient} con asunto '{email_subject}'.")
            return new_jobs, seen_dict

        # Intentar envío directo vía Gmail SMTP
        email_sent = send_email(email_subject, html_body, recipient)

        # Si SMTP falla, canal de respaldo garantizado vía GitHub Issue
        if not email_sent:
            print(f"[INFO] [{profile_key.upper()}] SMTP no disponible. Activando canal de respaldo garantizado mediante GitHub Issue...")
            issue_sent = create_github_issue_digest(new_jobs, today_str, recipient, profile_key)
            if issue_sent:
                email_sent = True
                print(f"[OK] [{profile_key.upper()}] Notificación garantizada entregada mediante GitHub Issue.")

        if not email_sent and not force_save:
            print(f"[WARN] [{profile_key.upper()}] No se pudo entregar por SMTP ni Issue. Se preserva historial para reintento.", file=sys.stderr)
    else:
        print(f"[INFO] [{profile_key.upper()}] No se encontraron nuevas vacantes acordes hoy.")

    return new_jobs, seen_dict


def main():
    parser = argparse.ArgumentParser(description="Daily Job Digest & Notification for Everth Bolivar (Dual Profile)")
    parser.add_argument("--profile", choices=["sde", "agentic", "all"], default="all", help="Perfil a buscar: 'sde', 'agentic', o 'all' (ambos)")
    parser.add_argument("--force-save", action="store_true", help="Guardar vacantes en seen_jobs.json incluso si no se envía el correo")
    parser.add_argument("--dry-run", action="store_true", help="Ejecutar búsqueda y reporte sin enviar correo ni alterar historial")
    args = parser.parse_args()

    bun_bin = find_bun()
    print(f"[INFO] Using Bun binary: {bun_bin}")

    seen_data = load_seen_jobs()
    seen_sde = seen_data.get("seen_sde", {})
    seen_agentic = seen_data.get("seen_agentic", {})

    profiles_to_run = ["sde", "agentic"] if args.profile == "all" else [args.profile]

    results_summary = {}

    for p in profiles_to_run:
        target_dict = seen_sde if p == "sde" else seen_agentic
        found_jobs, updated_dict = execute_profile_search(
            p,
            bun_bin,
            target_dict,
            dry_run=args.dry_run,
            force_save=args.force_save,
        )
        if p == "sde":
            seen_sde = updated_dict
        else:
            seen_agentic = updated_dict
        results_summary[p] = len(found_jobs)

    if not args.dry_run:
        seen_data["seen_sde"] = seen_sde
        seen_data["seen_agentic"] = seen_agentic
        # Combinar para compatibilidad hacia atrás
        combined_seen = dict(seen_data.get("seen", {}))
        combined_seen.update(seen_sde)
        combined_seen.update(seen_agentic)
        seen_data["seen"] = combined_seen
        save_seen_jobs(seen_data)
        print("[INFO] Historial dual guardado exitosamente en seen_jobs.json")

    print("\n" + "=" * 70)
    print("RESUMEN DE EJECUCIÓN DUAL:")
    for p, count in results_summary.items():
        p_name = PROFILES[p]["name"]
        print(f"  - {p.upper()} ({p_name}): {count} vacantes")
    print("=" * 70)


if __name__ == "__main__":
    main()
