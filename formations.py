"""
formations.py
-------------
Plateforme de formations gratuites : domaines IT -> modules (vidéo YouTube + test) -> soft skills -> certificat.

Le contenu est dans  data/formations.json  (voir le modèle dans ce fichier). Pour ajouter une vidéo :
colle son lien YouTube (ou son identifiant) dans le champ "video" d'un module. Un module sans vidéo est
ignoré (invisible pour les utilisateurs), un domaine sans module jouable est caché.

Vérifier le contenu :   python formations.py
"""

import json
import re
import sys
from pathlib import Path

FICHIER = Path(__file__).parent / "data" / "formations.json"
NOTE_MINI = 70            # % de bonnes réponses pour valider un module
MIN_VISIONNAGE = 30       # secondes minimum entre l'ouverture de la vidéo et l'envoi du test

_YT = re.compile(r"(?:v=|youtu\.be/|embed/|shorts/|live/)([A-Za-z0-9_-]{11})")


def youtube_id(valeur):
    """Accepte un lien YouTube (watch, youtu.be, embed, shorts) ou directement l'identifiant (11 caractères)."""
    valeur = (valeur or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", valeur):
        return valeur
    m = _YT.search(valeur)
    return m.group(1) if m else ""


def _quiz_valide(quiz):
    ok = []
    for q in quiz or []:
        opts = q.get("options") or []
        rep = q.get("reponse")
        if q.get("question") and len(opts) >= 2 and isinstance(rep, int) and 0 <= rep < len(opts):
            ok.append(q)
    return ok


def _module(m, phase):
    vid = youtube_id(m.get("video"))
    quiz = _quiz_valide(m.get("quiz"))
    if not (m.get("id") and m.get("titre") and vid and quiz):
        return None
    return {**m, "video_id": vid, "quiz": quiz, "phase": phase}


def charger():
    """{'domaines': [...], 'softskills': [...]} : uniquement les modules jouables."""
    try:
        brut = json.loads(FICHIER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"domaines": [], "softskills": []}
    soft = [m for m in (_module(x, "soft") for x in brut.get("softskills", [])) if m]
    domaines = []
    for d in brut.get("domaines", []):
        mods = [m for m in (_module(x, "tech") for x in d.get("modules", [])) if m]
        if d.get("id") and d.get("titre") and mods:
            domaines.append({**d, "modules": mods})
    return {"domaines": domaines, "softskills": soft}


def trouver_domaine(catalogue, did):
    return next((d for d in catalogue["domaines"] if d["id"] == did), None)


def parcours(domaine, catalogue):
    """Modules techniques du domaine, puis les soft skills (communs à tous les domaines)."""
    return list(domaine["modules"]) + list(catalogue["softskills"])


def etat(domaine, catalogue, faits, certificat=None):
    """
    faits = {module_id: {"score": n, "date": iso}} (partagé entre domaines : les soft skills ne se refont pas).
    Retourne la liste des modules avec leur statut (validé / débloqué / verrouillé) et un résumé.
    """
    faits = faits or {}
    liste, precedent_ok = [], True
    for m in parcours(domaine, catalogue):
        valide = m["id"] in faits
        liste.append({"m": m, "valide": valide, "score": faits.get(m["id"], {}).get("score"),
                      "debloque": valide or precedent_ok})
        precedent_ok = precedent_ok and valide
    nb, valides = len(liste), sum(1 for x in liste if x["valide"])
    scores = [x["score"] for x in liste if x["score"] is not None]
    prochain = next((x for x in liste if not x["valide"]), None)
    return {
        "modules": liste, "total": nb, "valides": valides,
        "pct": int(100 * valides / nb) if nb else 0,
        "complet": nb > 0 and valides == nb,
        "score_moyen": int(sum(scores) / len(scores)) if scores else 0,
        "prochain": prochain["m"]["id"] if prochain else None,
        "a_soft": any(x["m"]["phase"] == "soft" for x in liste),
        "certificat": certificat,
    }


def noter(module, form):
    """(pourcentage, [{'ok': bool, 'explication': str}...]) pour les réponses d'un formulaire (champs q0, q1...)."""
    detail, bonnes = [], 0
    for i, q in enumerate(module["quiz"]):
        try:
            choix = int(form.get(f"q{i}", ""))
        except ValueError:
            choix = -1
        ok = choix == q["reponse"]
        bonnes += ok
        detail.append({"ok": ok, "choix": choix, "explication": q.get("explication", "")})
    return int(100 * bonnes / len(module["quiz"])), detail


def verifier():
    """Rapport lisible sur le contenu de data/formations.json."""
    try:
        brut = json.loads(FICHIER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [f"ERREUR : impossible de lire {FICHIER} ({e})"]
    lignes, ids = [], set()

    def tester(m, contexte):
        problemes = []
        if not m.get("id"):
            problemes.append("id manquant")
        elif m["id"] in ids:
            problemes.append(f"id en double ({m['id']})")
        ids.add(m.get("id"))
        if not youtube_id(m.get("video")):
            problemes.append("vidéo absente ou lien YouTube invalide -> module caché")
        if len(_quiz_valide(m.get("quiz"))) != len(m.get("quiz") or []):
            problemes.append("question invalide (options / reponse)")
        if not _quiz_valide(m.get("quiz")):
            problemes.append("aucune question valide -> module caché")
        lignes.append(f"  [{'OK' if not problemes else '!!'}] {contexte} / {m.get('titre', '?')}"
                      + (" : " + " ; ".join(problemes) if problemes else ""))

    for d in brut.get("domaines", []):
        lignes.append(f"Domaine « {d.get('titre')} »")
        for m in d.get("modules", []):
            tester(m, d.get("id"))
    lignes.append("Soft skills (communs)")
    for m in brut.get("softskills", []):
        tester(m, "soft")
    return lignes


if __name__ == "__main__":
    print("\n".join(verifier()))
    cat = charger()
    print(f"\nVisible pour les utilisateurs : {len(cat['domaines'])} domaine(s), "
          f"{sum(len(d['modules']) for d in cat['domaines'])} module(s) technique(s), {len(cat['softskills'])} module(s) soft skills.")
    sys.exit(0)
