#!/usr/bin/env python3
"""Daily Job Digest & Notification for Everth Bolivar.

Executes priority searches for remote Senior Data Engineer, Cloud ETL,
and Python/FastAPI roles, deduplicates against seen jobs, and sends
an HTML summary email to ebolivar1000@gmail.com.
"""

import datetime
import json
import os
import smtplib
import subprocess
import sys
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

# Search configurations
SEARCH_QUERIES = [
    {"query": "Senior Data Engineer", "location": "Remote", "remote": "remote"},
    {"query": "Data Engineer", "location": "Argentina", "remote": "remote"},
    {"query": "Python FastAPI", "location": "Remote", "remote": "remote"},
    {"query": "Analytics Engineer", "location": "Remote", "remote": "remote"},
    {"query": "Snowflake Data Engineer", "location": "Remote", "remote": "remote"},
    {"query": "AWS Data Engineer", "location": "Remote", "remote": "remote"},
]


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


def run_search(bun_bin: str, query: str, location: str, remote: str = "remote", limit: int = 15) -> list:
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
        return results if isinstance(results, list) else []
    except subprocess.CalledProcessError as e:
        print(f"[WARN] Search failed for '{query}' in '{location}': {e.stderr}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[WARN] Unexpected error in search '{query}': {e}", file=sys.stderr)
        return []


def generate_html_email(new_jobs: list, today_str: str) -> str:
    """Build a modern, clean HTML email template."""
    job_cards_html = ""
    for j in new_jobs:
        title = j.get("title", "Posición sin título")
        company = j.get("company", "Empresa no especificada")
        loc = j.get("location", "Remoto")
        url = j.get("url", "#")
        date_posted = j.get("date", "Reciente")

        job_cards_html += f"""
        <div style="background-color: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; padding: 18px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <h3 style="margin: 0; color: #1e293b; font-size: 17px; font-weight: 600;">{title}</h3>
                <span style="background-color: #e0f2fe; color: #0369a1; font-size: 12px; font-weight: 600; padding: 3px 8px; border-radius: 9999px;">100% Remoto</span>
            </div>
            <p style="margin: 0 0 10px 0; color: #475569; font-size: 14px;">
                🏢 <strong>{company}</strong> &nbsp;|&nbsp; 📍 {loc} &nbsp;|&nbsp; 📅 {date_posted}
            </p>
            <a href="{url}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; text-decoration: none; padding: 8px 14px; border-radius: 6px; font-size: 13px; font-weight: 500;">
                Ver Vacante en LinkedIn &rarr;
            </a>
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
                <p style="margin: 0; font-size: 14px; opacity: 0.9;">
                    Búsqueda activa para <strong>Everth Bolivar</strong> &bull; {today_str}
                </p>
            </div>
            <div style="padding: 24px; background-color: #f1f5f9;">
                <p style="margin: 0 0 18px 0; font-size: 15px; color: #334155;">
                    Se encontraron <strong>{len(new_jobs)} nuevas vacantes</strong> acordes a tu perfil de <em>Senior Data Engineer, Cloud & Backend</em>:
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


def send_email(subject: str, html_content: str, recipient: str):
    """Send HTML email via Gmail SMTP using App Password."""
    smtp_user = os.environ.get("GMAIL_USER", "ebolivar1000@gmail.com")
    smtp_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not smtp_password:
        print("[WARN] GMAIL_APP_PASSWORD is not set. Email notification skipped.", file=sys.stderr)
        print(f"[INFO] Prepared '{subject}' for {recipient}")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"AI Job Search <{smtp_user}>"
    msg["To"] = recipient

    part = MIMEText(html_content, "html", "utf-8")
    msg.attach(part)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, recipient, msg.as_string())
        print(f"[OK] Email sent successfully to {recipient}!")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send email via SMTP: {e}", file=sys.stderr)
        return False


def main():
    bun_bin = find_bun()
    print(f"[INFO] Using Bun binary: {bun_bin}")

    seen_data = load_seen_jobs()
    seen_dict = seen_data.get("seen", {})

    all_found = []
    seen_urls_in_batch = set()

    for item in SEARCH_QUERIES:
        q = item["query"]
        l = item["location"]
        rem = item["remote"]
        print(f"[INFO] Searching: query='{q}', location='{l}'...")
        results = run_search(bun_bin, q, l, rem)
        for r in results:
            url = r.get("url", "").rstrip("/")
            if url and url not in seen_urls_in_batch:
                seen_urls_in_batch.add(url)
                all_found.append(r)

    print(f"[INFO] Total positions retrieved in search: {len(all_found)}")

    # Deduplicate against stored history
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

        job_id = j.get("id") or str(len(seen_dict) + 1)
        j_record = {
            "title": j.get("title"),
            "company": j.get("company"),
            "location": j.get("location"),
            "url": j.get("url"),
            "date": j.get("date"),
            "first_seen": now_iso,
            "status": "new",
            "fit": "high",
            "portal": "linkedin-search",
            "source": "cli",
        }
        seen_dict[job_id] = j_record
        stored_urls.add(url)
        stored_pairs.add((comp, tit))
        new_jobs.append(j)

    print(f"[INFO] New (unseen) jobs found: {len(new_jobs)}")

    if new_jobs:
        # Save updated seen jobs
        seen_data["seen"] = seen_dict
        save_seen_jobs(seen_data)
        print(f"[INFO] Saved {len(new_jobs)} new entries to seen_jobs.json")

        subject = f"[AI Job Search] {len(new_jobs)} nuevas vacantes remotas encontradas ({today_str})"
        html_body = generate_html_email(new_jobs, today_str)
        recipient = "ebolivar1000@gmail.com"
        send_email(subject, html_body, recipient)
    else:
        print("[INFO] No new jobs today. Skipping email.")


if __name__ == "__main__":
    main()
