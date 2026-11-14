"""
apply_offres_actuelles.py
-------------------------
Ajoute au projet la page « Offres actuelles » (bouton qui récupère les nouvelles offres informatique :
IA, cybersécurité, développement, data, réseaux...).

Utilisation : copie ce fichier dans le dossier du projet (celui qui contient app_web.py), puis :
    python apply_offres_actuelles.py

- Les fichiers modifiés sont sauvegardés en *.bak_offres.
- Rien n'est modifié si une des modifications ne peut pas être appliquée.
- Tu peux le relancer sans risque : il détecte ce qui est déjà fait.
"""
import re
import shutil
import sys
from pathlib import Path

NEW_FILES = {'live_offres.py': '"""\nlive_offres.py\n--------------\n« Offres actuelles » : récupère à la demande les offres d\'emploi INFORMATIQUE récentes\n(IA, cybersécurité, développement, data, réseaux/systèmes...) sur Rekrute, les classe par catégorie\net les enregistre dans la base (db.live_*), séparément du CSV des offres de départ.\n\nUtilisé par app_web.py (/offres-actuelles et le bouton « Actualiser »).\n\nPour ajouter une autre source plus tard : écrire une fonction qui retourne une liste de dicts\n(mêmes clés que parse_rekrute) et l\'ajouter dans SOURCES.\n"""\n\nimport re\nimport unicodedata\nfrom concurrent.futures import ThreadPoolExecutor\nfrom datetime import date, datetime, timedelta, timezone\nfrom urllib.parse import urljoin\n\nimport requests\nfrom bs4 import BeautifulSoup\n\nBASE_URL = "https://www.rekrute.com"\nSEARCH_URL = BASE_URL + "/fr/offres.html"\n# Fonctions Rekrute : 13 = Informatique / Electronique, 23 = Télécom / Réseaux, 19 = Internet / Multimédia\nFUNCTION_IDS = (13, 23, 19)\nHEADERS = {\n    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "\n                  "Chrome/124.0 Safari/537.36",\n    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",\n}\nTIMEOUT = 8                    # secondes par requête (3 requêtes en parallèle)\nCOOLDOWN_SECONDS = 15 * 60     # une actualisation toutes les 15 min au maximum (pour tous les utilisateurs)\nGARDER_JOURS = 90              # les offres publiées il y a plus de 90 jours sont supprimées\n\nCATEGORIES = {\n    "ia": "Intelligence artificielle",\n    "cyber": "Cybersécurité",\n    "dev": "Développement",\n    "data": "Data & BI",\n    "infra": "Réseaux, systèmes & cloud",\n    "autre": "Informatique (autre)",\n}\n\n# Ordre = priorité (une offre « Data & IA » est classée IA, « Développeur Data » est classée Data...)\n_MOTS = [\n    ("cyber", r"cyber|securite (informatique|des (systemes|si|donnees)|reseau|applicative|operationnelle)"\n              r"|\\bsoc\\b|pentest|\\brssi\\b|\\bssi\\b|\\bsiem\\b|infosec|forensic|vulnerabilit|\\biam\\b"),\n    ("ia", r"\\bia\\b|\\bai\\b|intelligence artificielle|machine learning|deep learning|\\bml\\b|\\bnlp\\b|\\bllm\\b"\n           r"|genai|ia generative|computer vision|vision par ordinateur|data scientist|mlops"),\n    ("data", r"\\bdata\\b|donnees|\\bbi\\b|power ?bi|big data|\\bsql\\b|\\betl\\b|dataviz|tableau|business intelligence"\n             r"|analytics|\\bdba\\b|decisionnel|statisticien"),\n    ("dev", r"developp|developer|\\bdev\\b|full ?stack|front ?end|back ?end|\\bjava\\b|python|\\.net|\\bphp\\b|react"\n            r"|angular|node\\.?js|laravel|symfony|mobile|android|\\bios\\b|flutter|ingenieur (logiciel|etudes)"\n            r"|programmeur|webmaster|integrateur|software|\\babap\\b|salesforce|\\bapi\\b|\\bweb\\b|test(eur)? logiciel"),\n    ("infra", r"reseau|systeme|admin|cloud|devops|infrastructure|help ?desk|service desk|support|technicien"\n              r"|exploitation|linux|windows|azure|\\baws\\b|\\bgcp\\b|kubernetes|docker|telecom|voip|ccna|cisco|\\bsre\\b"),\n]\n_MOTS = [(cat, re.compile(rx)) for cat, rx in _MOTS]\n\n_ID_RE = re.compile(r"/offre-emploi-.*?-(\\d+)\\.html")\n_PUB_RE = re.compile(r"Publication\\s*:\\s*du\\s*(\\d{2}/\\d{2}/\\d{4})\\s*au\\s*(\\d{2}/\\d{2}/\\d{4})", re.I)\n_CONTRAT_RE = re.compile(r"Type de contrat propos[ée]\\s*:\\s*(.+?)\\s*-\\s*T[ée]l[ée]travail\\s*:\\s*(\\w+)", re.I)\n_EXP_RE = re.compile(r"Exp[ée]rience requise\\s*:\\s*(.+?)\\s*Niveau d.[ée]tude", re.I)\n\n\n# ------------------------------------------------------------ classification ----\n\ndef _norm(s):\n    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()\n    return s.lower()\n\n\ndef classer(titre, description=""):\n    """Catégorie principale d\'une offre : on regarde d\'abord le TITRE, puis la description."""\n    for texte in (_norm(titre), _norm(description)):\n        for cat, rx in _MOTS:\n            if rx.search(texte):\n                return cat\n    return "autre"\n\n\n# ------------------------------------------------------------------ Rekrute ----\n\ndef _iso(jjmmaaaa):\n    try:\n        return datetime.strptime(jjmmaaaa, "%d/%m/%Y").date().isoformat()\n    except (TypeError, ValueError):\n        return None\n\n\ndef parse_rekrute(html):\n    """Transforme une page de résultats Rekrute en liste d\'offres (dicts)."""\n    soup = BeautifulSoup(html, "html.parser")\n    liens = [a for a in soup.select("h2 a[href]") if _ID_RE.search(a["href"])]\n    if not liens:     # plan B si la structure change : tous les liens d\'offres qui ressemblent à « Titre | Ville »\n        liens = [a for a in soup.select("a[href]") if _ID_RE.search(a["href"]) and "|" in a.get_text()]\n    offres, vus = [], set()\n    for a in liens:\n        rid = _ID_RE.search(a["href"]).group(1)\n        if rid in vus:\n            continue\n        vus.add(rid)\n\n        texte = a.get_text(" ", strip=True)\n        morceaux = re.split(r"\\s*\\|\\s*", texte)\n        titre = " | ".join(morceaux[:-1]) if len(morceaux) > 1 else texte\n        ville = re.sub(r"\\s*\\(.*?\\)\\s*$", "", morceaux[-1]).strip() if len(morceaux) > 1 else ""\n\n        bloc = a.find_parent("li") or a.find_parent(["article", "div"]) or a.parent\n        plat = bloc.get_text(" ", strip=True)\n        lignes = [l for l in bloc.get_text("\\n", strip=True).split("\\n") if l]\n\n        # Entreprise : alt/title du logo (les offres « confidentielles » ont un logo spécial)\n        entreprise = ""\n        img = bloc.find("img")\n        if img is not None:\n            if "confidentiel" in (img.get("src") or "").lower():\n                entreprise = "Confidentiel"\n            else:\n                entreprise = (img.get("title") or img.get("alt") or "").strip()\n\n        # Description : la ligne longue juste avant « Publication : du ... au ... »\n        description = ""\n        for i, l in enumerate(lignes):\n            if l.lower().startswith("publication"):\n                for prev in reversed(lignes[:i]):\n                    if len(prev) >= 40:\n                        description = prev\n                        break\n                break\n\n        pub = _PUB_RE.search(plat)\n        contrat = _CONTRAT_RE.search(plat)\n        exp = _EXP_RE.search(plat)\n        offres.append({\n            "id": f"rekrute-{rid}",\n            "source": "Rekrute",\n            "titre": titre,\n            "entreprise": entreprise,\n            "ville": ville or "Non précisé",\n            "description": description,\n            "date_publication": _iso(pub.group(1)) if pub else None,\n            "date_fin": _iso(pub.group(2)) if pub else None,\n            "lien": urljoin(BASE_URL, a["href"]).split("#")[0].split("?")[0],\n            "contrat": contrat.group(1).strip() if contrat else "",\n            "teletravail": contrat.group(2).strip() if contrat else "",\n            "experience": exp.group(1).strip() if exp else "",\n            "categorie": classer(titre, description),\n        })\n    return offres\n\n\ndef _page_rekrute(function_id):\n    # s=3 -> 50 offres par page, o=1 -> les plus récentes d\'abord, p=1 -> première page\n    r = requests.get(SEARCH_URL, headers=HEADERS, timeout=TIMEOUT,\n                     params={"s": 3, "p": 1, "o": 1, "positionId[0]": function_id})\n    r.raise_for_status()\n    return parse_rekrute(r.text)\n\n\ndef fetch_rekrute():\n    """(offres, erreurs) : les 3 fonctions IT sont chargées en parallèle, puis dédoublonnées."""\n    offres, erreurs = {}, []\n    with ThreadPoolExecutor(max_workers=len(FUNCTION_IDS)) as ex:\n        futures = {ex.submit(_page_rekrute, fid): fid for fid in FUNCTION_IDS}\n        for fut, fid in futures.items():\n            try:\n                for o in fut.result():\n                    offres.setdefault(o["id"], o)\n            except Exception as e:                       # réseau, blocage, structure modifiée...\n                erreurs.append(f"Rekrute (fonction {fid}) : {type(e).__name__}: {e}")\n    return list(offres.values()), erreurs\n\n\nSOURCES = (fetch_rekrute,)\n\n\n# ------------------------------------------------------------- actualisation ----\n\ndef _maintenant():\n    return datetime.now(timezone.utc)\n\n\ndef refresh(db, force=False):\n    """\n    Récupère les nouvelles offres et les enregistre.\n    Retourne {"status": "ok" | "cooldown" | "error", "new": n, "total": n, "wait": secondes, "errors": [...]}.\n    """\n    now = _maintenant()\n    last = db.live_last_refresh()\n    if last and not force:\n        try:\n            depuis = (now - datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds()\n        except ValueError:\n            depuis = COOLDOWN_SECONDS\n        if depuis < COOLDOWN_SECONDS:\n            return {"status": "cooldown", "wait": int(COOLDOWN_SECONDS - depuis), "new": 0, "total": 0, "errors": []}\n\n    offres, erreurs = [], []\n    for source in SOURCES:\n        o, e = source()\n        offres += o\n        erreurs += e\n    if not offres:\n        return {"status": "error", "new": 0, "total": 0, "errors": erreurs}\n\n    existants = db.live_ids()\n    nouvelles = sum(1 for o in offres if o["id"] not in existants)\n    db.live_put_many(offres, now.isoformat())\n    db.live_purge((date.today() - timedelta(days=GARDER_JOURS)).isoformat())\n    return {"status": "ok", "new": nouvelles, "total": len(offres), "errors": erreurs}\n', 'templates/offres_actuelles.html': '{% extends "base.html" %}\n{% block title %}{{ t(\'live_title\') }}{% endblock %}\n{% block content %}\n<section class="hero">\n    <span class="eyebrow">{{ t(\'live_eyebrow\') }}</span>\n    <h1>{{ t(\'live_title\') }}</h1>\n    <p class="lead">{{ t(\'live_lead\') }}</p>\n    <div class="live-bar">\n        <form method="post" action="{{ url_for(\'offres_actuelles_actualiser\') }}">{{ csrf_input() }}\n            <button class="btn btn-primary" type="submit"><i class="fa-solid fa-rotate"></i> {{ t(\'live_refresh\') }}</button>\n        </form>\n        <span class="live-last">{% if derniere %}{{ t(\'live_last\', d=derniere) }}{% else %}{{ t(\'live_never\') }}{% endif %}</span>\n    </div>\n    {% if not vide %}\n    <form method="get" action="{{ url_for(\'page_offres_actuelles\') }}" class="search-bar">\n        <label class="search-field"><i class="fa-solid fa-magnifying-glass"></i><input type="text" name="q" value="{{ q }}" placeholder="{{ t(\'offers_search_ph\') }}"></label>\n        <label class="select-field"><i class="fa-solid fa-location-dot"></i><select name="ville"><option value="">{{ t(\'all_cities\') }}</option>{% for v in villes %}<option value="{{ v }}" {{ \'selected\' if v == ville }}>{{ v }}</option>{% endfor %}</select></label>\n        {% if categorie %}<input type="hidden" name="categorie" value="{{ categorie }}">{% endif %}\n        <button type="submit" class="btn btn-primary">{{ t(\'search\') }}</button>\n    </form>\n    {% endif %}\n</section>\n\n{% if vide %}\n<p class="empty">{{ t(\'live_empty\') }}</p>\n{% else %}\n<div class="live-cats">\n    <a class="live-cat {{ \'active\' if not categorie }}" href="{{ url_for(\'page_offres_actuelles\', q=q, ville=ville) }}">{{ t(\'live_all\') }} <b>{{ nb_total }}</b></a>\n    {% for key, label in categories.items() %}{% if compteurs.get(key) %}\n    <a class="live-cat {{ \'active\' if categorie == key }}" href="{{ url_for(\'page_offres_actuelles\', q=q, ville=ville, categorie=key) }}">{{ t(\'cat_\' ~ key) }} <b>{{ compteurs[key] }}</b></a>\n    {% endif %}{% endfor %}\n</div>\n<p class="results-count">{{ t(\'offers_found\', n=total) }}</p>\n<div class="cards">\n    {% for o in offres %}\n    {% set next_url = request.full_path.rstrip(\'?\') ~ \'#card-\' ~ o.id %}\n    <article class="card job-card" id="card-{{ o.id }}">\n        <div class="job-head">\n            <span class="job-logo">{{ ((o.entreprise or o.source or \'?\')[:1])|upper }}</span>\n            <div class="job-title-wrap">\n                <a class="card-title" dir="auto" href="{{ o.lien }}" target="_blank" rel="noopener">{{ o.titre }}</a>\n                <div class="job-company" dir="auto">{{ o.entreprise or o.source }}</div>\n            </div>\n            {% if applied.get(o.lien) %}<span class="badge badge-ok"><i class="fa-solid fa-check"></i> {{ t(\'applied\') }}</span>{% endif %}\n        </div>\n        <div class="tags">\n            <span class="tag tag-cat"><i class="fa-solid fa-microchip"></i> {{ t(\'cat_\' ~ o.categorie) }}</span>\n            <span class="tag"><i class="fa-solid fa-location-dot"></i> {{ o.ville }}</span>\n            {% if o.contrat %}<span class="tag"><i class="fa-solid fa-file-contract"></i> {{ o.contrat }}</span>{% endif %}\n            {% if o.age is not none %}<span class="tag"><i class="fa-regular fa-calendar"></i> {{ t(\'live_today\') if o.age <= 0 else t(\'live_ago\', n=o.age) }}</span>{% endif %}\n            <span class="tag"><i class="fa-solid fa-globe"></i> {{ o.source }}</span>\n        </div>\n        <p class="excerpt" dir="auto">{{ (o.description or \'\')[:220] }}{{ \'…\' if (o.description or \'\')|length > 220 }}</p>\n        <div class="actions">\n            <a class="btn btn-primary btn-sm" href="{{ o.lien }}" target="_blank" rel="noopener"><i class="fa-solid fa-arrow-up-right-from-square"></i> {{ t(\'apply\') }}</a>\n            <a class="btn btn-mail btn-sm" href="{{ gmail_offre(o) }}" target="_blank" rel="noopener" title="{{ t(\'contact_email_hint\') }}"><i class="fa-regular fa-envelope"></i> {{ t(\'contact_email\') }}</a>\n            <form method="post" action="{{ url_for(\'toggle\') }}" class="inline-form">{{ csrf_input() }}\n                <input type="hidden" name="key" value="{{ o.lien }}"><input type="hidden" name="next" value="{{ next_url }}">\n                {% if applied.get(o.lien) %}<button class="btn btn-success btn-sm" title="{{ t(\'click_to_remove\') }}"><i class="fa-solid fa-check"></i> {{ t(\'applied\') }}</button>\n                {% else %}<button class="btn btn-outline btn-sm"><i class="fa-regular fa-square-check"></i> {{ t(\'mark_applied\') }}</button>{% endif %}\n            </form>\n        </div>\n    </article>\n    {% else %}\n    <p class="empty">{{ t(\'offers_none\') }}</p>\n    {% endfor %}\n</div>\n{% endif %}\n{% endblock %}\n'}
ROUTES = '@app.route("/offres-actuelles")\ndef page_offres_actuelles():\n    q = request.args.get("q", "").strip().lower()\n    ville = request.args.get("ville", "").strip()\n    categorie = request.args.get("categorie", "").strip()\n    toutes = db.live_all()\n\n    villes = sorted({o.get("ville") for o in toutes if o.get("ville")})\n    base = toutes\n    if q:\n        base = [o for o in base if q in str(o.get("titre", "")).lower() or q in str(o.get("description", "")).lower()\n                or q in str(o.get("entreprise", "")).lower()]\n    if ville:\n        base = [o for o in base if o.get("ville") == ville]\n    compteurs = {}\n    for o in base:\n        compteurs[o.get("categorie", "autre")] = compteurs.get(o.get("categorie", "autre"), 0) + 1\n    offres = [o for o in base if o.get("categorie", "autre") == categorie] if categorie in live_offres.CATEGORIES else base\n\n    aujourd_hui = date.today()\n    for o in offres:\n        try:\n            o["age"] = (aujourd_hui - date.fromisoformat(o["date_publication"])).days\n        except (TypeError, ValueError, KeyError):\n            o["age"] = None\n    return render_template(\n        "offres_actuelles.html", offres=offres[:200], total=len(offres), q=q, ville=ville, villes=villes,\n        categorie=categorie, categories=live_offres.CATEGORIES, compteurs=compteurs, nb_total=len(base),\n        derniere=(db.live_last_refresh() or "")[:16].replace("T", " "), vide=not toutes,\n    )\n\n\n@app.route("/offres-actuelles/actualiser", methods=["POST"])\ndef offres_actuelles_actualiser():\n    try:\n        res = live_offres.refresh(db)\n    except Exception:\n        app.logger.exception("Actualisation des offres actuelles")\n        res = {"status": "error", "errors": []}\n    if res["status"] == "ok":\n        flash(t("live_updated", n=res["new"], total=res["total"]), "success")\n    elif res["status"] == "cooldown":\n        flash(t("live_cooldown", min=max(1, -(-res["wait"] // 60))), "info")\n    else:\n        flash(t("live_error"), "danger")\n        for e in res.get("errors", []):\n            app.logger.warning("offres actuelles : %s", e)\n    return redirect(url_for("page_offres_actuelles"))\n\n\n'
STORE_LOCAL = '    # -- offres actuelles : {"offres": {id: offre}, "last_refresh": iso}\n    def live_put_many(self, offres, fetched_at):\n        data = self._read(self.live_f) or {}\n        stock = data.get("offres", {})\n        for o in offres:\n            stock[o["id"]] = o\n        self._write(self.live_f, {"offres": stock, "last_refresh": fetched_at})\n\n    def live_all(self):\n        stock = (self._read(self.live_f) or {}).get("offres", {})\n        return sorted(stock.values(), key=lambda o: o.get("date_publication") or "", reverse=True)\n\n    def live_ids(self):\n        return set((self._read(self.live_f) or {}).get("offres", {}))\n\n    def live_last_refresh(self):\n        return (self._read(self.live_f) or {}).get("last_refresh")\n\n    def live_purge(self, avant_iso):\n        data = self._read(self.live_f) or {}\n        stock = data.get("offres", {})\n        garde = {k: o for k, o in stock.items() if (o.get("date_publication") or "9999") >= avant_iso}\n        if len(garde) != len(stock):\n            data["offres"] = garde\n            self._write(self.live_f, data)\n\n'
STORE_SUPA = '    # -- offres actuelles (table app_offres_live)\n    def live_put_many(self, offres, fetched_at):\n        rows = [{"offre_id": o["id"], "published": o.get("date_publication"), "fetched_at": fetched_at, "data": o}\n                for o in offres]\n        self._rest("POST", "app_offres_live", {"on_conflict": "offre_id"}, rows,\n                   prefer="resolution=merge-duplicates,return=minimal")\n\n    def live_all(self):\n        rows = self._rest("GET", "app_offres_live",\n                          {"select": "data", "order": "published.desc.nullslast", "limit": "1000"}).json()\n        return [r["data"] for r in rows]\n\n    def live_ids(self):\n        rows = self._rest("GET", "app_offres_live", {"select": "offre_id", "limit": "5000"}).json()\n        return {r["offre_id"] for r in rows}\n\n    def live_last_refresh(self):\n        rows = self._rest("GET", "app_offres_live",\n                          {"select": "fetched_at", "order": "fetched_at.desc", "limit": "1"}).json()\n        return rows[0]["fetched_at"] if rows else None\n\n    def live_purge(self, avant_iso):\n        self._rest("DELETE", "app_offres_live", {"published": f"lt.{avant_iso}"}, prefer="return=minimal")\n\n'
I18N = '    # ---- offres actuelles\n    "nav_live": ("Offres actuelles", "Current offers", "العروض الحالية"),\n    "live_eyebrow": ("EN DIRECT", "LIVE", "مباشر"),\n    "live_title": ("Offres actuelles", "Current offers", "العروض الحالية"),\n    "live_lead": ("Les offres informatique les plus récentes : IA, cybersécurité, développement, data, réseaux. Clique sur « Actualiser » pour récupérer les nouvelles offres.",\n                  "The latest IT job offers: AI, cybersecurity, development, data, networks. Click \\"Refresh\\" to fetch new offers.",\n                  "أحدث عروض الشغل في المعلوميات: الذكاء الاصطناعي، الأمن السيبراني، التطوير، البيانات، الشبكات. اضغط على «تحديث» لجلب عروض جديدة."),\n    "live_refresh": ("Actualiser les offres", "Refresh offers", "تحديث العروض"),\n    "live_last": ("Dernière actualisation : {d} (UTC)", "Last refresh: {d} (UTC)", "آخر تحديث: {d} (UTC)"),\n    "live_never": ("Jamais actualisé", "Never refreshed", "لم يتم التحديث بعد"),\n    "live_empty": ("Aucune offre pour le moment. Clique sur « Actualiser les offres » pour les récupérer.",\n                   "No offers yet. Click \\"Refresh offers\\" to fetch them.",\n                   "لا توجد عروض حالياً. اضغط على «تحديث العروض» لجلبها."),\n    "live_all": ("Toutes", "All", "الكل"),\n    "live_today": ("Aujourd\'hui", "Today", "اليوم"),\n    "live_ago": ("Il y a {n} j", "{n} d ago", "منذ {n} يوم"),\n    "live_updated": ("{n} nouvelle(s) offre(s) ajoutée(s), {total} offres vérifiées.", "{n} new offer(s) added, {total} offers checked.", "تمت إضافة {n} عرض جديد، تم فحص {total} عرض."),\n    "live_cooldown": ("Les offres viennent d\'être actualisées. Réessaie dans {min} min.", "Offers were just refreshed. Try again in {min} min.", "تم تحديث العروض للتو. أعد المحاولة بعد {min} دقيقة."),\n    "live_error": ("Impossible de récupérer les offres pour le moment. Réessaie plus tard.", "Could not fetch offers right now. Please try again later.", "تعذر جلب العروض حالياً. أعد المحاولة لاحقاً."),\n    "cat_ia": ("Intelligence artificielle", "Artificial intelligence", "الذكاء الاصطناعي"),\n    "cat_cyber": ("Cybersécurité", "Cybersecurity", "الأمن السيبراني"),\n    "cat_dev": ("Développement", "Development", "التطوير"),\n    "cat_data": ("Data & BI", "Data & BI", "البيانات"),\n    "cat_infra": ("Réseaux, systèmes & cloud", "Networks, systems & cloud", "الشبكات والأنظمة والسحابة"),\n    "cat_autre": ("Informatique (autre)", "IT (other)", "معلوميات (أخرى)"),\n\n'
CSS = '/* ---- page Offres actuelles */\n.live-bar { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-top: 18px; }\n.live-bar form { margin: 0; }\n.live-last { color: var(--muted); font-size: .9rem; }\n.live-cats { display: flex; gap: 8px; flex-wrap: wrap; margin: 6px 0 14px; }\n.live-cat { display: inline-flex; align-items: center; gap: 8px; padding: 7px 14px; border-radius: 999px; background: #fff; border: 1px solid var(--border); color: var(--ink); text-decoration: none; font-weight: 600; font-size: .86rem; }\n.live-cat b { background: #eef2ff; color: var(--primary); border-radius: 999px; padding: 1px 8px; font-size: .76rem; }\n.live-cat:hover { border-color: var(--primary); }\n.live-cat.active { background: var(--primary); border-color: var(--primary); color: #fff; }\n.live-cat.active b { background: #ffffff33; color: #fff; }\n.tag-cat { background: #eef2ff; color: var(--primary); font-weight: 700; }\n'
SQL = '-- Offres actuelles (page « Offres actuelles » : offres IT récupérées à la demande)\ncreate table if not exists app_offres_live (\n    offre_id   text primary key,\n    published  date,\n    fetched_at timestamptz not null default now(),\n    data       jsonb not null\n);\ncreate index if not exists app_offres_live_published_idx on app_offres_live (published desc);\nalter table app_offres_live  enable row level security;\n'
NAV = '<a href="{{ url_for(\'page_offres_actuelles\') }}" class="{{ \'active\' if request.endpoint == \'page_offres_actuelles\' }}"><i class="fa-solid fa-bolt"></i><span>{{ t(\'nav_live\') }}</span></a>'

ROOT = Path.cwd()
erreurs, ecritures, deja = [], {}, []


def lire(chemin):
    p = ROOT / chemin
    if not p.exists():
        erreurs.append(f"fichier introuvable : {chemin}")
        return None
    return p.read_text(encoding="utf-8")


def avant(texte, ancres, bloc, nom):
    """Insère `bloc` juste avant la première ancre trouvée (liste d'ancres de secours)."""
    for a in ancres:
        i = texte.find(a)
        if i != -1:
            debut = texte.rfind("\n", 0, i) + 1 if a.strip() == a else i
            return texte[:debut] + bloc + texte[debut:]
    erreurs.append(f"{nom} : endroit d'insertion introuvable")
    return texte


if not (ROOT / "app_web.py").exists():
    sys.exit("ERREUR : lance ce script depuis le dossier du projet (celui qui contient app_web.py).")

# 1) nouveaux fichiers
for chemin, contenu in NEW_FILES.items():
    p = ROOT / chemin
    if p.exists() and p.read_text(encoding="utf-8") == contenu:
        deja.append(chemin)
    else:
        ecritures[chemin] = contenu

# 2) app_web.py : import + routes
s = lire("app_web.py")
if s is not None:
    if "live_offres" in s:
        deja.append("app_web.py")
    else:
        s = avant(s, ["import mailer", "import i18n"], "import live_offres\n", "app_web.py (import)")
        m = re.search(r"^from datetime import ([^\n]+)$", s, re.M)
        if m:
            noms = [n.strip() for n in m.group(1).split(",")]
            if "date" not in noms:
                s = s.replace(m.group(0), "from datetime import " + ", ".join(noms + ["date"]), 1)
        else:
            s = avant(s, ["import hashlib", "import json"], "from datetime import date\n", "app_web.py (date)")
        s = avant(s, ['@app.route("/a-propos")', '@app.route("/profil", methods=["GET", "POST"])',
                      'if __name__ == "__main__":'], ROUTES, "app_web.py (routes)")
        ecritures["app_web.py"] = s

# 3) store.py
s = lire("store.py")
if s is not None:
    if "live_put_many" in s:
        deja.append("store.py")
    else:
        m = re.search(r"\n([ \t]+)self\.cands_f = [^\n]+\n", s)
        if m:
            s = s.replace(m.group(0), m.group(0) + m.group(1) + 'self.live_f = self.base / "offres_actuelles.json"\n', 1)
        else:
            erreurs.append("store.py : self.cands_f introuvable")
        s = avant(s, ["    # -- photos d'identité (bucket privé)"], STORE_SUPA, "store.py (Supabase)")
        s = avant(s, ["    # -- photos d'identité\n    def kyc_put"], STORE_LOCAL, "store.py (local)")
        ecritures["store.py"] = s

# 4) i18n.py
s = lire("i18n.py")
if s is not None:
    if '"nav_live"' in s:
        deja.append("i18n.py")
    else:
        s = avant(s, ["    # ---- admin\n"], I18N, "i18n.py")
        ecritures["i18n.py"] = s

# 5) base.html : lien dans la barre latérale
s = lire("templates/base.html")
if s is not None:
    if "page_offres_actuelles" in s:
        deja.append("templates/base.html")
    else:
        m = re.search(r"^([ \t]*)<a href=\"\{\{ url_for\('page_profil'\) \}\}\"", s, re.M)
        if m:
            s = s[:m.start()] + m.group(1) + NAV + "\n" + s[m.start():]
            ecritures["templates/base.html"] = s
        else:
            erreurs.append("templates/base.html : lien « page_profil » introuvable (ajoute le lien à la main)")

# 6) CSS
css_path = next((c for c in ("public/static/style.css", "static/style.css") if (ROOT / c).exists()), None)
if css_path is None:
    erreurs.append("style.css introuvable")
else:
    s = lire(css_path)
    if "page Offres actuelles" in s:
        deja.append(css_path)
    else:
        ecritures[css_path] = s.rstrip("\n") + "\n\n" + CSS

# 7) supabase_schema.sql + .gitignore (facultatifs)
if (ROOT / "supabase_schema.sql").exists():
    s = (ROOT / "supabase_schema.sql").read_text(encoding="utf-8")
    if "app_offres_live" not in s:
        ecritures["supabase_schema.sql"] = s.rstrip("\n") + "\n\n" + SQL
if (ROOT / ".gitignore").exists():
    s = (ROOT / ".gitignore").read_text(encoding="utf-8")
    if "offres_actuelles.json" not in s:
        ecritures[".gitignore"] = s.rstrip("\n") + "\ndata/offres_actuelles.json\n"

if erreurs:
    print("RIEN n'a été modifié. Problèmes :")
    for e in erreurs:
        print("  -", e)
    sys.exit(1)

for chemin, contenu in ecritures.items():
    p = ROOT / chemin
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        shutil.copy2(p, p.with_name(p.name + ".bak_offres"))
    p.write_text(contenu, encoding="utf-8")

print("Fichiers modifiés / créés :", ", ".join(ecritures) or "aucun")
if deja:
    print("Déjà en place :", ", ".join(deja))
print()
print("ETAPE SUIVANTE (si tu utilises Supabase) : dans Supabase > SQL Editor, exécute :")
print("-" * 60)
print(SQL)
print("-" * 60)
print("Puis relance l'application : flask --app app_web run --debug  et ouvre /offres-actuelles")
