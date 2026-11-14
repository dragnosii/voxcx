"""Briefing de direction : trois constats chiffrés, chacun relié à des avis sources."""
import pandas as pd

from voxcx.priorisation import table_priorites


def _fr(x, n=2):
    return f"{x:.{n}f}".replace(".", ",")


def faits(avis, aspects):
    """Retourne une liste de constats : {texte, nb_avis, sources (DataFrame d'avis), ton}."""
    res = []
    if avis.empty:
        return res
    fin = avis["date"].max()
    r = avis[avis["date"] > fin - pd.Timedelta(days=30)]
    p = avis[(avis["date"] <= fin - pd.Timedelta(days=30)) & (avis["date"] > fin - pd.Timedelta(days=60))]
    if len(r) >= 10 and len(p) >= 10:
        delta = r["note"].mean() - p["note"].mean()
        sens = "progresse" if delta > 0.02 else "recule" if delta < -0.02 else "reste stable"
        res.append({"texte": f"La note moyenne du groupe {sens} sur les 30 derniers jours : {_fr(r['note'].mean())} contre {_fr(p['note'].mean())} le mois précédent ({'+' if delta >= 0 else ''}{_fr(delta)}).",
                    "sources": r.sort_values("date", ascending=False).head(6), "ton": "ok" if delta >= 0 else "ko"})
    if not aspects.empty:
        pri = table_priorites(aspects)
        if not pri.empty:
            top = pri.iloc[0]
            g = aspects[(aspects["aspect"] == top["aspect"]) & (aspects["etiquette"] == "négatif")]
            hotel_top = g["hotel"].value_counts().index[0] if not g.empty else ""
            ids = g[g["hotel"] == hotel_top]["id"].tolist() if hotel_top else []
            res.append({"texte": f"Premier point de vigilance : « {top['aspect']} » ({int(top['negatives'])} commentaires négatifs, priorité {int(top['priorite'])}/100), surtout à {hotel_top}.",
                        "sources": avis[avis["id"].isin(ids)].sort_values("date", ascending=False).head(6), "ton": "ko"})
        pos = aspects[aspects["etiquette"] == "positif"].groupby("aspect").size().sort_values(ascending=False)
        if not pos.empty:
            asp = pos.index[0]
            g = aspects[(aspects["aspect"] == asp) & (aspects["etiquette"] == "positif")]
            hotel_best = g["hotel"].value_counts().index[0]
            ids = g[g["hotel"] == hotel_best]["id"].tolist()
            res.append({"texte": f"Principal point fort : « {asp} » ({int(pos.iloc[0])} commentaires positifs), en particulier à {hotel_best}.",
                        "sources": avis[avis["id"].isin(ids)].sort_values("likes", ascending=False).head(6), "ton": "info"})
    return res
