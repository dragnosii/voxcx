"""Chargement et nettoyage des avis Google Maps (hôtels Kenzi)."""
import json
import os

import pandas as pd

DOSSIER_APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(os.path.dirname(DOSSIER_APP), "data", "avis", "avis.csv")
PROPRE = os.path.join(DOSSIER_APP, "data", "avis_propres.csv")

# Tous les hôtels sont comparés à partir de cette date (Solazur, plafonné à 1 300 avis, ne remonte pas plus loin)
DATE_FENETRE_COMMUNE = "2026-05-14"


def _json(texte):
    if not isinstance(texte, str) or not texte.strip():
        return {}
    try:
        return json.loads(texte)
    except ValueError:
        return {}


def preparer(source=SOURCE, sortie=PROPRE):
    """Lit avis.csv, ajoute les colonnes utiles à l'analyse et enregistre avis_propres.csv."""
    d = pd.read_csv(source)
    out = pd.DataFrame()
    out["id"] = d["reviewId"]
    out["hotel"] = d["hotel"]
    out["ville"] = d["city"]
    out["date"] = pd.to_datetime(d["publishedAtDate"], utc=True).dt.tz_localize(None)
    out["mois"] = out["date"].dt.strftime("%Y-%m")
    out["semaine"] = out["date"].dt.to_period("W").dt.start_time
    out["note"] = d["stars"].astype(int)
    out["texte"] = d["text"].fillna("").astype(str).str.strip()
    out["texte_fr"] = d["textTranslated"].fillna("").astype(str).str.strip()
    out.loc[out["texte_fr"] == "", "texte_fr"] = out["texte"]
    out["a_texte"] = out["texte"].str.len() > 0
    out["langue"] = d["originalLanguage"].fillna("")

    detail = d["reviewDetailedRating"].map(_json)
    for cle, col in (("Chambres", "note_chambres"), ("Service", "note_service"), ("Emplacement", "note_emplacement")):
        out[col] = detail.map(lambda x, c=cle: x.get(c)).astype("float")

    ctx = d["reviewContext"].map(_json)
    out["type_voyage"] = ctx.map(lambda x: x.get("Type de voyage", ""))
    out["groupe"] = ctx.map(lambda x: x.get("Groupe de voy.", ""))

    out["auteur"] = d["name"].fillna("")
    out["auteur_nb_avis"] = pd.to_numeric(d["reviewerNumberOfReviews"], errors="coerce")
    out["local_guide"] = d["isLocalGuide"].fillna(False).astype(bool)
    out["likes"] = pd.to_numeric(d["likesCount"], errors="coerce").fillna(0).astype(int)
    out["url_avis"] = d["reviewUrl"].fillna("")

    out["reponse"] = d["responseFromOwnerText"].fillna("").astype(str).str.len() > 0
    out["texte_reponse"] = d["responseFromOwnerText"].fillna("").astype(str)
    rep = pd.to_datetime(d["responseFromOwnerDate"], utc=True, errors="coerce").dt.tz_localize(None)
    out["delai_reponse_h"] = (rep - out["date"]).dt.total_seconds() / 3600
    out.loc[out["delai_reponse_h"] < 0, "delai_reponse_h"] = pd.NA

    out["fenetre_commune"] = out["date"] >= pd.Timestamp(DATE_FENETRE_COMMUNE)
    out = out.sort_values("date").reset_index(drop=True)
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    out.to_csv(sortie, index=False, encoding="utf-8-sig")
    return out


def charger():
    """Charge les avis nettoyés (les prépare au premier appel)."""
    if not os.path.exists(PROPRE):
        return preparer()
    d = pd.read_csv(PROPRE, parse_dates=["date", "semaine"])
    d["texte"] = d["texte"].fillna("")
    d["texte_fr"] = d["texte_fr"].fillna("")
    d["texte_reponse"] = d["texte_reponse"].fillna("")
    for c in ("type_voyage", "groupe", "langue", "auteur"):
        d[c] = d[c].fillna("")
    return d


if __name__ == "__main__":
    df = preparer()
    print(len(df), "avis préparés ->", PROPRE)
    print(df.groupby("hotel").agg(avis=("id", "count"), note=("note", "mean"), reponse=("reponse", "mean")).round(2))
    print("fenêtre commune :", int(df["fenetre_commune"].sum()), "avis")
    print("délai de réponse médian (h) :", round(df["delai_reponse_h"].median(), 1))
