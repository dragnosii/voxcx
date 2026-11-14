"""Priorisation des problèmes : score = fréquence x gravité x tendance (0 à 100)."""
import numpy as np
import pandas as pd


def _tendance(dates, negatif, jours=56):
    """Variation de la part d'avis négatifs : dernières 8 semaines contre les 8 précédentes (en points)."""
    fin = dates.max()
    recent = dates > fin - pd.Timedelta(days=jours)
    avant = (dates <= fin - pd.Timedelta(days=jours)) & (dates > fin - pd.Timedelta(days=2 * jours))
    if recent.sum() < 5 or avant.sum() < 5:
        return 0.0
    return float(negatif[recent].mean() - negatif[avant].mean())


def table_priorites(aspects, hotel=None, ville=None):
    """aspects : tableau de nlp.calculer() (une ligne par phrase mentionnant un aspect)."""
    d = aspects.copy()
    if hotel:
        d = d[d["hotel"] == hotel]
    if ville:
        d = d[d["ville"] == ville]
    if d.empty:
        return pd.DataFrame()
    d["neg"] = (d["etiquette"] == "négatif").astype(int)
    lignes = []
    for asp, g in d.groupby("aspect"):
        n_neg = int(g["neg"].sum())
        if n_neg == 0:
            continue
        gravite = float(-g.loc[g["neg"] == 1, "score"].mean())  # 0,25 à 1
        part_neg = n_neg / len(g)
        tend = _tendance(g["date"], g["neg"])
        lignes.append({
            "aspect": asp, "mentions": len(g), "negatives": n_neg, "part_negative": part_neg,
            "gravite": gravite, "tendance": tend,
            "_brut": n_neg * gravite * (1 + np.clip(tend * 5, -0.5, 1.0)),
        })
    t = pd.DataFrame(lignes)
    if t.empty:
        return t
    t["priorite"] = (100 * t["_brut"] / t["_brut"].max()).round().astype(int)
    t["niveau"] = pd.cut(t["priorite"], [-1, 33, 66, 100], labels=["Faible", "Moyen", "Élevé"])
    return t.drop(columns="_brut").sort_values("priorite", ascending=False).reset_index(drop=True)


def matrice_sentiment(aspects, par="hotel"):
    """Score moyen par aspect et par hôtel (carte de chaleur), de 0 à 10."""
    d = aspects.copy()
    d["note10"] = (d["score"] + 1) * 5
    return d.pivot_table(index="aspect", columns=par, values="note10", aggfunc="mean").round(1)


def alertes(aspects, avis, seuil_hausse=0.08):
    """Détecte les hausses de plaintes par (hôtel, aspect) et les chutes de note par hôtel."""
    res = []
    for (hotel, asp), g in aspects.groupby(["hotel", "aspect"]):
        g = g.assign(neg=(g["etiquette"] == "négatif").astype(int))
        t = _tendance(g["date"], g["neg"])
        n_neg = int(g["neg"].sum())
        if t >= seuil_hausse and n_neg >= 8:
            res.append({"niveau": "Critique" if t >= 0.15 else "Attention", "hotel": hotel, "aspect": asp,
                        "texte": f"{asp} : la part de commentaires négatifs augmente de {t * 100:.0f} points en 8 semaines", "valeur": t, "n": n_neg})
    return pd.DataFrame(res).sort_values("valeur", ascending=False).reset_index(drop=True) if res else pd.DataFrame(columns=["niveau", "hotel", "aspect", "texte", "valeur", "n"])
