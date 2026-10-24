# """
# graphes.py
# ----------
# Fonctions qui construisent les figures matplotlib/seaborn à partir des
# données nettoyées. Chaque fonction retourne un objet Figure (ne
# sauvegarde rien elle-même) — utilisé par :
#     - visualisation.py (CLI) : sauvegarde chaque figure en PNG
#     - app.py (Dashboard Streamlit) : affiche chaque figure avec st.pyplot
# """

# import matplotlib.pyplot as plt
# import seaborn as sns
# import pandas as pd

# from villes_maroc import get_coords

# sns.set_theme(style="whitegrid")


# def fig_bar_villes(df):
#     fig, ax = plt.subplots(figsize=(9, 5))
#     df["ville"].value_counts().plot(kind="bar", color="#2E86AB", ax=ax)
#     ax.set_title("Nombre d'offres IA par ville")
#     ax.set_xlabel("Ville")
#     ax.set_ylabel("Nombre d'offres")
#     plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
#     fig.tight_layout()
#     return fig


# def fig_pie_sources(df):
#     fig, ax = plt.subplots(figsize=(6, 6))
#     df["source"].value_counts().plot(
#         kind="pie", autopct="%1.1f%%", startangle=90,
#         colors=["#2E86AB", "#F26419", "#6A4C93"], ax=ax
#     )
#     ax.set_title("Répartition des offres par source")
#     ax.set_ylabel("")
#     fig.tight_layout()
#     return fig


# def fig_hist_longueur(df):
#     fig, ax = plt.subplots(figsize=(9, 5))
#     ax.hist(df["longueur_description"].dropna(), bins=25, color="#6A4C93")
#     ax.set_title("Distribution de la longueur des descriptions")
#     ax.set_xlabel("Longueur (nombre de caractères)")
#     ax.set_ylabel("Fréquence")
#     fig.tight_layout()
#     return fig


# def fig_boxplot_longueur(df):
#     fig, ax = plt.subplots(figsize=(10, 5))
#     sns.boxplot(data=df, x="ville", y="longueur_description", ax=ax)
#     ax.set_title("Longueur des descriptions par ville")
#     plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
#     fig.tight_layout()
#     return fig


# def fig_heatmap_ville_source(df):
#     table = pd.crosstab(df["ville"], df["source"])
#     fig, ax = plt.subplots(figsize=(7, 8))
#     sns.heatmap(table, annot=True, fmt="d", cmap="YlGnBu", ax=ax)
#     ax.set_title("Nombre d'offres par ville et par source")
#     fig.tight_layout()
#     return fig


# def fig_scatter_villes(df):
#     df = df.copy()
#     coords = df["ville"].apply(get_coords)
#     df["latitude"] = coords.apply(lambda c: c[0])
#     df["longitude"] = coords.apply(lambda c: c[1])

#     fig, ax = plt.subplots(figsize=(8, 8))
#     for source, sous_df in df.groupby("source"):
#         ax.scatter(sous_df["longitude"], sous_df["latitude"], label=source, alpha=0.6, s=60)
#     ax.set_title("Localisation des offres IA (par ville)")
#     ax.set_xlabel("Longitude")
#     ax.set_ylabel("Latitude")
#     ax.legend(title="Source")
#     fig.tight_layout()
#     return fig


# def fig_bar_categories_entreprises(df_entreprises):
#     fig, ax = plt.subplots(figsize=(9, 5))
#     df_entreprises["categorie"].value_counts().head(15).plot(kind="bar", color="#F26419", ax=ax)
#     ax.set_title("Entreprises IA à Marrakech par catégorie")
#     ax.set_xlabel("Catégorie")
#     ax.set_ylabel("Nombre d'entreprises")
#     plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
#     fig.tight_layout()
#     return fig
"""
graphes.py
----------
Fonctions qui construisent les figures matplotlib/seaborn à partir des
données nettoyées. Chaque fonction retourne un objet Figure (ne
sauvegarde rien elle-même) — utilisé par app_web.py (/graphe/<nom>.png).

Toutes les figures indiquent le nombre d'offres / d'entreprises réellement
utilisées (n = ...) et affichent les valeurs sur le graphique, pour être lisibles
sans deviner.
"""

import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from villes_maroc import VILLES_COORDS

sns.set_theme(style="whitegrid")

BLEU, ORANGE, VIOLET, VERT, GRIS = "#2457E6", "#F26419", "#6A4C93", "#137A49", "#8A97AB"
PALETTE = [BLEU, ORANGE, VIOLET, VERT, "#2E86AB", "#B3261E"]
NON_PRECISE = "Non précisé"


# ------------------------------------------------------------ utilitaires ----

def _txt(s):
    """Évite que '$' soit interprété comme du LaTeX par matplotlib."""
    return str(s).replace("$", r"\$")


def _titre(ax, titre, sous_titre=None):
    ax.set_title(_txt(titre) + (f"\n{_txt(sous_titre)}" if sous_titre else ""),
                 fontsize=12, fontweight="bold", loc="left", pad=12)


def _etiquettes_barres(ax, total=None, horizontal=False):
    """Écrit la valeur (et le % du total) au bout de chaque barre."""
    for b in ax.patches:
        v = b.get_width() if horizontal else b.get_height()
        if not v:
            continue
        label = f"{v:.0f}" + (f"  ({v / total * 100:.0f} %)" if total else "")
        if horizontal:
            ax.annotate(label, (v, b.get_y() + b.get_height() / 2), xytext=(4, 0),
                        textcoords="offset points", va="center", fontsize=9)
        else:
            ax.annotate(label, (b.get_x() + b.get_width() / 2, v), xytext=(0, 3),
                        textcoords="offset points", ha="center", fontsize=9)


def _jours_depuis_publication(df):
    """Âge de chaque offre en jours (« il y a N jours »), NaN si la date est inconnue."""
    def age(txt):
        m = re.search(r"il y a (\d+)\s*jour", str(txt))
        if m:
            return int(m.group(1))
        if re.search(r"aujourd|il y a (\d+)\s*(heure|minute)", str(txt)):
            return 0
        return np.nan
    return df["date_publication"].apply(age)


def _vide(texte="Pas assez de données pour ce graphique"):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.text(0.5, 0.5, texte, ha="center", va="center", color=GRIS)
    ax.axis("off")
    return fig


# ----------------------------------------------------------------- offres ----

def fig_bar_villes(df):
    s = df["ville"].value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(9, max(4, 0.42 * len(s) + 1.5)))
    ax.barh(s.index, s.values, color=BLEU)
    _etiquettes_barres(ax, total=len(df), horizontal=True)
    ax.set_xlim(0, s.max() * 1.22)
    ax.set_xlabel("Nombre d'offres")
    ax.set_ylabel("")
    _titre(ax, "Nombre d'offres par ville", f"n = {len(df)} offres · « {NON_PRECISE} » = ville absente de l'annonce")
    fig.tight_layout()
    return fig


def fig_pie_sources(df):
    s = df["source"].value_counts()
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.pie(s.values, labels=[f"{k}\n{v} offres" for k, v in s.items()], colors=PALETTE[:len(s)],
           autopct="%1.1f%%", startangle=90, pctdistance=0.78,
           wedgeprops={"width": 0.45, "edgecolor": "white"}, textprops={"fontsize": 10})
    ax.text(0, 0, f"{len(df)}\noffres", ha="center", va="center", fontsize=14, fontweight="bold")
    _titre(ax, "Répartition des offres par source")
    fig.tight_layout()
    return fig


def fig_hist_longueur(df):
    """Histogramme : UNE variable (longueur de la description)."""
    x = df["longueur_description"].dropna()
    if x.empty:
        return _vide()
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(x, bins=20, color=VIOLET, edgecolor="white")
    ax.axvline(x.mean(), color=ORANGE, ls="--", lw=2, label=f"moyenne = {x.mean():.0f}")
    ax.axvline(x.median(), color=VERT, ls=":", lw=2, label=f"médiane = {x.median():.0f}")
    ax.set_xlabel("Longueur de la description (caractères)")
    ax.set_ylabel("Nombre d'offres")
    ax.legend()
    tronque = int((x >= x.max()).sum())
    _titre(ax, "Distribution de la longueur des descriptions",
           f"n = {len(x)} offres · {tronque} descriptions tronquées à {x.max():.0f} caractères")
    fig.tight_layout()
    return fig


def fig_hist_anciennete(df):
    """Histogramme : UNE variable (ancienneté de l'offre en jours)."""
    age = _jours_depuis_publication(df).dropna()
    if age.empty:
        return _vide()
    fig, ax = plt.subplots(figsize=(9, 5))
    bins = np.arange(0, age.max() + 8, 7)          # une barre = une semaine
    ax.hist(age, bins=bins, color=BLEU, edgecolor="white")
    ax.axvline(age.median(), color=ORANGE, ls="--", lw=2, label=f"médiane = {age.median():.0f} jours")
    ax.set_xlabel("Ancienneté de l'offre (jours depuis la publication, 1 barre = 7 jours)")
    ax.set_ylabel("Nombre d'offres")
    ax.legend()
    manquantes = len(df) - len(age)
    _titre(ax, "Âge des offres publiées", f"n = {len(age)} offres datées · {manquantes} sans date (MarocEmploi)")
    fig.tight_layout()
    return fig


def fig_boxplot_longueur(df):
    n_par_ville = df["ville"].value_counts()
    villes = n_par_ville[n_par_ville >= 3].index.tolist()
    sub = df[df["ville"].isin(villes)]
    if sub.empty:
        return _vide()
    ordre = sub.groupby("ville")["longueur_description"].median().sort_values().index
    fig, ax = plt.subplots(figsize=(9, max(4, 0.55 * len(ordre) + 1.5)))
    sns.boxplot(data=sub, y="ville", x="longueur_description", order=ordre, color="#cfdcff", ax=ax)
    sns.stripplot(data=sub, y="ville", x="longueur_description", order=ordre, color=BLEU, size=3, alpha=.6, ax=ax)
    ax.set_yticks(range(len(ordre)))
    ax.set_yticklabels([f"{v} (n={n_par_ville[v]})" for v in ordre])
    ax.set_xlabel("Longueur de la description (caractères)")
    ax.set_ylabel("")
    _titre(ax, "Longueur des descriptions par ville", "villes avec au moins 3 offres · boîte = 50 % centraux, trait = médiane")
    fig.tight_layout()
    return fig


def fig_heatmap_ville_source(df):
    table = pd.crosstab(df["ville"], df["source"])
    table = table.loc[table.sum(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(7, max(4, 0.45 * len(table) + 1.5)))
    sns.heatmap(table, annot=True, fmt="d", cmap="YlGnBu", linewidths=.5, cbar_kws={"label": "Nombre d'offres"}, ax=ax)
    ax.set_xlabel("")
    ax.set_ylabel("")
    _titre(ax, "Nombre d'offres par ville et par source", f"n = {len(df)} offres")
    fig.tight_layout()
    return fig


def fig_timeline_offres(df):
    d = pd.to_datetime(df["date_publication_norm"], errors="coerce").dropna()
    if d.empty:
        return _vide()
    par_jour = d.dt.normalize().value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(par_jour.index, par_jour.values, marker="o", color=BLEU, lw=2)
    ax.fill_between(par_jour.index, par_jour.values, alpha=.12, color=BLEU)
    for x, y in par_jour.items():
        ax.annotate(int(y), (x, y), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8)
    ax.set_ylim(0, par_jour.max() * 1.2)
    ax.set_xlabel("Date de publication")
    ax.set_ylabel("Offres publiées ce jour-là")
    fig.autofmt_xdate()
    _titre(ax, "Offres publiées par date", f"n = {int(par_jour.sum())} offres datées")
    fig.tight_layout()
    return fig


def fig_bar_mots_cles(df):
    s = df["mot_cle"].value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(9, max(3.5, 0.55 * len(s) + 1.5)))
    ax.barh(s.index, s.values, color=ORANGE)
    _etiquettes_barres(ax, total=len(df), horizontal=True)
    ax.set_xlim(0, s.max() * 1.22)
    ax.set_xlabel("Nombre d'offres")
    ax.set_ylabel("")
    _titre(ax, "Offres par mot-clé de recherche", f"n = {len(df)} offres")
    fig.tight_layout()
    return fig


def fig_bubble_ville_motcle(df):
    """Bubble chart : ville (x) × mot-clé (y), taille de la bulle = nombre d'offres."""
    t = df.groupby(["ville", "mot_cle"]).size().reset_index(name="n")
    if t.empty:
        return _vide()
    villes = df["ville"].value_counts().index.tolist()
    mots = df["mot_cle"].value_counts().index.tolist()
    t["x"] = t["ville"].map({v: i for i, v in enumerate(villes)})
    t["y"] = t["mot_cle"].map({m: i for i, m in enumerate(mots)})
    fig, ax = plt.subplots(figsize=(10, max(4, 0.8 * len(mots) + 2)))
    ax.scatter(t["x"], t["y"], s=t["n"] * 45, color=BLEU, alpha=.55, edgecolor="white", linewidth=1.5)
    for _, r in t.iterrows():
        ax.annotate(int(r["n"]), (r["x"], r["y"]), ha="center", va="center", fontsize=8, fontweight="bold")
    ax.set_xticks(range(len(villes)))
    ax.set_xticklabels(villes, rotation=45, ha="right")
    ax.set_yticks(range(len(mots)))
    ax.set_yticklabels(mots)
    ax.set_xlim(-.7, len(villes) - .3)
    ax.set_ylim(-.7, len(mots) - .3)
    ax.grid(True, alpha=.4)
    _titre(ax, "Bubble chart : mot-clé × ville", "taille de la bulle = nombre d'offres (valeur écrite dans la bulle)")
    fig.tight_layout()
    return fig


def fig_bubble_carte_villes(df):
    """Bubble chart géographique : position = ville, taille de la bulle = nombre d'offres."""
    n = df["ville"].value_counts()
    inconnues = int(n.get(NON_PRECISE, 0))
    n = n[[v for v in n.index if v in VILLES_COORDS and v != NON_PRECISE]]
    if n.empty:
        return _vide()
    lon = [VILLES_COORDS[v][1] for v in n.index]
    lat = [VILLES_COORDS[v][0] for v in n.index]
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(lon, lat, s=n.values * 60, color=BLEU, alpha=.5, edgecolor="white", linewidth=1.5)
    for v, x, y, c in zip(n.index, lon, lat, n.values):
        ax.annotate(f"{v} ({c})", (x, y), xytext=(8, 6), textcoords="offset points", fontsize=9)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal", adjustable="datalim")
    ax.margins(.15)
    _titre(ax, "Carte des offres par ville (bubble chart)",
           f"taille = nombre d'offres · {inconnues} offres sans ville exclues de la carte")
    fig.tight_layout()
    return fig


def fig_scatter_anciennete_longueur(df):
    """Scatter : ancienneté de l'offre (x) contre longueur de la description (y), une couleur par source."""
    d = df.assign(age=_jours_depuis_publication(df)).dropna(subset=["age", "longueur_description"])
    if d.empty:
        return _vide()
    rng = np.random.default_rng(0)                  # léger décalage pour voir les points superposés
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for (source, sous), c in zip(d.groupby("source"), PALETTE):
        ax.scatter(sous["age"] + rng.uniform(-.4, .4, len(sous)), sous["longueur_description"],
                   label=f"{source} (n={len(sous)})", color=c, alpha=.6, s=55, edgecolor="white")
    ax.set_xlabel("Ancienneté de l'offre (jours)")
    ax.set_ylabel("Longueur de la description (caractères)")
    ax.legend(title="Source")
    _titre(ax, "Scatter : ancienneté × longueur de la description", f"n = {len(d)} offres datées")
    fig.tight_layout()
    return fig


# ------------------------------------------------------------ entreprises ----

def fig_bar_categories_entreprises(df_entreprises):
    s = df_entreprises["categorie"].replace("", NON_PRECISE).value_counts().head(12).sort_values()
    fig, ax = plt.subplots(figsize=(9, max(4, 0.45 * len(s) + 1.5)))
    ax.barh(s.index, s.values, color=ORANGE)
    _etiquettes_barres(ax, total=len(df_entreprises), horizontal=True)
    ax.set_xlim(0, s.max() * 1.22)
    ax.set_xlabel("Nombre d'entreprises")
    ax.set_ylabel("")
    _titre(ax, "Entreprises IA à Marrakech par catégorie",
           f"n = {len(df_entreprises)} entreprises · 12 catégories les plus fréquentes")
    fig.tight_layout()
    return fig


def fig_hist_notes(df_entreprises):
    """Histogramme : UNE variable (note Google)."""
    x = df_entreprises["note"].dropna()
    if x.empty:
        return _vide()
    fig, ax = plt.subplots(figsize=(9, 5))
    bins = np.arange(1, 5.26, .25)
    ax.hist(x, bins=bins, color=VERT, edgecolor="white")
    ax.axvline(x.mean(), color=ORANGE, ls="--", lw=2, label=f"moyenne = {x.mean():.2f}")
    ax.axvline(x.median(), color=BLEU, ls=":", lw=2, label=f"médiane = {x.median():.2f}")
    ax.set_xlabel("Note Google (sur 5, 1 barre = 0,25 point)")
    ax.set_ylabel("Nombre d'entreprises")
    ax.legend(loc="upper left")
    _titre(ax, "Distribution des notes des entreprises",
           f"n = {len(x)} entreprises notées · {len(df_entreprises) - len(x)} sans note")
    fig.tight_layout()
    return fig


def fig_scatter_note_avis(df_entreprises):
    """Scatter : nombre d'avis (x, échelle log) contre note (y)."""
    d = df_entreprises.dropna(subset=["note", "nombre_avis"])
    d = d[d["nombre_avis"] > 0]
    if d.empty:
        return _vide()
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.scatter(d["nombre_avis"], d["note"], color=BLEU, alpha=.6, s=60, edgecolor="white")
    for i, (_, r) in enumerate(d.nlargest(5, "nombre_avis").iterrows()):
        ax.annotate(_txt(str(r["nom"])[:28]), (r["nombre_avis"], r["note"]), xytext=(-8, -14 - 11 * (i % 3)),
                    textcoords="offset points", fontsize=8, ha="right",
                    arrowprops={"arrowstyle": "-", "color": GRIS, "lw": .6})
    ax.set_xscale("log")
    ax.set_ylim(.8, 5.3)
    ax.set_xlabel("Nombre d'avis (échelle logarithmique)")
    ax.set_ylabel("Note Google")
    _titre(ax, "Scatter : nombre d'avis × note", f"n = {len(d)} entreprises · les 5 plus commentées sont nommées")
    fig.tight_layout()
    return fig


def fig_bubble_categories(df_entreprises):
    """Bubble chart : par catégorie, note moyenne (x) × nombre d'entreprises (y), taille = total des avis."""
    d = df_entreprises.assign(categorie=df_entreprises["categorie"].replace("", NON_PRECISE))
    g = d.groupby("categorie").agg(n=("nom", "size"), note=("note", "mean"), avis=("nombre_avis", "sum")).dropna(subset=["note"])
    g = g.sort_values("n", ascending=False).head(10)
    if g.empty:
        return _vide()
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(g["note"], g["n"], s=40 + g["avis"] / g["avis"].max() * 1800, color=ORANGE, alpha=.5,
               edgecolor="white", linewidth=1.5)
    for i, (cat, r) in enumerate(g.head(6).iterrows()):       # seules les 6 plus grosses sont nommées (lisibilité)
        ax.annotate(f"{_txt(cat)} ({int(r['n'])} ent., {int(r['avis'])} avis)", (r["note"], r["n"]),
                    xytext=(-14, 14 + 16 * (i % 3)), textcoords="offset points", ha="right", fontsize=8,
                    arrowprops={"arrowstyle": "-", "color": GRIS, "lw": .6})
    ax.set_xlabel("Note moyenne (sur 5)")
    ax.set_ylabel("Nombre d'entreprises")
    ax.margins(.18)
    _titre(ax, "Bubble chart : catégories d'entreprises",
           "taille de la bulle = total des avis · 10 catégories les plus fréquentes, 6 nommées")
    fig.tight_layout()
    return fig
