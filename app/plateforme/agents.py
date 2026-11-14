"""Les agents métier de VoxCX 2.
- Collecte : import de tout l'historique à la connexion d'une fiche, puis synchronisation ; enquêtes QR / WhatsApp.
- Rattrapage : une enquête mécontente ouvre un cas et prévient le gérant, avec un conseil d'appel.
- Réponse : file des avis récents sans réponse, brouillon dans la langue du client, validation humaine.
- Analyste : tableau « Ce matin » (pouls, sujets, décisions) et questions en langage naturel avec sources.
"""
import hashlib
import json
import threading
from collections import Counter
from datetime import datetime, timedelta

import pandas as pd

from plateforme import base, ia
from plateforme.config import CACHE_ASPECTS_DEMO, CACHE_SENTIMENT_DEMO, SOURCE_DEMO

JOURS_A_TRAITER = 90  # seuls les avis récents sans réponse entrent dans la file « à répondre »


# ----------------------------------------------------------------- Collecte : connexion d'une fiche (démo)
def fiches_demo():
    """Fiches disponibles pour la connexion de démonstration (remplacée en production par l'API Google Business Profile)."""
    try:
        d = pd.read_csv(SOURCE_DEMO, usecols=["hotel", "ville"], encoding="utf-8-sig")
    except (FileNotFoundError, ValueError):
        return []
    g = d.groupby(["hotel", "ville"]).size().reset_index(name="n")
    return [{"fiche": r.hotel, "ville": r.ville, "avis": int(r.n)} for r in g.itertuples()]


def _pseudo(auteur):
    return "Client " + hashlib.sha256(str(auteur).encode("utf-8")).hexdigest()[:6].upper()


def lancer_import(etab_id, fiche):
    base.ecrire("UPDATE etablissements SET import_statut='en_cours', import_fait=0, import_total=0, source_connectee=? WHERE id=?",
                (f"Google (démo) : {fiche}", etab_id))
    threading.Thread(target=_importer, args=(etab_id, fiche), daemon=True).start()


def _importer(etab_id, fiche):
    try:
        d = pd.read_csv(SOURCE_DEMO, encoding="utf-8-sig")
        d = d[d["hotel"] == fiche].copy()
        d["date"] = pd.to_datetime(d["date"])
        total = len(d)
        base.ecrire("UPDATE etablissements SET import_total=? WHERE id=?", (total, etab_id))
        # Analyse déjà calculée pour ce jeu de démonstration (sinon : modèle local)
        try:
            sent = pd.read_csv(CACHE_SENTIMENT_DEMO).set_index("id")["sentiment"].to_dict()
            asp = pd.read_csv(CACHE_ASPECTS_DEMO, encoding="utf-8-sig")
            sujets = asp.groupby("id")["aspect"].apply(lambda s: sorted(set(s))).to_dict()
            negs = asp[asp["etiquette"].str.startswith("n") & (asp["etiquette"] != "neutre")].groupby("id")["aspect"].apply(lambda s: sorted(set(s))).to_dict()
        except (FileNotFoundError, KeyError):
            sent, sujets, negs = {}, {}, {}
        limite = datetime.now() - timedelta(days=JOURS_A_TRAITER)
        lignes, fait = [], 0
        a_analyser = []
        for r in d.itertuples():
            texte = r.texte if isinstance(r.texte, str) else ""
            texte_fr = r.texte_fr if isinstance(r.texte_fr, str) else texte
            repondu = bool(r.reponse) if not pd.isna(r.reponse) else False
            rep_date = None
            if repondu and not pd.isna(r.delai_reponse_h):
                rep_date = (r.date + timedelta(hours=float(r.delai_reponse_h))).isoformat(sep=" ")[:19]
            statut = "repondu" if repondu else ("a_traiter" if r.date >= limite and texte.strip() else "historique")
            s = sent.get(r.id)
            if s is None and texte.strip():
                a_analyser.append((r.id, texte))
            lignes.append((base.nouvel_id(), etab_id, "google", r.id, _pseudo(r.auteur), int(r.note), texte, texte_fr,
                           r.langue if isinstance(r.langue, str) else "", r.date.isoformat(sep=" ")[:19],
                           None if s is None else float(s), json.dumps(sujets.get(r.id, []), ensure_ascii=False),
                           json.dumps(negs.get(r.id, []), ensure_ascii=False), int(repondu),
                           (r.texte_reponse if isinstance(r.texte_reponse, str) else ""), rep_date, statut))
            fait += 1
            if fait % 200 == 0:
                base.ecrire("UPDATE etablissements SET import_fait=? WHERE id=?", (fait, etab_id))
        base.ecrire_plusieurs(
            "INSERT OR IGNORE INTO avis (id, etablissement_id, source, id_externe, auteur, note, texte, texte_fr, langue, date, "
            "sentiment, aspects, aspects_neg, repondu, reponse, reponse_date, statut) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", lignes)
        # Avis jamais analysés : modèle local (gratuit)
        if a_analyser:
            res = ia.analyser([t for _, t in a_analyser])
            base.ecrire_plusieurs("UPDATE avis SET sentiment=?, aspects=?, aspects_neg=? WHERE etablissement_id=? AND id_externe=?",
                                  [(s, json.dumps(a, ensure_ascii=False), json.dumps(n, ensure_ascii=False), etab_id, i)
                                   for (i, _), (s, a, n) in zip(a_analyser, res)])
        base.ecrire("UPDATE etablissements SET import_statut='termine', import_fait=? WHERE id=?", (total, etab_id))
        base.journaliser("import_termine", None, f"{etab_id} : {total} avis")
    except Exception as e:  # noqa: BLE001 - on garde l'appli debout et on trace
        base.ecrire("UPDATE etablissements SET import_statut='erreur' WHERE id=?", (etab_id,))
        base.journaliser("import_erreur", None, f"{type(e).__name__}: {e}")


# ----------------------------------------------------------------- Collecte : enquête client + Rattrapage
def enregistrer_enquete(etab, note, commentaire, contact, consentement):
    eid = base.nouvel_id()
    now = base.maintenant()
    base.ecrire("INSERT INTO enquetes (id, etablissement_id, note, commentaire, contact, consentement, date) VALUES (?,?,?,?,?,?,?)",
                (eid, etab["id"], note, commentaire, contact if consentement else "", int(consentement), now))
    if commentaire.strip():
        (s, a, n), = ia.analyser([commentaire])
    else:
        s, a, n = None, [], []
    base.ecrire("INSERT INTO avis (id, etablissement_id, source, id_externe, auteur, note, texte, texte_fr, langue, date, sentiment, "
                "aspects, aspects_neg, statut) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (base.nouvel_id(), etab["id"], "enquete", eid, "Client (enquête)", note, commentaire, commentaire, "fr", now, s,
                 json.dumps(a, ensure_ascii=False), json.dumps(n, ensure_ascii=False), "interne"))
    if note <= 3:
        conseil, _ = ia.conseil_rattrapage(note, commentaire, etab["nom"])
        base.ecrire("INSERT INTO cas_rattrapage (id, etablissement_id, enquete_id, suggestion, cree_le, maj_le) VALUES (?,?,?,?,?,?)",
                    (base.nouvel_id(), etab["id"], eid, conseil, now, now))
        return "mecontent"
    return "content"


# ----------------------------------------------------------------- Analyste : tableau « Ce matin »
def _df(etab_id):
    lignes = base.lire("SELECT id, source, note, texte, date, sentiment, aspects_neg, repondu, reponse_date, statut "
                       "FROM avis WHERE etablissement_id=?", (etab_id,))
    d = pd.DataFrame(lignes)
    if d.empty:
        return d
    d["date"] = pd.to_datetime(d["date"])
    d["neg"] = d["aspects_neg"].apply(json.loads)
    return d


def tableau(etab_id):
    d = _df(etab_id)
    cas = base.lire("SELECT COUNT(*) n FROM cas_rattrapage WHERE etablissement_id=? AND statut IN ('ouvert','rappele')", (etab_id,), un=True)["n"]
    file_rep = base.lire("SELECT COUNT(*) n FROM avis WHERE etablissement_id=? AND statut IN ('a_traiter','brouillon')", (etab_id,), un=True)["n"]
    if d.empty:
        return {"vide": True, "cas_ouverts": cas, "a_repondre": file_rep}
    g = d[d["source"] == "google"]
    fin = d["date"].max()
    r30 = g[g["date"] > fin - pd.Timedelta(days=30)]
    p30 = g[(g["date"] <= fin - pd.Timedelta(days=30)) & (g["date"] > fin - pd.Timedelta(days=60))]
    rep = g[g["repondu"] == 1].dropna(subset=["reponse_date"])
    delai = None
    if len(rep):
        delai = float(((pd.to_datetime(rep["reponse_date"]) - rep["date"]).dt.total_seconds() / 3600).median())
    # pouls : 26 dernières semaines
    sem = g[g["date"] > fin - pd.Timedelta(weeks=26)].copy()
    sem["wk"] = sem["date"].dt.to_period("W-SUN").dt.start_time
    pouls = []
    for wk, x in sem.groupby("wk"):
        c = Counter(a for l in x["neg"] for a in l)
        top = c.most_common(1)[0] if c else (None, 0)
        q = None
        if top[0]:
            cand = x[x["neg"].apply(lambda l: top[0] in l)].sort_values("sentiment")
            if len(cand):
                q = cand.iloc[0]["texte"][:220]
        pouls.append({"du": wk.strftime("%d/%m"), "note": round(float(x["note"].mean()), 2), "n": int(len(x)),
                      "ko": int((x["note"] <= 2).sum()), "sujet": top[0], "nsujet": int(top[1]), "citation": q})
    # sujets : 4 dernières semaines contre les 4 d'avant
    r4 = g[g["date"] > fin - pd.Timedelta(weeks=4)]
    p4 = g[(g["date"] <= fin - pd.Timedelta(weeks=4)) & (g["date"] > fin - pd.Timedelta(weeks=8))]
    c_r, c_p = Counter(a for l in r4["neg"] for a in l), Counter(a for l in p4["neg"] for a in l)
    c_all = Counter(a for l in g["neg"] for a in l)
    sujets = [{"sujet": s, "total": n, "recents": c_r.get(s, 0), "avant": c_p.get(s, 0)} for s, n in c_all.most_common(11)]
    # décisions du jour
    dec = []
    if cas:
        dec.append({"niveau": "urgent", "titre": f"{cas} client{'s' if cas > 1 else ''} mécontent{'s' if cas > 1 else ''} à rappeler",
                    "texte": "Ils ont répondu à l'enquête avec une note basse. Les rappeler aujourd'hui évite un avis négatif public.",
                    "vers": "rattrapage"})
    if file_rep:
        dec.append({"niveau": "urgent" if file_rep > 5 else "normal", "titre": f"{file_rep} avis récent{'s' if file_rep > 1 else ''} sans réponse",
                    "texte": "Un avis sans réponse laisse croire que personne n'écoute. Les brouillons sont prêts dans la langue du client.",
                    "vers": "avis"})
    hausse = sorted([s for s in sujets if s["recents"] >= 3 and s["recents"] > s["avant"] * 1.3], key=lambda s: -(s["recents"] - s["avant"]))
    if hausse:
        s = hausse[0]
        dec.append({"niveau": "normal", "titre": f"« {s['sujet']} » revient plus souvent",
                    "texte": f"{s['recents']} phrases négatives ces 4 dernières semaines, contre {s['avant']} les 4 semaines d'avant.",
                    "vers": "analyse", "sujet": s["sujet"]})
    nouveaux = [s for s in sujets if s["recents"] >= 2 and s["avant"] == 0]
    if nouveaux:
        dec.append({"niveau": "nouveau", "titre": f"Nouveau sujet : « {nouveaux[0]['sujet']} »",
                    "texte": "Ce sujet n'apparaissait pas le mois d'avant.", "vers": "analyse", "sujet": nouveaux[0]["sujet"]})
    enq = d[d["source"] == "enquete"]
    return {
        "vide": False, "fin": fin.strftime("%d/%m/%Y"), "debut": g["date"].min().strftime("%d/%m/%Y") if len(g) else None,
        "kpi": {"note": round(float(g["note"].mean()), 2) if len(g) else None,
                "note30": round(float(r30["note"].mean()), 2) if len(r30) else None,
                "note30_avant": round(float(p30["note"].mean()), 2) if len(p30) else None,
                "avis": int(len(g)), "taux_reponse": round(float(g["repondu"].mean()) * 100, 1) if len(g) else None,
                "delai_h": None if delai is None else round(delai), "enquetes": int(len(enq)),
                "mecontents_pct": round(float((g["note"] <= 2).mean()) * 100, 1) if len(g) else None},
        "pouls": pouls, "sujets": sujets, "decisions": dec[:4], "cas_ouverts": cas, "a_repondre": file_rep,
    }


def file_reponses(etab_id):
    return base.lire("SELECT id, auteur, note, texte, texte_fr, langue, date, aspects_neg, statut, brouillon FROM avis "
                     "WHERE etablissement_id=? AND statut IN ('a_traiter','brouillon') ORDER BY note ASC, date DESC LIMIT 100", (etab_id,))


def question(etab, texte_question):
    lignes = base.lire("SELECT id, note, texte, date FROM avis WHERE etablissement_id=? AND length(texte) >= 15 ORDER BY date DESC LIMIT 3000",
                       (etab["id"],))
    if not lignes:
        return {"texte": "Aucun avis avec du texte pour l'instant. Connectez une fiche ou partagez l'enquête.", "sources": [], "mode": "aucun"}
    trouves = ia.chercher([l["texte"] for l in lignes], list(range(len(lignes))), texte_question)
    if not trouves:
        return {"texte": "Je n'ai pas trouvé d'avis qui parlent de ce sujet. Essayez avec d'autres mots.", "sources": [], "mode": "aucun"}
    sources = [lignes[i] for i, _ in trouves]
    texte, mode = ia.repondre_question(texte_question, sources, etab["nom"])
    return {"texte": texte, "mode": mode,
            "sources": [{"n": k, "date": s["date"][:10], "note": s["note"], "texte": s["texte"][:400]} for k, s in enumerate(sources, 1)]}
