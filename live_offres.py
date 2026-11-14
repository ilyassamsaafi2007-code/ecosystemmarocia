"""
live_offres.py
--------------
« Offres actuelles » : récupère à la demande les offres d'emploi INFORMATIQUE récentes
(IA, cybersécurité, développement, data, réseaux/systèmes...) sur Rekrute, les classe par catégorie
et les enregistre dans la base (db.live_*), séparément du CSV des offres de départ.

Utilisé par app_web.py (/offres-actuelles et le bouton « Actualiser »).

Pour ajouter une autre source plus tard : écrire une fonction qui retourne une liste de dicts
(mêmes clés que parse_rekrute) et l'ajouter dans SOURCES.
"""

import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.rekrute.com"
SEARCH_URL = BASE_URL + "/fr/offres.html"
# Fonctions Rekrute : 13 = Informatique / Electronique, 23 = Télécom / Réseaux, 19 = Internet / Multimédia
FUNCTION_IDS = (13, 23, 19)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
}
TIMEOUT = 8                    # secondes par requête (3 requêtes en parallèle)
COOLDOWN_SECONDS = 15 * 60     # une actualisation toutes les 15 min au maximum (pour tous les utilisateurs)
GARDER_JOURS = 90              # les offres publiées il y a plus de 90 jours sont supprimées

CATEGORIES = {
    "ia": "Intelligence artificielle",
    "cyber": "Cybersécurité",
    "dev": "Développement",
    "data": "Data & BI",
    "infra": "Réseaux, systèmes & cloud",
    "autre": "Informatique (autre)",
}

# Ordre = priorité (une offre « Data & IA » est classée IA, « Développeur Data » est classée Data...)
_MOTS = [
    ("cyber", r"cyber|securite (informatique|des (systemes|si|donnees)|reseau|applicative|operationnelle)"
              r"|\bsoc\b|pentest|\brssi\b|\bssi\b|\bsiem\b|infosec|forensic|vulnerabilit|\biam\b"),
    ("ia", r"\bia\b|\bai\b|intelligence artificielle|machine learning|deep learning|\bml\b|\bnlp\b|\bllm\b"
           r"|genai|ia generative|computer vision|vision par ordinateur|data scientist|mlops"),
    ("data", r"\bdata\b|donnees|\bbi\b|power ?bi|big data|\bsql\b|\betl\b|dataviz|tableau|business intelligence"
             r"|analytics|\bdba\b|decisionnel|statisticien"),
    ("dev", r"developp|developer|\bdev\b|full ?stack|front ?end|back ?end|\bjava\b|python|\.net|\bphp\b|react"
            r"|angular|node\.?js|laravel|symfony|mobile|android|\bios\b|flutter|ingenieur (logiciel|etudes)"
            r"|programmeur|webmaster|integrateur|software|\babap\b|salesforce|\bapi\b|\bweb\b|test(eur)? logiciel"),
    ("infra", r"reseau|systeme|admin|cloud|devops|infrastructure|help ?desk|service desk|support|technicien"
              r"|exploitation|linux|windows|azure|\baws\b|\bgcp\b|kubernetes|docker|telecom|voip|ccna|cisco|\bsre\b"),
]
_MOTS = [(cat, re.compile(rx)) for cat, rx in _MOTS]

_ID_RE = re.compile(r"/offre-emploi-.*?-(\d+)\.html")
_PUB_RE = re.compile(r"Publication\s*:\s*du\s*(\d{2}/\d{2}/\d{4})\s*au\s*(\d{2}/\d{2}/\d{4})", re.I)
_CONTRAT_RE = re.compile(r"Type de contrat propos[ée]\s*:\s*(.+?)\s*-\s*T[ée]l[ée]travail\s*:\s*(\w+)", re.I)
_EXP_RE = re.compile(r"Exp[ée]rience requise\s*:\s*(.+?)\s*Niveau d.[ée]tude", re.I)


# ------------------------------------------------------------ classification ----

def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return s.lower()


def classer(titre, description=""):
    """Catégorie principale d'une offre : on regarde d'abord le TITRE, puis la description."""
    for texte in (_norm(titre), _norm(description)):
        for cat, rx in _MOTS:
            if rx.search(texte):
                return cat
    return "autre"


# ------------------------------------------------------------------ Rekrute ----

def _iso(jjmmaaaa):
    try:
        return datetime.strptime(jjmmaaaa, "%d/%m/%Y").date().isoformat()
    except (TypeError, ValueError):
        return None


def parse_rekrute(html):
    """Transforme une page de résultats Rekrute en liste d'offres (dicts)."""
    soup = BeautifulSoup(html, "html.parser")
    liens = [a for a in soup.select("h2 a[href]") if _ID_RE.search(a["href"])]
    if not liens:     # plan B si la structure change : tous les liens d'offres qui ressemblent à « Titre | Ville »
        liens = [a for a in soup.select("a[href]") if _ID_RE.search(a["href"]) and "|" in a.get_text()]
    offres, vus = [], set()
    for a in liens:
        rid = _ID_RE.search(a["href"]).group(1)
        if rid in vus:
            continue
        vus.add(rid)

        texte = a.get_text(" ", strip=True)
        morceaux = re.split(r"\s*\|\s*", texte)
        titre = " | ".join(morceaux[:-1]) if len(morceaux) > 1 else texte
        ville = re.sub(r"\s*\(.*?\)\s*$", "", morceaux[-1]).strip() if len(morceaux) > 1 else ""

        bloc = a.find_parent("li") or a.find_parent(["article", "div"]) or a.parent
        plat = bloc.get_text(" ", strip=True)
        lignes = [l for l in bloc.get_text("\n", strip=True).split("\n") if l]

        # Entreprise : alt/title du logo (les offres « confidentielles » ont un logo spécial)
        entreprise = ""
        img = bloc.find("img")
        if img is not None:
            if "confidentiel" in (img.get("src") or "").lower():
                entreprise = "Confidentiel"
            else:
                entreprise = (img.get("title") or img.get("alt") or "").strip()

        # Description : la ligne longue juste avant « Publication : du ... au ... »
        description = ""
        for i, l in enumerate(lignes):
            if l.lower().startswith("publication"):
                for prev in reversed(lignes[:i]):
                    if len(prev) >= 40:
                        description = prev
                        break
                break

        pub = _PUB_RE.search(plat)
        contrat = _CONTRAT_RE.search(plat)
        exp = _EXP_RE.search(plat)
        offres.append({
            "id": f"rekrute-{rid}",
            "source": "Rekrute",
            "titre": titre,
            "entreprise": entreprise,
            "ville": ville or "Non précisé",
            "description": description,
            "date_publication": _iso(pub.group(1)) if pub else None,
            "date_fin": _iso(pub.group(2)) if pub else None,
            "lien": urljoin(BASE_URL, a["href"]).split("#")[0].split("?")[0],
            "contrat": contrat.group(1).strip() if contrat else "",
            "teletravail": contrat.group(2).strip() if contrat else "",
            "experience": exp.group(1).strip() if exp else "",
            "categorie": classer(titre, description),
        })
    return offres


def _page_rekrute(function_id):
    # s=3 -> 50 offres par page, o=1 -> les plus récentes d'abord, p=1 -> première page
    r = requests.get(SEARCH_URL, headers=HEADERS, timeout=TIMEOUT,
                     params={"s": 3, "p": 1, "o": 1, "positionId[0]": function_id})
    r.raise_for_status()
    return parse_rekrute(r.text)


def fetch_rekrute():
    """(offres, erreurs) : les 3 fonctions IT sont chargées en parallèle, puis dédoublonnées."""
    offres, erreurs = {}, []
    with ThreadPoolExecutor(max_workers=len(FUNCTION_IDS)) as ex:
        futures = {ex.submit(_page_rekrute, fid): fid for fid in FUNCTION_IDS}
        for fut, fid in futures.items():
            try:
                for o in fut.result():
                    offres.setdefault(o["id"], o)
            except Exception as e:                       # réseau, blocage, structure modifiée...
                erreurs.append(f"Rekrute (fonction {fid}) : {type(e).__name__}: {e}")
    return list(offres.values()), erreurs


SOURCES = (fetch_rekrute,)


# ------------------------------------------------------------- actualisation ----

def _maintenant():
    return datetime.now(timezone.utc)


def refresh(db, force=False):
    """
    Récupère les nouvelles offres et les enregistre.
    Retourne {"status": "ok" | "cooldown" | "error", "new": n, "total": n, "wait": secondes, "errors": [...]}.
    """
    now = _maintenant()
    last = db.live_last_refresh()
    if last and not force:
        try:
            depuis = (now - datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds()
        except ValueError:
            depuis = COOLDOWN_SECONDS
        if depuis < COOLDOWN_SECONDS:
            return {"status": "cooldown", "wait": int(COOLDOWN_SECONDS - depuis), "new": 0, "total": 0, "errors": []}

    offres, erreurs = [], []
    for source in SOURCES:
        o, e = source()
        offres += o
        erreurs += e
    if not offres:
        return {"status": "error", "new": 0, "total": 0, "errors": erreurs}

    existants = db.live_ids()
    nouvelles = sum(1 for o in offres if o["id"] not in existants)
    db.live_put_many(offres, now.isoformat())
    db.live_purge((date.today() - timedelta(days=GARDER_JOURS)).isoformat())
    return {"status": "ok", "new": nouvelles, "total": len(offres), "errors": erreurs}
