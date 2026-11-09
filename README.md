# projet_ia_jobs : Offres IA & Data au Maroc

Plateforme web (Flask) qui rassemble les offres d'emploi IA / Data au Maroc et les entreprises IA de Marrakech.
Projet réalisé à l'OFPPT Marrakech. Interface disponible en **français, anglais et arabe**.

## Fonctionnalités

- **Offres d'emploi** : recherche, filtres (ville, source, mot-clé), page de détail, commentaires.
- **Entreprises IA de Marrakech** : fiches, notes, bouton « Contacter par email » (ouvre Gmail).
- **Tableau de bord** : graphiques (villes, sources, dates, cartes à bulles...).
- **Compte utilisateur** : inscription, connexion (email + Google), vérification de l'email par code, profil, vérification d'identité (administrateur).
- **Générateur de CV** (PDF) et **évaluation de CV** par IA.
- **Chatbot** hors-ligne (Darija / français / anglais) sur les offres et les entreprises.
- **API REST** : chaque utilisateur peut générer une **clé API** depuis son profil et récupérer les offres en JSON.
- Page **À propos de nous**.

---

## 1. Prérequis

- **Python 3.10 ou plus** (testé avec 3.12) : https://www.python.org/downloads/
  Sous Windows, coche « Add Python to PATH » pendant l'installation.
- **Git** (seulement si tu clones depuis GitHub) : https://git-scm.com/downloads
- Un éditeur de code (VS Code conseillé).

## 2. Installation

Ouvre un terminal dans le dossier du projet (celui qui contient `app_web.py`).

**Windows (PowerShell)**
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

**macOS / Linux**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

> Si PowerShell refuse d'activer le venv (« l'exécution de scripts est désactivée »), lance une fois :
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, puis réessaie.

Après l'installation, le terminal affiche `(venv)` au début de la ligne. Il faut **réactiver le venv**
(`venv\Scripts\activate`) à chaque nouveau terminal, mais `pip install` ne se refait qu'une seule fois.

## 3. Configuration (`.env`)

Ouvre le fichier `.env` créé à l'étape précédente.

### Minimum pour démarrer en local

Une seule variable est nécessaire :

```env
FLASK_SECRET_KEY=une-longue-phrase-secrete-aleatoire
```

Sans Supabase, l'application enregistre les comptes et commentaires dans des fichiers du dossier `data/`.
C'est parfait pour le développement local.

### Variables optionnelles

| Variable | Rôle | Si elle est absente |
|---|---|---|
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | Base de données Supabase (obligatoire sur Vercel) | Fichiers locaux dans `data/` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Envoi du code de vérification par email | Le code s'affiche **dans le terminal** |
| `ADMIN_EMAILS` | Emails (séparés par des virgules) autorisés à valider les profils | Pas d'administrateur |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Connexion avec Google | Bouton Google désactivé |
| `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` | Captcha Cloudflare | Captcha désactivé |
| `OMNIROUTE_API_KEY`, `OMNIROUTE_BASE_URL`, `OMNIROUTE_MODEL` | IA pour l'évaluation de CV | L'évaluation de CV par IA est indisponible |
| `FLASK_DEBUG` | `1` = mode développement | `0` |

> **Gmail (SMTP)** : active la validation en 2 étapes, crée un « mot de passe d'application » sur
> https://myaccount.google.com/apppasswords et mets-le dans `SMTP_PASSWORD`.

> **Ne mets jamais `.env` sur GitHub.** Il est déjà dans `.gitignore`.

## 4. Lancer l'application

```powershell
flask --app app_web run --debug
```
ou
```powershell
python app_web.py
```
(avec `python app_web.py`, le mode debug n'est actif que si `FLASK_DEBUG=1` est dans `.env`.)

Puis ouvre **http://127.0.0.1:5000** dans le navigateur.

> `run` seul n'est pas une commande : utilise la commande complète ci-dessus.

## 5. Premiers pas

1. Va sur `/signup` et crée un compte.
2. **Profil → Vérifier l'email.** Sans SMTP, le code à 6 chiffres s'affiche **dans le terminal** où Flask tourne.
3. Pour être administrateur : mets ton email dans `ADMIN_EMAILS` (dans `.env`), relance l'application, vérifie ton email. La page « Vérifications » apparaît.

## 6. Utiliser l'API

### Générer une clé
**Profil → Clé API → Générer ma clé API** (l'email doit être vérifié).
La clé (`ijk_...`) n'est affichée **qu'une seule fois** : copie-la tout de suite.
Regénérer une clé désactive l'ancienne. Tu peux aussi la **révoquer**.

> Seul le hash (SHA-256) de la clé est stocké. Ne publie jamais ta clé (GitHub, JavaScript côté navigateur).

### Appeler l'API

La clé s'envoie dans l'en-tête `X-API-Key` (ou `Authorization: Bearer <clé>`).

```powershell
# Windows PowerShell : utilise curl.exe (curl est un alias d'une autre commande)
curl.exe -H "X-API-Key: ijk_VOTRE_CLE" "http://127.0.0.1:5000/api/v1/offres?q=data&per_page=5"
```

```bash
# macOS / Linux
curl -H "X-API-Key: ijk_VOTRE_CLE" "http://127.0.0.1:5000/api/v1/offres?q=data&per_page=5"
```

```python
import requests

BASE = "http://127.0.0.1:5000"
headers = {"X-API-Key": "ijk_VOTRE_CLE"}
r = requests.get(f"{BASE}/api/v1/offres", headers=headers,
                 params={"q": "data", "ville": "Marrakech", "per_page": 10})
for o in r.json()["offres"]:
    print(o["titre"], "-", o["ville"], "-", o["lien"])
```

### Endpoints

| Méthode | URL | Description |
|---|---|---|
| GET | `/api/v1/offres` | Liste paginée des offres (description tronquée à 300 caractères) |
| GET | `/api/v1/offres/<id>` | Une offre avec sa description complète |

Paramètres de `/api/v1/offres` :

| Paramètre | Rôle |
|---|---|
| `q` | Mot-clé cherché dans le titre et la description |
| `ville` | Ville exacte (ex. `Marrakech`) |
| `source` | Source (ex. `Rekrute`) |
| `page` | Numéro de page (défaut 1) |
| `per_page` | Nombre d'offres par page (défaut 20, maximum 50) |

Réponse :
```json
{
  "total": 129, "page": 1, "per_page": 20, "nb_pages": 7,
  "offres": [
    {"id": 0, "titre": "...", "entreprise": null, "ville": "Casablanca",
     "source": "Rekrute", "mot_cle": "...", "date_publication": "2026-09-25",
     "lien": "https://...", "description": "..."}
  ]
}
```

Codes d'erreur : `401` clé absente, invalide ou révoquée · `404` offre introuvable.

> Il n'y a pas de limitation de débit (rate limiting) pour le moment.

## 7. Les données

Les offres et les entreprises sont dans des fichiers CSV du dossier `data/` :

| Fichier | Contenu |
|---|---|
| `data/emplois_ia_maroc_clean.csv` | Les offres d'emploi |
| `data/entreprises_ia_marrakech_clean.csv` | Les entreprises IA de Marrakech |
| `data/emails_entreprises.csv` | Emails des entreprises (généré par `trouver_emails.py`, optionnel) |

L'`id` d'une offre est son **numéro de ligne** dans le CSV (0, 1, 2...).
Pour mettre à jour les offres, remplace le CSV en gardant les mêmes colonnes (ouvre le fichier actuel comme modèle),
puis relance l'application.

### Trouver les emails des entreprises

Le bouton « Contacter par email » remplit le champ « À » de Gmail uniquement si l'email de l'entreprise est connu.
Pour les récupérer automatiquement depuis les sites web des entreprises :

```powershell
python trouver_emails.py
```

Cela crée `data/emails_entreprises.csv`. Tu peux l'ouvrir et corriger ou ajouter des emails à la main : ils ne sont pas écrasés.
Pour les offres, l'email n'est affiché que s'il est écrit dans la description de l'offre.

## 8. Structure du projet

```
projet_ia_jobs/
├── app_web.py             # application Flask : routes, API, pages
├── index.py               # point d'entrée pour Vercel
├── store.py               # stockage : fichiers locaux ou Supabase
├── graphes.py             # graphiques du tableau de bord
├── chatbot.py             # chatbot hors-ligne
├── cv_generator.py        # génération de CV en PDF
├── mailer.py              # envoi d'emails (SMTP)
├── i18n.py                # traductions FR / EN / AR
├── villes_maroc.py        # coordonnées des villes
├── trouver_emails.py      # script de recherche des emails d'entreprises
├── supabase_schema.sql    # tables Supabase (à exécuter une fois)
├── requirements.txt       # dépendances Python
├── vercel.json            # configuration Vercel
├── .env.example           # modèle de configuration
├── data/                  # fichiers CSV
├── templates/             # pages HTML (Jinja)
└── public/static/         # CSS et JavaScript
```

## 9. Déploiement sur Vercel (avec Supabase)

Vercel ne conserve pas les fichiers écrits par l'application : les comptes, commentaires, clés API et photos sont donc
enregistrés dans **Supabase**. L'application choisit Supabase automatiquement si `SUPABASE_URL` et `SUPABASE_SERVICE_KEY` sont définies.

### a) Supabase
1. Crée un projet sur https://supabase.com
2. **SQL Editor → New query**, colle le contenu de `supabase_schema.sql`, puis **Run**
   (crée les tables, active la sécurité RLS et crée un bucket privé `kyc`).
3. **Project Settings → API Keys** : copie la **Project URL** et la clé **secrète** (`sb_secret_...`).
4. **Storage** : vérifie que le bucket `kyc` est **Private**.

> Si ton projet Supabase existe déjà, relance `supabase_schema.sql` : il utilise `if not exists` et ajoute seulement
> ce qui manque (par exemple la table `app_api_keys` pour les clés API).

### b) GitHub
Envoie le projet sur GitHub **sans** `.env`. Dans `.gitignore`, ajoute aussi les fichiers créés en mode local :
```
data/users.json
data/commentaires.json
data/candidatures.json
data/api_keys.json
data/kyc/
```

### c) Vercel
1. **Add New → Project**, choisis le dépôt GitHub. Framework : **Flask**.
2. **Settings → Environment Variables** : ajoute au minimum `FLASK_SECRET_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
   puis (selon ce que tu utilises) `ADMIN_EMAILS`, `SMTP_*`, `GOOGLE_*`, `TURNSTILE_*`, `OMNIROUTE_*`.
   Colle les valeurs réelles de ton `.env`. Marque les clés secrètes comme **Sensitive**.
3. **Deploy**. Après chaque `git push`, Vercel redéploie automatiquement.
4. Si tu modifies une variable d'environnement, fais un **Redeploy** : l'ancien déploiement ne la voit pas.

### d) Après le premier déploiement
- **Google Sign-In** : ajoute `https://TON-DOMAINE/login/google/callback` dans les « Authorized redirect URIs ».
- **Turnstile** : ajoute ton domaine Vercel dans les « Hostnames ».
- Inscris-toi avec un email de `ADMIN_EMAILS` et vérifie-le pour voir la page « Vérifications ».

### Limites de Vercel
- Taille maximale d'une requête : 4,5 Mo (les photos sont compressées dans le navigateur, un CV est limité à 4 Mo).
- Les offres sont lues depuis le CSV déployé avec le code : pour les mettre à jour, modifie le CSV puis fais un `git push`.

## 10. Dépannage

| Problème | Solution |
|---|---|
| `run : Le terme « run » n'est pas reconnu` | Utilise `flask --app app_web run --debug` ou `python app_web.py` |
| `ModuleNotFoundError` | Le venv n'est pas activé : `venv\Scripts\activate`, puis `pip install -r requirements.txt` |
| `Internal Server Error` en local | Lis la dernière ligne du `Traceback` dans le terminal où Flask tourne : elle donne la cause |
| `500 FUNCTION_INVOCATION_FAILED` sur Vercel | Vercel → **Logs** → lis la dernière ligne du `Traceback`. Souvent : une variable d'environnement manquante, ou un fichier non poussé sur GitHub |
| `AttributeError: module 'graphes' has no attribute ...` | Le `graphes.py` de GitHub ne correspond pas à `app_web.py` : pousse les deux fichiers ensemble |
| API : `401` avec une clé correcte | Tu utilises une ancienne clé (en générer une nouvelle révoque l'ancienne), ou ton script appelle un autre serveur que celui qui tourne |
| `Internal Server Error` en cliquant sur « Générer » (avec Supabase) | La table `app_api_keys` n'existe pas : exécute `supabase_schema.sql` |
| « Contacter par email » : champ « À » vide | L'email de l'entreprise est inconnu : lance `python trouver_emails.py` (voir section 7) |
| Vercel affiche « Needs Attention » sur une variable | Ce n'est pas une erreur : modifie la variable et active **Sensitive** |
| `Pandas4Warning: 'str' is not supported as a fill value` | Simple avertissement, sans effet sur le fonctionnement |
| Le code de vérification n'arrive pas par email | SMTP non configuré : le code est affiché dans le terminal |

## 11. Sécurité

- Ne publie **jamais** `.env`, `SUPABASE_SERVICE_KEY`, les clés SMTP ou les clés API.
- Si une clé a été exposée (capture d'écran, chat, GitHub), **régénère-la** immédiatement.
- Les clés API des utilisateurs sont stockées sous forme de hash SHA-256, jamais en clair.
- La clé Supabase `service_role` / `sb_secret_...` donne tous les droits : uniquement côté serveur.

## 12. Auteur

**Ilyasse**, étudiant en Intelligence Artificielle & Data Analyst à l'OFPPT Marrakech.

- GitHub : https://github.com/ilyassamsaafi2007-code
- Portfolio : https://ilyasseo.site.je/?i=1
- LinkedIn : https://www.linkedin.com/in/amssaafi-ilyasse-38b272385/
