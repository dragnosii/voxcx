"""Couche de service : tous les calculs que l'interface web demande (aucune dépendance à l'interface)."""
import csv
import os
import threading

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import Ridge
from sklearn.metrics import f1_score

from voxcx.donnees import DATE_FENETRE_COMMUNE, DOSSIER_APP, charger
from voxcx.nlp import CACHE_ASPECTS, CACHE_AVIS, decouper_phrases, detecter_aspects
from voxcx.priorisation import alertes as _alertes
from voxcx.priorisation import table_priorites

PLAN = os.path.join(DOSSIER_APP, "data", "plan_actions.csv")
EXPERIENCE = os.path.join(DOSSIER_APP, "data", "experience_chronometree.csv")
JOURNAL = os.path.join(DOSSIER_APP, "data", "journal_gouvernance.csv")
_verrous = {k: threading.Lock() for k in ('d', 'assistant', 'pq')}
_cache = {}

# Actions types proposées (mode local) : action, porteur, effort de 1 à 5, indicateur
ACTIONS = {
    "Chambre et literie": ("Plan de rénovation et contrôle qualité des chambres les plus citées", "Direction technique", 5, "Part de commentaires négatifs sur les chambres -30 %"),
    "Propreté": ("Audit de propreté inopiné et checklist de contrôle des étages", "Gouvernante générale", 2, "Plaintes de propreté -40 %"),
    "Personnel et service": ("Formation accueil et gestion des réclamations", "Ressources humaines", 2, "Note du service +0,2 point"),
    "Petit-déjeuner et restauration": ("Revue du buffet et des temps d'attente au petit-déjeuner", "Direction restauration", 3, "Commentaires négatifs restauration -30 %"),
    "Piscine, spa et animations": ("Entretien et planning des équipements de loisirs", "Direction loisirs", 4, "Commentaires négatifs loisirs -30 %"),
    "Emplacement": ("Informations de transport et navettes pour compenser l'éloignement", "Réception", 1, "Mentions négatives de l'emplacement -20 %"),
    "Bruit": ("Audit acoustique des chambres exposées et pose de double vitrage", "Direction technique", 5, "Mentions négatives du bruit -50 %"),
    "Prix et rapport qualité-prix": ("Revue de la politique tarifaire et des services inclus", "Direction commerciale", 3, "Mentions négatives du prix -25 %"),
    "Wi-Fi et équipements": ("Renforcement du Wi-Fi et maintenance préventive (clim, ascenseurs)", "DSI et maintenance", 3, "Pannes signalées -60 %"),
    "Arrivée et départ": ("Check-in rapide et personnel supplémentaire aux heures de pointe", "Réception", 2, "Mentions d'attente -50 %"),
    "Parking": ("Réorganisation du parking et signalétique", "Services généraux", 3, "Plaintes parking -40 %"),
}
STATUTS = ["À valider", "En cours", "Terminé", "Refusée"]


# ------------------------------------------------------------------ données
def donnees():
    with _verrous['d']:
        if "d" not in _cache:
            d = charger()
            if os.path.exists(CACHE_AVIS):
                d = d.merge(pd.read_csv(CACHE_AVIS), on="id", how="left")
            else:
                d["sentiment"], d["etiquette"] = np.nan, None
            if os.path.exists(CACHE_ASPECTS):
                asp = pd.read_csv(CACHE_ASPECTS, parse_dates=["date"])
            else:
                asp = pd.DataFrame(columns=["id", "hotel", "ville", "date", "aspect", "phrase", "score", "etiquette"])
            _cache["d"] = (d, asp)
        return _cache["d"]


def meta():
    d, _ = donnees()
    hotels = d.groupby(["ville", "hotel"]).size().reset_index(name="avis")
    return {
        "hotels": [{"hotel": r.hotel, "ville": r.ville, "avis": int(r.avis)} for r in hotels.itertuples()],
        "villes": sorted(d["ville"].unique().tolist()),
        "date_min": d["date"].min().strftime("%Y-%m-%d"),
        "date_max": d["date"].max().strftime("%Y-%m-%d"),
        "fenetre_commune": DATE_FENETRE_COMMUNE,
        "nb_avis_total": int(len(d)),
    }


def filtrer(debut=None, fin=None, hotels=None, villes=None):
    d, asp = donnees()
    debut = pd.Timestamp(debut or DATE_FENETRE_COMMUNE)
    fin = (pd.Timestamp(fin) if fin else d["date"].max()) + pd.Timedelta(days=1)
    m = (d["date"] >= debut) & (d["date"] < fin)
    ma = (asp["date"] >= debut) & (asp["date"] < fin)
    if hotels:
        m &= d["hotel"].isin(hotels)
        ma &= asp["hotel"].isin(hotels)
    if villes:
        m &= d["ville"].isin(villes)
        ma &= asp["ville"].isin(villes)
    return d[m].copy(), asp[ma].copy()


def _f(x, n=2):
    return float(round(float(x), n)) if pd.notna(x) else None


def _source(r):
    return {"hotel": r.hotel, "ville": r.ville, "date": r.date.strftime("%d/%m/%Y"), "note": int(r.note), "auteur": r.auteur or "",
            "texte": (r.texte_fr or r.texte or "")[:500], "langue": r.langue or "", "reponse": bool(r.reponse)}


def _fr(x, n=2):
    return f"{x:.{n}f}".replace(".", ",")


# ------------------------------------------------------------------ accueil
def accueil(avis, asp, action="2026-07-16"):
    if avis.empty:
        return {"vide": True}
    fin = avis["date"].max()
    r30 = avis[avis["date"] > fin - pd.Timedelta(days=30)]
    p30 = avis[(avis["date"] <= fin - pd.Timedelta(days=30)) & (avis["date"] > fin - pd.Timedelta(days=60))]
    nps = lambda x: 100 * ((x["note"] == 5).mean() - (x["note"] <= 3).mean())
    pri = table_priorites(asp) if not asp.empty else pd.DataFrame()
    delta = (r30["note"].mean() - p30["note"].mean()) if len(r30) >= 10 and len(p30) >= 10 else None

    insights = []
    if delta is not None:
        ton = "ok" if delta > 0.02 else "ko" if delta < -0.02 else "info"
        titre = {"ok": "Ça va mieux", "ko": "Ça baisse", "info": "Stable"}[ton]
        texte = (f"La note passe de {_fr(p30['note'].mean())} à {_fr(r30['note'].mean())} sur les 30 derniers jours."
                 if ton != "info" else f"La note reste stable à {_fr(r30['note'].mean())} sur les 30 derniers jours.")
        insights.append({"ton": ton, "icone": "tendance", "titre": titre, "texte": texte, "lien": "themes", "n": len(r30),
                         "sources": [_source(r) for r in r30.sort_values("date", ascending=False).head(6).itertuples()]})
    if not pri.empty:
        top = pri.iloc[0]
        g = asp[(asp["aspect"] == top["aspect"]) & (asp["etiquette"] == "négatif")]
        hotel_top = g["hotel"].value_counts().index[0] if not g.empty else ""
        ids = g[g["hotel"] == hotel_top]["id"].tolist() if hotel_top else []
        src = avis[avis["id"].isin(ids)].sort_values("date", ascending=False).head(6)
        insights.append({"ton": "ko", "icone": "alerte", "titre": "À traiter en premier",
                         "texte": f"« {top['aspect']} » : {int(top['negatives'])} commentaires négatifs, surtout à {hotel_top}.", "lien": "plan", "n": int(top["negatives"]),
                         "sources": [_source(r) for r in src.itertuples()]})
        pos = asp[asp["etiquette"] == "positif"].groupby("aspect").size().sort_values(ascending=False)
        if not pos.empty:
            a = pos.index[0]
            g = asp[(asp["aspect"] == a) & (asp["etiquette"] == "positif")]
            hb = g["hotel"].value_counts().index[0]
            src = avis[avis["id"].isin(g[g["hotel"] == hb]["id"])].sort_values("likes", ascending=False).head(6)
            insights.append({"ton": "accent", "icone": "etoile", "titre": "Point fort",
                             "texte": f"« {a} » : {int(pos.iloc[0]):,} commentaires positifs, surtout à {hb}.".replace(",", " "), "lien": "themes", "n": int(pos.iloc[0]),
                             "sources": [_source(r) for r in src.itertuples()]})

    mois = avis.groupby("mois").agg(note=("note", "mean"), n=("id", "count")).reset_index()
    par_mois = avis.groupby("mois").apply(lambda g: pd.Series({"nps": nps(g), "plaintes": 100 * (g["note"] <= 2).mean(), "reponse": 100 * g["reponse"].mean()}), include_groups=False).reset_index()
    mois = mois.merge(par_mois, on="mois")
    liste_mois = mois["mois"].tolist()
    cible = pd.Timestamp(action)
    avant, apres = avis[avis["date"] < cible], avis[avis["date"] >= cible]
    aa = None
    if len(avant) > 20 and len(apres) > 20:
        _, p = stats.ttest_ind(apres["note"], avant["note"], equal_var=False)
        aa = {"avant": _f(avant["note"].mean()), "n_avant": int(len(avant)), "apres": _f(apres["note"].mean()), "n_apres": int(len(apres)),
              "ecart": _f(apres["note"].mean() - avant["note"].mean()), "p": _f(p, 4), "significatif": bool(p < 0.05)}

    al = _alertes(asp, avis) if not asp.empty else pd.DataFrame()
    alertes_liste = [{"niveau": r.niveau, "hotel": r.hotel, "texte": r.texte.replace(f"{r.aspect} : ", f"{r.aspect} : ", 1)} for r in al.head(4).itertuples()]
    classement = avis.groupby("hotel").agg(note=("note", "mean"), n=("id", "count"), ville=("ville", "first")).sort_values("note", ascending=False).reset_index()
    spark = avis.groupby(["hotel", "mois"])["note"].mean().unstack()
    r30h = avis[avis["date"] > fin - pd.Timedelta(days=30)].groupby("hotel")["note"].mean()
    p30h = avis[(avis["date"] <= fin - pd.Timedelta(days=30)) & (avis["date"] > fin - pd.Timedelta(days=60))].groupby("hotel")["note"].mean()
    sent = avis[avis["a_texte"] & avis["etiquette"].notna()].groupby(["hotel", "etiquette"]).size().unstack(fill_value=0)
    sent = sent.div(sent.sum(axis=1), axis=0) * 100

    return {
        "vide": False,
        "periode": {"debut": avis["date"].min().strftime("%d/%m/%Y"), "fin": avis["date"].max().strftime("%d/%m/%Y")},
        "n_avis": int(len(avis)), "n_hotels": int(avis["hotel"].nunique()),
        "kpis": {
            "note": _f(avis["note"].mean()), "delta30": _f(delta) if delta is not None else None,
            "nps": _f(nps(avis), 0), "plaintes": _f(100 * (avis["note"] <= 2).mean(), 1),
            "reponse": _f(100 * avis["reponse"].mean(), 0), "delai_h": _f(avis["delai_reponse_h"].median(), 0),
            "delta_nps": _f(nps(r30) - nps(p30), 0) if len(r30) >= 10 and len(p30) >= 10 else None,
            "delta_plaintes": _f(100 * (r30["note"] <= 2).mean() - 100 * (p30["note"] <= 2).mean(), 1) if len(r30) >= 10 and len(p30) >= 10 else None,
            "delta_reponse": _f(100 * r30["reponse"].mean() - 100 * p30["reponse"].mean(), 0) if len(r30) >= 10 and len(p30) >= 10 else None,
        },
        "insights": insights,
        "serie": [{"mois": r.mois, "note": _f(r.note, 3), "n": int(r.n), "nps": _f(r.nps, 1), "plaintes": _f(r.plaintes, 1), "reponse": _f(r.reponse, 1)} for r in mois.itertuples()],
        "action": action, "avant_apres": aa,
        "alertes": alertes_liste,
        "classement": [{"hotel": r.hotel, "ville": r.ville, "note": _f(r.note), "n": int(r.n),
                        "spark": [_f(spark.loc[r.hotel, m], 3) if (r.hotel in spark.index and m in spark.columns) else None for m in liste_mois],
                        "delta30": _f(r30h.get(r.hotel) - p30h.get(r.hotel)) if (r.hotel in r30h.index and r.hotel in p30h.index) else None} for r in classement.itertuples()],
        "sentiments": [{"hotel": h, "positif": _f(sent.loc[h].get("positif", 0), 1), "neutre": _f(sent.loc[h].get("neutre", 0), 1), "negatif": _f(sent.loc[h].get("négatif", 0), 1)} for h in classement["hotel"] if h in sent.index],
    }


# ------------------------------------------------------------------ thèmes
def _phrases_lecture(avis, asp, rang=0):
    """Choisit un avis récent riche en aspects et retourne ses phrases étiquetées."""
    cand = asp.groupby("id")["aspect"].nunique()
    cand = cand[cand >= 3].index
    s = avis[avis["id"].isin(cand) & (avis["texte"].str.len().between(80, 420))].sort_values("date", ascending=False)
    if s.empty:
        return None
    r = s.iloc[rang % min(len(s), 25)]
    lab = asp[asp["id"] == r["id"]].drop_duplicates("phrase").set_index("phrase")["etiquette"].to_dict()
    phrases = []
    for p in decouper_phrases(r["texte"]):
        phrases.append({"texte": p, "sens": lab.get(p), "aspects": detecter_aspects(p)})
    return {"hotel": r["hotel"], "date": r["date"].strftime("%d/%m/%Y"), "note": int(r["note"]), "auteur": r["auteur"], "langue": r["langue"], "phrases": phrases}


def themes(avis, asp, rang=0):
    if asp.empty:
        return {"vide": True}
    g = asp.groupby("aspect").agg(mentions=("id", "count"), negatives=("etiquette", lambda s: int((s == "négatif").sum()))).reset_index()
    g["part"] = g["negatives"] / g["mentions"]
    g = g.sort_values("mentions", ascending=False)
    pri = table_priorites(asp)
    fiab = []
    for nom, col in (("Chambre et literie", "note_chambres"), ("Personnel et service", "note_service"), ("Emplacement", "note_emplacement")):
        x = asp[asp["aspect"] == nom].groupby("id")["score"].mean().rename("m").to_frame().join(avis.set_index("id")[col]).dropna()
        if len(x) > 30:
            fiab.append({"aspect": nom, "n": int(len(x)), "corr": _f(x["m"].corr(x[col], method="spearman"))})
    mat = asp.assign(note10=(asp["score"] + 1) * 5).pivot_table(index="aspect", columns="hotel", values="note10", aggfunc=["mean", "count"])
    ordre = g["aspect"].tolist()
    hotels_cols = sorted(asp["hotel"].unique())
    matrice = {"aspects": ordre, "hotels": hotels_cols, "valeurs": [[(_f(mat[("mean", h)].get(a), 1) if (mat[("count", h)].get(a, 0) or 0) >= 5 else None) if ("mean", h) in mat.columns else None for h in hotels_cols] for a in ordre]}
    return {
        "vide": False,
        "matrice": matrice,
        "sujets": [{"aspect": r.aspect, "mentions": int(r.mentions), "negatives": int(r.negatives), "part": _f(r.part, 3)} for r in g.itertuples()],
        "priorites": [{"aspect": r.aspect, "negatives": int(r.negatives), "tendance": _f(r.tendance * 100, 1), "priorite": int(r.priorite), "niveau": str(r.niveau)} for r in pri.head(3).itertuples()] if not pri.empty else [],
        "lecture": _phrases_lecture(avis, asp, rang), "fiabilite": fiab,
    }


def phrases_aspect(avis, asp, aspect, sens="négatif", limite=12):
    g = asp[(asp["aspect"] == aspect) & (asp["etiquette"] == sens)].sort_values("date", ascending=False).head(limite)
    info = avis.set_index("id")
    out = []
    for r in g.itertuples():
        a = info.loc[r.id] if r.id in info.index else None
        out.append({"hotel": r.hotel, "date": r.date.strftime("%d/%m/%Y"), "note": int(a["note"]) if a is not None else None,
                    "auteur": (a["auteur"] if a is not None else ""), "phrase": r.phrase})
    return out


# ------------------------------------------------------------------ assistant
def assistant():
    with _verrous['assistant']:
        if "assistant" not in _cache:
            from voxcx.assistant import Assistant

            _cache["assistant"] = Assistant()
    return _cache["assistant"]


def question(texte, hotel=None, negatifs=False, k=8, mode="local", depuis=None):
    from voxcx.assistant import mode_en_ligne_disponible

    bot = assistant()
    rep = bot.repondre(texte, k=k, mode=mode, hotel=hotel or None, negatifs_seulement=negatifs, depuis=pd.Timestamp(depuis) if depuis else None)
    return {"texte": rep["texte"], "mode": rep["mode"], "confiance": rep["confiance"], "duree": round(rep["duree"], 1),
            "en_ligne_disponible": mode_en_ligne_disponible(),
            "sources": [dict(_source(r), similarite=round(float(r.similarite), 2)) for r in rep["sources"].itertuples()]}


# ------------------------------------------------------------------ prédictif
def modele_predictif():
    with _verrous['pq']:
        if "pq" not in _cache:
            from voxcx.prediction import charger_modele

            _cache["pq"] = charger_modele()
    return _cache["pq"]


def predictif():
    from voxcx.prediction import COMBINE

    pq = modele_predictif()
    bm, reg, tai, tp = pq["benchmark"], pq["regression"], pq["taille"], pq["test_pred"]
    lr = bm[bm["modele"] == COMBINE].iloc[0]
    glob = f1_score(tp["insatisfait"], tp["risque"] >= pq["seuil"])
    biais = []
    for col, nom in (("langue", "Langue de l'avis"), ("type_voyage", "Type de voyage"), ("ville", "Ville")):
        groupes = []
        for val, g in tp.groupby(col):
            if val and len(g) >= 40 and g["insatisfait"].sum() >= 3:
                groupes.append({"nom": val, "n": int(len(g)), "f1": _f(f1_score(g["insatisfait"], g["risque"] >= pq["seuil"]))})
        if groupes:
            ecart = max(abs(x["f1"] - glob) for x in groupes)
            biais.append({"critere": nom, "groupes": groupes, "ecart": _f(ecart), "statut": "ok" if ecart <= 0.10 else "mid" if ecart <= 0.20 else "ko"})
    return {
        "f1": _f(lr["f1"]), "auc": _f(lr["auc"]), "mae": _f(reg["mae"]), "mae_ref": _f(reg["mae_reference"]), "r2": _f(reg["r2"]),
        "n_app": tai["app"], "n_test": tai["test"], "n_pos_test": tai["positifs_test"], "date_coupure": tai["date_coupure"],
        "benchmark": [{"modele": r.modele, "f1": _f(r.f1), "auc": _f(r.auc), "retenu": r.modele == COMBINE} for r in bm.sort_values("f1", ascending=False).itertuples()],
        "biais": biais, "seuil": _f(pq["seuil"]),
    }


def tester_avis(texte):
    from voxcx.prediction import expliquer, predire

    pq = modele_predictif()
    import re
    import unicodedata

    p = predire([texte], pq).iloc[0]
    sans_accent = lambda s: "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    originaux = {sans_accent(m.lower()): m.lower() for m in re.findall(r"\w+", texte)}

    def joli(mot):
        if mot.startswith("["):
            return "ton général de l'avis"
        return " ".join(originaux.get(part, part) for part in mot.split(" "))

    return {"risque": _f(p["risque"], 3), "note_prevue": _f(p["note_prevue"], 1), "seuil": _f(pq["seuil"]),
            "contributions": [{"mot": joli(m), "valeur": _f(v, 2)} for m, v in expliquer(texte, pq, n=8)]}


# ------------------------------------------------------------------ journal
def journaliser(evenement, auteur, detail):
    from voxcx.assistant import journaliser as j

    j(evenement, auteur, detail)


def journal(n=8):
    if not os.path.exists(JOURNAL):
        return []
    j = pd.read_csv(JOURNAL).fillna("").tail(n).iloc[::-1]
    return [{"date": r.date, "evenement": r.evenement, "auteur": r.auteur, "detail": r.detail} for r in j.itertuples()]


# ------------------------------------------------------------------ plan d'actions
def _lire_plan():
    if os.path.exists(PLAN):
        p = pd.read_csv(PLAN).fillna("")
        for c in ("id", "quoi", "pourquoi", "qui", "ou", "quand", "cout", "kpi", "statut", "aspect", "priorite"):
            if c not in p.columns:
                p[c] = ""
        return p
    return pd.DataFrame(columns=["id", "quoi", "pourquoi", "qui", "ou", "quand", "cout", "kpi", "statut", "aspect", "priorite"])


def plan():
    p = _lire_plan()
    return [{"id": int(r.id), "quoi": r.quoi, "pourquoi": r.pourquoi, "qui": r.qui, "ou": r.ou, "quand": r.quand,
             "cout": int(r.cout) if str(r.cout) != "" else 0, "kpi": r.kpi, "statut": r.statut, "aspect": r.aspect,
             "priorite": int(r.priorite) if str(r.priorite) != "" else None} for r in p.itertuples()]


def proposer_actions(avis, asp, n=4):
    pri = table_priorites(asp)
    p = _lire_plan()
    existants = set(p["aspect"]) if len(p) else set()
    prochain = int(p["id"].max()) + 1 if len(p) else 1
    lignes = []
    for r in pri.head(n).itertuples():
        if r.aspect in existants:
            continue
        quoi, qui, effort, kpi = ACTIONS.get(r.aspect, (f"Traiter « {r.aspect} »", "À définir", 3, ""))
        g = asp[(asp["aspect"] == r.aspect) & (asp["etiquette"] == "négatif")]["hotel"].value_counts()
        lignes.append({"id": prochain, "quoi": quoi, "pourquoi": f"{r.aspect} : priorité {r.priorite} sur 100", "qui": qui,
                       "ou": g.index[0] if len(g) else "Tous les hôtels", "quand": "T+3 mois", "cout": effort * 30000, "kpi": kpi,
                       "statut": "À valider", "aspect": r.aspect, "priorite": r.priorite})
        prochain += 1
    if lignes:
        pd.concat([p, pd.DataFrame(lignes)], ignore_index=True).to_csv(PLAN, index=False, encoding="utf-8-sig")
        journaliser("recommandation", "IA", f"{len(lignes)} actions proposées")
    return len(lignes)


def changer_statut(id_action, statut):
    if statut not in STATUTS:
        raise ValueError("statut inconnu")
    p = _lire_plan()
    i = p.index[p["id"].astype(int) == int(id_action)]
    if len(i) == 0:
        raise ValueError("action introuvable")
    ancien = p.loc[i[0], "statut"]
    p.loc[i[0], "statut"] = statut
    p.to_csv(PLAN, index=False, encoding="utf-8-sig")
    journaliser("décision", "Humain", f"{p.loc[i[0], 'quoi']} : {ancien} → {statut}")


def simulateur(avis, asp, aspect, part=50, cout=180000):
    d = avis[avis["a_texte"]]
    neg = asp[asp["etiquette"] == "négatif"].groupby(["id", "aspect"]).size().unstack(fill_value=0).clip(upper=1)
    X = d.set_index("id")[[]].join(neg).fillna(0)
    y = d.set_index("id")["note"]
    if len(X) < 100 or aspect not in X.columns:
        return {"ok": False}
    coef = pd.Series(Ridge(alpha=5).fit(X, y).coef_, index=X.columns)
    p_neg = float(X[aspect].mean())
    gain = max(-coef[aspect] * p_neg * part / 100, 0)
    evites = int(X[aspect].sum() * part / 100)
    return {"ok": True, "gain": _f(gain, 3), "impact_unitaire": _f(coef[aspect]), "evites": evites, "observes": int(X[aspect].sum()),
            "cout_par_evite": int(round(cout / max(evites, 1)))}


def aspects_simulables(asp):
    pri = table_priorites(asp)
    return pri["aspect"].tolist() if not pri.empty else []


# ------------------------------------------------------------------ expérience chronométrée
def lire_experience():
    if os.path.exists(EXPERIENCE):
        e = pd.read_csv(EXPERIENCE)
        return [{"testeur": r[0], "avis": r[1], "main": None if pd.isna(r[2]) else float(r[2]), "outil": None if pd.isna(r[3]) else float(r[3])} for r in e.itertuples(index=False)]
    return [{"testeur": f"Testeur {i}", "avis": 100, "main": None, "outil": None} for i in (1, 2, 3)]


def ecrire_experience(lignes):
    with open(EXPERIENCE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Testeur", "Avis analysés", "Minutes à la main", "Minutes avec l'outil"])
        for r in lignes:
            w.writerow([r.get("testeur", ""), r.get("avis", 100), "" if r.get("main") in (None, "") else r["main"], "" if r.get("outil") in (None, "") else r["outil"]])
    journaliser("expérience", "Humain", f"{len(lignes)} testeurs enregistrés")


def prechauffer():
    """Charge les modèles en arrière-plan pour que les premières réponses soient rapides."""
    try:
        donnees()
        assistant()
        modele_predictif()
        from voxcx.prediction import _sentiment_modele

        _sentiment_modele()
    except Exception as e:  # le serveur reste utilisable : l'erreur éventuelle réapparaîtra à la première requête concernée
        print("Préchauffage incomplet :", e)
