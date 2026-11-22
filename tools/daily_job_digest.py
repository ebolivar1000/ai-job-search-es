#!/usr/bin/env python3
"""Daily Job Digest & Notification for Everth Bolivar.

Executes priority searches for remote Senior Data Engineer, Cloud ETL,
and Python/FastAPI roles in Spanish-speaking countries and Latin America
across LinkedIn and Get on Board, scores vacancies against candidate profile,
deduplicates against seen jobs, and sends an HTML summary email to ebolivar1000@gmail.com.
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

# Search configurations for LinkedIn (restricted to Hispanic countries & LATAM)
LINKEDIN_QUERIES = [
    # Argentina (Prioridad local y regional)
    {"query": "Senior Data Engineer", "location": "Argentina", "remote": "remote"},
    {"query": "Data Engineer", "location": "Argentina", "remote": "remote"},
    {"query": "Python FastAPI", "location": "Argentina", "remote": "remote"},
    {"query": "Senior Python Developer", "location": "Argentina", "remote": "remote"},
    {"query": "ETL Developer", "location": "Argentina", "remote": "remote"},
    # Latinoamérica (100% Remoto en español / inglés técnico)
    {"query": "Senior Data Engineer", "location": "Latin America", "remote": "remote"},
    {"query": "Data Engineer", "location": "Latin America", "remote": "remote"},
    {"query": "Analytics Engineer", "location": "Latin America", "remote": "remote"},
    {"query": "Snowflake Data Engineer", "location": "Latin America", "remote": "remote"},
    {"query": "Databricks Engineer", "location": "Latin America", "remote": "remote"},
    {"query": "AWS Data Engineer", "location": "Latin America", "remote": "remote"},
    {"query": "Python Backend", "location": "Latin America", "remote": "remote"},
    # España (100% Teletrabajo en español)
    {"query": "Data Engineer", "location": "Spain", "remote": "remote"},
    {"query": "Ingeniero de Datos", "location": "Spain", "remote": "remote"},
    {"query": "Senior Data Engineer", "location": "Spain", "remote": "remote"},
    # Colombia & México (Principales hubs tecnológicos de LATAM)
    {"query": "Data Engineer", "location": "Colombia", "remote": "remote"},
    {"query": "Senior Data Engineer", "location": "Colombia", "remote": "remote"},
    {"query": "Data Engineer", "location": "Mexico", "remote": "remote"},
    {"query": "Senior Data Engineer", "location": "Mexico", "remote": "remote"},
]

# Get on Board categories & keywords
GETONBOARD_CATEGORIES = ["data-science-analytics", "programming"]
GETONBOARD_KEYWORDS = [
    "data engineer",
    "ingeniero de datos",
    "analytics engineer",
    "etl",
    "python",
    "fastapi",
    "snowflake",
    "databricks",
    "backend",
    "big data",
    "aws glue",
    "redshift",
    "airflow",
    "spark",
    "pyspark",
    "data warehouse",
    "powercenter",
    "teradata",
]

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

# Skill patterns for candidate profile scoring (Everth Bolivar)
SKILL_PATTERNS = [
    ("Snowflake", r"\bsnowflake\b"),
    ("Databricks", r"\bdatabricks\b"),
    ("AWS / Cloud", r"\b(aws|glue|redshift|s3|emr)\b"),
    ("Airflow", r"\bairflow\b"),
    ("Spark / PySpark", r"\b(spark|pyspark)\b"),
    ("FastAPI", r"\bfastapi\b"),
    ("Python", r"\bpython\b"),
    ("ETL / Pipelines", r"\b(etl|elt|pipeline[s]?)\b"),
    ("Data Warehouse", r"\b(data\s*warehouse|dwh|data\s*mart)\b"),
    ("Informatica / PowerCenter", r"\b(informatica|powercenter)\b"),
    ("SQL / Relacional", r"\b(sql|postgresql|postgres|oracle|teradata)\b"),
    ("Analytics Engineer", r"\banalytics\s*engineer\b"),
    ("Data Engineer", r"\b(data\s*engineer|ingeniero\s*de\s*datos)\b"),
    ("Backend", r"\bbackend\b"),
    ("Big Data", r"\bbig\s*data\b"),
    ("Docker", r"\bdocker\b"),
]

NEGATIVE_PATTERNS = [
    r"\b(junior|jr|trainee|intern|practicante|pasante)\b",
    r"\b(php|wordpress|ruby|rails|\.net|c#|flutter|swift|ios|android)\b",
    r"\b(qa\s*tester|qa\s*manual|scrum\s*master|ux|ui\s*designer)\b",
]


def score_and_enrich_job(job: dict) -> tuple[int, str, list[str]]:
    """Score a job against Everth Bolivar's Senior Data Engineer / Python FastAPI profile."""
    title = (job.get("title") or "").strip()
    company = (job.get("company") or "").strip()
    location = (job.get("location") or "").strip()
    text = f"{title} {company} {location}".lower()

    # Disqualification / heavy penalty for junior or unrelated stacks
    for neg in NEGATIVE_PATTERNS:
        if re.search(neg, text):
            return 10, "BAJO", []

    score = 40  # base score for remote tech in Hispanic/LATAM region

    # Seniority bonus
    if re.search(r"\b(senior|sr|lead|principal|architect|arquitecto|staff)\b", text):
        score += 25
    elif re.search(r"\b(semi[- ]?senior|ssr)\b", text):
        score += 10

    # Core Data Engineer / Architecture match
    if re.search(r"\b(data\s*engineer|ingeniero\s*de\s*datos|analytics\s*engineer|etl\s*developer|data\s*architect)\b", text):
        score += 25

    # Core Python / Backend match
    if re.search(r"\b(python\s*backend|backend\s*developer|python\s*developer|fastapi)\b", text):
        score += 20

    matched_skills = []
    for skill_name, pattern in SKILL_PATTERNS:
        if re.search(pattern, text):
            matched_skills.append(skill_name)
            if skill_name in ["Snowflake", "Databricks", "AWS / Cloud", "Airflow", "Spark / PySpark", "FastAPI"]:
                score += 15
            elif skill_name in ["Python", "ETL / Pipelines", "Data Warehouse"]:
                score += 10
            elif skill_name in ["SQL / Relacional", "Informatica / PowerCenter"]:
                score += 8
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
    """Load existing seen jobs dictionary."""
    if not SEEN_JOBS_FILE.exists():
        return {"seen": {}}
    try:
        data = json.loads(SEEN_JOBS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "seen" not in data:
            return {"seen": {}}
        return data
    except Exception as e:
        print(f"[WARN] Error loading seen_jobs.json: {e}, starting fresh.", file=sys.stderr)
        return {"seen": {}}


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


def run_getonboard_search() -> list:
    """Fetch remote positions from Get on Board API for tech & data roles in LATAM."""
    print("[INFO] Buscando vacantes en Get on Board (LATAM / Remoto)...")
    results = []
    headers = {"User-Agent": "AIJobSearch/1.0 (+https://github.com/ebolivar1000/ai-job-search-es)"}

    for cat in GETONBOARD_CATEGORIES:
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

                    if any(kw in title_lower for kw in GETONBOARD_KEYWORDS):
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

                        job_dict = {
                            "id": f"gob_{item.get('id')}",
                            "title": title,
                            "company": comp,
                            "location": f"100% Remoto ({zone})",
                            "url": link,
                            "date": date_str,
                            "portal": "Get on Board",
                        }
                        results.append(job_dict)
        except Exception as e:
            print(f"[WARN] Error fetching Get on Board category '{cat}': {e}", file=sys.stderr)

    print(f"[INFO] Get on Board: {len(results)} posiciones remotas encontradas.")
    return results


def generate_html_email(new_jobs: list, today_str: str) -> str:
    """Build a modern, clean HTML email template with matching score badges and extracted tech tags."""
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
                <a href="{url}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; text-decoration: none; padding: 8px 14px; border-radius: 6px; font-size: 13px; font-weight: 500;">
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
        <title>Nuevas Vacantes - Everth Bolivar</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #334155;">
        <div style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); padding: 28px 24px; color: #ffffff;">
                <h1 style="margin: 0 0 6px 0; font-size: 22px; font-weight: 700;">🎯 Resumen Diario de Empleo</h1>
                <p style="margin: 0; font-size: 14px; opacity: 0.95;">
                    Búsqueda activa para <strong>Everth Bolivar</strong> &bull; {today_str}
                </p>
                <p style="margin: 4px 0 0 0; font-size: 12px; opacity: 0.85;">
                    💼 Senior Data Engineer &bull; Cloud ETL (Snowflake, Databricks, AWS) &bull; Python / FastAPI
                </p>
                <div style="margin-top: 14px;">
                    <span style="display: inline-block; background-color: rgba(255,255,255,0.2); padding: 4px 10px; border-radius: 6px; font-size: 12px; margin-right: 6px;">📊 Total nuevas: <strong>{len(new_jobs)}</strong></span>
                    <span style="display: inline-block; background-color: rgba(254,240,138,0.3); color: #fef08a; padding: 4px 10px; border-radius: 6px; font-size: 12px; margin-right: 6px;">🌟 Calce Excelente: <strong>{excellent_count}</strong></span>
                    <span style="display: inline-block; background-color: rgba(219,234,254,0.3); color: #dbeafe; padding: 4px 10px; border-radius: 6px; font-size: 12px;">⭐ Calce Alto: <strong>{high_count}</strong></span>
                </div>
            </div>
            <div style="padding: 24px; background-color: #f1f5f9;">
                <p style="margin: 0 0 18px 0; font-size: 15px; color: #334155;">
                    Se encontraron <strong>{len(new_jobs)} nuevas vacantes</strong> ordenadas por compatibilidad con tu perfil:
                </p>
                {job_cards_html}
            </div>
            <div style="padding: 16px 24px; background-color: #ffffff; text-align: center; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8;">
                Generado automáticamente por el buscador de empleo de AI Job Search &bull; Santa Fe, Argentina
            </div>
        </div>
    </body>
    </html>
    """
    return html


def write_github_step_summary(new_jobs: list, today_str: str):
    """Write an interactive Markdown summary table to $GITHUB_STEP_SUMMARY if available."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    try:
        lines = [
            f"# 🎯 Resumen Diario de Empleo - {today_str}",
            "",
            f"Se encontraron **{len(new_jobs)} nuevas vacantes remotas** en español / LATAM acordes al perfil de **Everth Bolivar** (Senior Data Engineer | Cloud ETL & Python FastAPI).",
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
        print(f"[INFO] Resumen de {len(new_jobs)} vacantes agregado a GITHUB_STEP_SUMMARY.")
    except Exception as e:
        print(f"[WARN] Error al escribir en GITHUB_STEP_SUMMARY: {e}", file=sys.stderr)


def send_email(subject: str, html_content: str, recipient: str) -> bool:
    """Send HTML email via Gmail SMTP using App Password with resilient IPv4, SSL/TLS, and retries."""
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

    # Force IPv4 resolution in getaddrinfo during SMTP connection to prevent IPv6 dropouts in cloud runners
    original_getaddrinfo = socket.getaddrinfo

    def ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    ssl_context = ssl.create_default_context()

    # Connection methods to attempt in order of cloud resilience:
    # 1. Port 465 (Implicit SSL/TLS) - Recommended for automated scripts, avoids STARTTLS handshake drops
    # 2. Port 587 (Explicit STARTTLS)
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
                    print(f"[INFO] Intentando enviar correo vía {cfg['name']} (intento {attempt}/{max_attempts_per_config})...")
                    if cfg["ssl"]:
                        print(f"  -> Conectando a smtp.gmail.com:{cfg['port']} con SSL...")
                        with smtplib.SMTP_SSL("smtp.gmail.com", cfg["port"], context=ssl_context, timeout=30) as server:
                            print("  -> Conexión establecida. Enviando EHLO...")
                            server.ehlo()
                            print(f"  -> Autenticando usuario '{smtp_user}'...")
                            server.login(smtp_user, smtp_password)
                            print(f"  -> Autenticado exitosamente. Enviando mensaje a '{recipient}'...")
                            server.sendmail(smtp_user, recipient, msg.as_string())
                    else:
                        print(f"  -> Conectando a smtp.gmail.com:{cfg['port']}...")
                        with smtplib.SMTP("smtp.gmail.com", cfg["port"], timeout=30) as server:
                            print("  -> Conexión establecida. Enviando EHLO...")
                            server.ehlo()
                            print("  -> Iniciando STARTTLS...")
                            server.starttls(context=ssl_context)
                            print("  -> STARTTLS completado. Enviando segundo EHLO...")
                            server.ehlo()
                            print(f"  -> Autenticando usuario '{smtp_user}'...")
                            server.login(smtp_user, smtp_password)
                            print(f"  -> Autenticado exitosamente. Enviando mensaje a '{recipient}'...")
                            server.sendmail(smtp_user, recipient, msg.as_string())

                    print(f"[OK] Correo enviado exitosamente a {recipient} usando {cfg['name']}!")
                    return True
                except smtplib.SMTPAuthenticationError as auth_err:
                    print(f"[ERROR] Error de autenticación SMTP de Gmail (535): {auth_err}", file=sys.stderr)
                    print("[ERROR] Verifica que el secreto GMAIL_APP_PASSWORD en GitHub contenga una contraseña de aplicación válida (16 caracteres).", file=sys.stderr)
                    return False  # Do not retry if credentials are explicitly rejected
                except Exception as e:
                    print(f"[WARN] Falló intento {attempt} con {cfg['name']}: {type(e).__name__} - {e}", file=sys.stderr)
                    if attempt < max_attempts_per_config:
                        time.sleep(2 * attempt)
    finally:
        socket.getaddrinfo = original_getaddrinfo

    print(f"[ERROR] No se pudo enviar el correo a {recipient} tras agotar todos los protocolos y reintentos.", file=sys.stderr)
    return False


def main():
    parser = argparse.ArgumentParser(description="Daily Job Digest & Notification for Everth Bolivar")
    parser.add_argument("--force-save", action="store_true", help="Guardar vacantes en seen_jobs.json incluso si no se envía el correo")
    parser.add_argument("--dry-run", action="store_true", help="Ejecutar búsqueda y reporte sin enviar correo ni alterar historial")
    args = parser.parse_args()

    bun_bin = find_bun()
    print(f"[INFO] Using Bun binary: {bun_bin}")

    seen_data = load_seen_jobs()
    seen_dict = seen_data.get("seen", {})

    all_found = []
    seen_urls_in_batch = set()

    # 1. Búsqueda en Get on Board (LATAM / Remoto)
    gob_jobs = run_getonboard_search()
    for r in gob_jobs:
        url = r.get("url", "").rstrip("/")
        if url and url not in seen_urls_in_batch:
            seen_urls_in_batch.add(url)
            all_found.append(r)

    # 2. Búsqueda en LinkedIn (Países hispanohablantes & LATAM)
    for item in LINKEDIN_QUERIES:
        q = item["query"]
        l = item["location"]
        rem = item["remote"]
        print(f"[INFO] Buscando en LinkedIn: '{q}' en '{l}' (remoto)...")
        results = run_linkedin_search(bun_bin, q, l, rem)
        for r in results:
            # Filtrar vacantes fuera de países hispanohablantes (ej. India, China, Canadá, etc.)
            if not is_hispanic_or_latam_job(r):
                continue
            url = r.get("url", "").rstrip("/")
            if url and url not in seen_urls_in_batch:
                seen_urls_in_batch.add(url)
                all_found.append(r)

    print(f"[INFO] Total posiciones obtenidas (filtradas a países hispanohablantes): {len(all_found)}")

    # Deduplicar contra el historial guardado
    stored_urls = {v.get("url", "").rstrip("/") for v in seen_dict.values() if isinstance(v, dict)}
    stored_pairs = {(v.get("company", "").strip().lower(), v.get("title", "").strip().lower()) for v in seen_dict.values() if isinstance(v, dict)}

    new_jobs = []
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    today_str = datetime.date.today().strftime("%d/%m/%Y")

    for j in all_found:
        url = j.get("url", "").rstrip("/")
        comp = j.get("company", "").strip().lower()
        tit = j.get("title", "").strip().lower()

        if url in stored_urls or (comp, tit) in stored_pairs:
            continue

        # Score job against candidate profile
        fit_score, fit_level, matched_skills = score_and_enrich_job(j)

        # Filter out completely irrelevant / junior / incompatible roles (< 35% fit)
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
            "source": "cli",
        }
        seen_dict[job_id] = j_record
        stored_urls.add(url)
        stored_pairs.add((comp, tit))
        new_jobs.append(j)

    # Ordenar las vacantes encontradas por calce con el perfil (mayor compatibilidad primero)
    new_jobs.sort(key=lambda x: x.get("fit_score", 0), reverse=True)

    print(f"[INFO] Nuevas vacantes acordes al perfil encontradas: {len(new_jobs)}")

    if new_jobs:
        # Generar GitHub Actions Step Summary si está disponible en el entorno
        write_github_step_summary(new_jobs, today_str)

        subject = f"[AI Job Search] {len(new_jobs)} nuevas vacantes acordes a tu perfil ({today_str})"
        html_body = generate_html_email(new_jobs, today_str)
        recipient = os.environ.get("GMAIL_USER", "ebolivar1000@gmail.com")

        if args.dry_run:
            print(f"[DRY-RUN] Simulación completada. Se enviarían {len(new_jobs)} vacantes a {recipient}.")
            return

        email_sent = send_email(subject, html_body, recipient)

        if email_sent or args.force_save:
            seen_data["seen"] = seen_dict
            save_seen_jobs(seen_data)
            print(f"[INFO] Guardadas {len(new_jobs)} nuevas entradas en seen_jobs.json")
        else:
            if os.environ.get("GITHUB_ACTIONS") == "true":
                if not os.environ.get("GMAIL_APP_PASSWORD"):
                    print(
                        "\n::error title=Falta secreto GMAIL_APP_PASSWORD::El secreto 'GMAIL_APP_PASSWORD' no está configurado en GitHub Secrets.\n"
                        "Para recibir los correos diarios en tu bandeja de entrada:\n"
                        "1. Ve a tu repositorio: Settings -> Secrets and variables -> Actions\n"
                        "2. Haz clic en 'New repository secret'\n"
                        "3. Nombre: GMAIL_APP_PASSWORD\n"
                        "4. Valor: Contraseña de aplicación de Gmail (16 caracteres generada en https://myaccount.google.com/apppasswords)\n",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                else:
                    print("::error title=Error SMTP::Falló el envío del correo con las credenciales de Gmail tras reintentos.", file=sys.stderr)
                    sys.exit(1)
            else:
                print("[WARN] Correo no enviado; no se modificó seen_jobs.json para que las vacantes no se pierdan en futuras búsquedas.")
    else:
        print("[INFO] No se encontraron nuevas vacantes acordes al perfil hoy.")


if __name__ == "__main__":
    main()
