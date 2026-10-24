"""
trouver_emails.py
-----------------
Cherche l'adresse email de contact de chaque entreprise en visitant son site web
(page d'accueil + pages "contact"), puis écrit  data/emails_entreprises.csv  (colonnes : nom,email,source).

L'application lit déjà ce fichier : le bouton « Contacter par email » remplit alors le champ « À » de Gmail.

Utilisation (dans le dossier du projet, venv activé) :
    python trouver_emails.py

- Les emails déjà présents dans data/emails_entreprises.csv (par ex. ajoutés à la main) ne sont PAS écrasés.
- Tu peux ouvrir le CSV et corriger / ajouter des emails à la main, puis relancer l'app.
- Respecte les sites : peu de pages par site, petite pause, User-Agent clair.
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent
F_ENTREPRISES = BASE / "data" / "entreprises_ia_marrakech_clean.csv"
F_EMAILS = BASE / "data" / "emails_entreprises.csv"

CONTACT_PATHS = ["", "/contact", "/contact-us", "/contactez-nous", "/nous-contacter", "/contacts", "/about", "/a-propos"]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ProjetIAJobs/1.0; recherche email de contact pour candidature)"}
TIMEOUT = 8
WORKERS = 6

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
BAD_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js", ".woff", ".woff2", ".ico")
BAD_DOMAINS = ("example.com", "domain.com", "email.com", "sentry.io", "wixpress.com", "sentry-next.wixpress.com",
               "godaddy.com", "google.com", "facebook.com", "instagram.com", "schema.org", "w3.org", "yourdomain.com")
BAD_LOCAL = ("your", "name", "email", "user", "test", "nom", "exemple", "example", "noreply", "no-reply", "donotreply")
FREE_MAIL = ("gmail.com", "yahoo.com", "yahoo.fr", "hotmail.com", "outlook.com", "live.com", "menara.ma")
PREFERRED = ("rh", "recrutement", "hr", "jobs", "career", "careers", "stage", "stages", "contact", "info", "infos", "hello", "bonjour")


def decode_cfemail(hexstr):
    """Décode les emails protégés par Cloudflare (data-cfemail)."""
    try:
        key = int(hexstr[:2], 16)
        return "".join(chr(int(hexstr[i:i + 2], 16) ^ key) for i in range(2, len(hexstr), 2))
    except ValueError:
        return ""


def clean(text):
    text = text.replace("[at]", "@").replace("(at)", "@").replace(" [arobase] ", "@").replace("[dot]", ".").replace("(dot)", ".")
    return text


def emails_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    found = set()
    for a in soup.select('a[href^="mailto:"]'):
        found.add(a["href"][7:].split("?")[0].strip())
    for el in soup.select("[data-cfemail]"):
        found.add(decode_cfemail(el["data-cfemail"]))
    found.update(EMAIL_RE.findall(clean(soup.get_text(" "))))
    found.update(EMAIL_RE.findall(clean(html)))
    out = set()
    for e in found:
        e = e.strip().strip(".,;:()<>").lower()
        if not EMAIL_RE.fullmatch(e) or e.endswith(BAD_EXT):
            continue
        local, domain = e.split("@", 1)
        if domain in BAD_DOMAINS or any(local.startswith(b) for b in BAD_LOCAL):
            continue
        out.add(e)
    return out


def score(email, site_domain):
    local, domain = email.split("@", 1)
    s = 0
    if site_domain and (domain == site_domain or domain.endswith("." + site_domain) or site_domain.endswith("." + domain)):
        s += 10                       # même domaine que le site : le plus fiable
    elif domain in FREE_MAIL:
        s += 4                        # petite entreprise avec un Gmail : acceptable
    if local in PREFERRED:
        s += 3 - min(PREFERRED.index(local), 3) * 0.2
    return s


def find_email(site):
    """Retourne (email, url_source) ou ('', '')."""
    if not site or not isinstance(site, str):
        return "", ""
    if not site.startswith("http"):
        site = "https://" + site
    host = urlparse(site).netloc.lower().removeprefix("www.")
    candidates = {}
    for path in CONTACT_PATHS:
        url = urljoin(site if path == "" else site.rstrip("/") + "/", path.lstrip("/")) if path else site
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
            if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", ""):
                continue
            for e in emails_from_html(r.text):
                candidates.setdefault(e, url)
        except requests.RequestException:
            continue
        time.sleep(0.4)
        if any(score(e, host) >= 10 for e in candidates):     # email du bon domaine trouvé : on s'arrête
            break
    if not candidates:
        return "", ""
    best = max(candidates, key=lambda e: score(e, host))
    return best, candidates[best]


def main():
    ent = pd.read_csv(F_ENTREPRISES)
    existing = {}
    if F_EMAILS.exists():
        old = pd.read_csv(F_EMAILS).dropna(subset=["nom", "email"])
        for _, r in old.iterrows():
            src = r["source"] if "source" in old.columns and pd.notna(r["source"]) else ""
            existing[str(r["nom"]).strip()] = (str(r["email"]).strip(), str(src))

    todo = [(str(r["nom"]).strip(), r.get("site_web")) for _, r in ent.iterrows() if str(r["nom"]).strip() not in existing]
    print(f"{len(ent)} entreprises, {len(existing)} email(s) déjà connus, {len(todo)} à chercher...")

    def work(item):
        nom, site = item
        email, src = find_email(site)
        print(f"  {'OK ' if email else '-- '} {nom[:45]:45} {email}")
        return nom, email, src

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(work, todo))

    rows = [{"nom": n, "email": e, "source": s} for n, (e, s) in existing.items()]
    rows += [{"nom": n, "email": e, "source": s} for n, e, s in results if e]
    pd.DataFrame(rows, columns=["nom", "email", "source"]).to_csv(F_EMAILS, index=False, encoding="utf-8")
    trouves = sum(1 for _, e, _ in results if e)
    print(f"\nTerminé : {trouves} nouvel(s) email(s) trouvé(s), {len(rows)} au total -> {F_EMAILS}")
    print("Ouvre ce fichier pour vérifier/corriger, puis relance l'application.")


if __name__ == "__main__":
    main()
