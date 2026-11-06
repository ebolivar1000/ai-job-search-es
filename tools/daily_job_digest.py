#!/usr/bin/env python3
"""Daily Job Digest & Notification for Everth Bolivar.

Executes priority searches for remote Senior Data Engineer, Cloud ETL,
and Python/FastAPI roles in Spanish-speaking countries and Latin America
across LinkedIn and Get on Board, deduplicates against seen jobs, and
sends an HTML summary email to ebolivar1000@gmail.com.
"""

import argparse
import datetime
import json
import os
import smtplib
import subprocess
import sys
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
    # Argentina
    {"query": "Senior Data Engineer", "location": "Argentina", "remote": "remote"},
    {"query": "Data Engineer", "location": "Argentina", "remote": "remote"},
    {"query": "Python FastAPI", "location": "Argentina", "remote": "remote"},
    # Latinoamérica
    {"query": "Data Engineer", "location": "Latin America", "remote": "remote"},
    {"query": "Senior Data Engineer", "location": "Latin America", "remote": "remote"},
    {"query": "Analytics Engineer", "location": "Latin America", "remote": "remote"},
    {"query": "Python Backend", "location": "Latin America", "remote": "remote"},
    # España (100% teletrabajo en español)
    {"query": "Data Engineer", "location": "Spain", "remote": "remote"},
    {"query": "Ingeniero de Datos", "location": "Spain", "remote": "remote"},
    # Colombia & México
    {"query": "Data Engineer", "location": "Colombia", "remote": "remote"},
    {"query": "Data Engineer", "location": "Mexico", "remote": "remote"},
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
    """Build a modern, clean HTML email template."""
    job_cards_html = ""
    for j in new_jobs:
        title = j.get("title", "Posición sin título")
        company = j.get("company", "Empresa no especificada")
        loc = j.get("location", "Remoto")
        url = j.get("url", "#")
        date_posted = j.get("date", "Reciente")
        portal = j.get("portal", "LinkedIn")

        portal_bg = "#0077b5" if portal == "LinkedIn" else "#00b493"

        job_cards_html += f"""
        <div style="background-color: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; padding: 18px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <h3 style="margin: 0; color: #1e293b; font-size: 17px; font-weight: 600;">{title}</h3>
                <div>
                    <span style="background-color: {portal_bg}; color: #ffffff; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 9999px; margin-right: 4px;">{portal}</span>
                    <span style="background-color: #e0f2fe; color: #0369a1; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 9999px;">100% Remoto</span>
                </div>
            </div>
            <p style="margin: 0 0 12px 0; color: #475569; font-size: 14px;">
                🏢 <strong>{company}</strong> &nbsp;|&nbsp; 📍 {loc} &nbsp;|&nbsp; 📅 {date_posted}
            </p>
            <a href="{url}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; text-decoration: none; padding: 8px 14px; border-radius: 6px; font-size: 13px; font-weight: 500;">
                Ver Vacante en {portal} &rarr;
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
                <p style="margin: 4px 0 0 0; font-size: 12px; opacity: 0.8;">
                    🌍 Filtrado exclusivo: Países Hispanohablantes & Latinoamérica (LinkedIn + Get on Board)
                </p>
            </div>
            <div style="padding: 24px; background-color: #f1f5f9;">
                <p style="margin: 0 0 18px 0; font-size: 15px; color: #334155;">
                    Se encontraron <strong>{len(new_jobs)} nuevas vacantes</strong> acordes a tu perfil de <em>Senior Data Engineer, Cloud & Python/FastAPI</em>:
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


def send_email(subject: str, html_content: str, recipient: str) -> bool:
    """Send HTML email via Gmail SMTP using App Password."""
    smtp_user = os.environ.get("GMAIL_USER", "ebolivar1000@gmail.com")
    smtp_password = os.environ.get("GMAIL_APP_PASSWORD")

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

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, recipient, msg.as_string())
        print(f"[OK] Correo enviado exitosamente a {recipient}!")
        return True
    except Exception as e:
        print(f"[ERROR] Error al enviar correo vía SMTP a {recipient}: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Daily Job Digest & Notification")
    parser.add_argument("--force-save", action="store_true", help="Guardar vacantes en seen_jobs.json incluso si no se envía el correo")
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
            "portal": j.get("portal", "LinkedIn"),
            "source": "cli",
        }
        seen_dict[job_id] = j_record
        stored_urls.add(url)
        stored_pairs.add((comp, tit))
        new_jobs.append(j)

    print(f"[INFO] Nuevas vacantes encontradas: {len(new_jobs)}")

    if new_jobs:
        subject = f"[AI Job Search] {len(new_jobs)} nuevas vacantes remotas encontradas ({today_str})"
        html_body = generate_html_email(new_jobs, today_str)
        recipient = os.environ.get("GMAIL_USER", "ebolivar1000@gmail.com")
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
                    print("::error title=Error SMTP::Falló el envío del correo con las credenciales de Gmail.", file=sys.stderr)
                    sys.exit(1)
            else:
                print("[WARN] Correo no enviado; no se modificó seen_jobs.json para que las vacantes no se pierdan en futuras búsquedas.")
    else:
        print("[INFO] No se encontraron nuevas vacantes hoy. Se omite el envío del correo.")


if __name__ == "__main__":
    main()
