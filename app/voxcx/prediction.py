"""Module prédictif : insatisfaction (note <= 3) et prévision de la note à partir du texte, avec explication SHAP.

Validation chronologique : on entraîne sur les avis les plus anciens et on teste sur les plus récents.
Le modèle retenu combine les mots de l'avis (TF-IDF) et le score du modèle de sentiment multilingue (XLM-R).
"""
import os
import time

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import f1_score, mean_absolute_error, r2_score, roc_auc_score

from voxcx.donnees import DOSSIER_APP, charger

MODELE = os.path.join(DOSSIER_APP, "data", "prediction.joblib")
SENTIMENTS = os.path.join(DOSSIER_APP, "data", "sentiments.csv")
SEUIL_INSATISFAIT = 3  # note <= 3 étoiles
COMBINE = "Régression logistique (TF-IDF + sentiment XLM-R)"
_SENT = {}
_VERROU_SENT = __import__("threading").Lock()


def _sentiment_modele():
    with _VERROU_SENT:
        if "m" not in _SENT:
            from voxcx.nlp import Sentiment

            _SENT["m"] = Sentiment()
    return _SENT["m"]


def _jeu():
    d = charger()
    d = d[d["a_texte"] & (d["texte"].str.len() >= 5)].copy()
    s = pd.read_csv(SENTIMENTS).set_index("id")["sentiment"]
    d["sentiment"] = d["id"].map(s).fillna(0.0)
    d["insatisfait"] = (d["note"] <= SEUIL_INSATISFAIT).astype(int)
    return d.sort_values("date").reset_index(drop=True)


def _vect():
    return TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=4000, sublinear_tf=True, strip_accents="unicode")


def _combiner(X, sent):
    return hstack([X, csr_matrix(np.asarray(sent, dtype=float).reshape(-1, 1))]).tocsr()


def entrainer():
    d = _jeu()
    coupure = int(len(d) * 0.75)
    app, test = d.iloc[:coupure], d.iloc[coupure:]
    v = _vect().fit(app["texte"])
    Xa, Xt = v.transform(app["texte"]), v.transform(test["texte"])
    Ca, Ct = _combiner(Xa, app["sentiment"]), _combiner(Xt, test["sentiment"])
    ya, yt = app["insatisfait"].values, test["insatisfait"].values

    resultats, probas = [], {}

    def evaluer(nom, modele, Xa_, Xt_, explicable):
        t0 = time.time()
        modele.fit(Xa_, ya)
        dt = time.time() - t0
        p = modele.predict_proba(Xt_)[:, 1]
        probas[nom] = p
        seuils = np.linspace(0.1, 0.9, 33)
        meilleur = max(seuils, key=lambda s: f1_score(yt, p >= s))
        resultats.append({"modele": nom, "f1": f1_score(yt, p >= meilleur), "auc": roc_auc_score(yt, p),
                          "temps_s": dt, "explicable": explicable, "seuil": float(meilleur)})

    evaluer("Régression logistique (TF-IDF)", LogisticRegression(C=3, class_weight="balanced", max_iter=2000), Xa, Xt, "Oui (SHAP)")
    evaluer("Forêt aléatoire (TF-IDF)", RandomForestClassifier(n_estimators=300, class_weight="balanced_subsample", random_state=0, n_jobs=-1), Xa, Xt, "Partielle")
    evaluer("Sentiment XLM-R seul (modèle local)", LogisticRegression(class_weight="balanced"), app[["sentiment"]].values, test[["sentiment"]].values, "Faible")
    evaluer(COMBINE, LogisticRegression(C=3, class_weight="balanced", max_iter=2000), Ca, Ct, "Oui (SHAP)")
    bench = pd.DataFrame(resultats)

    # régression de la note (1 à 5)
    ridge = Ridge(alpha=1.0).fit(Ca, app["note"])
    pred = np.clip(ridge.predict(Ct), 1, 5)
    reg = {"mae": float(mean_absolute_error(test["note"], pred)), "r2": float(r2_score(test["note"], pred)),
           "mae_reference": float(mean_absolute_error(test["note"], np.full(len(test), app["note"].mean())))}

    seuil = float(bench.loc[bench["modele"] == COMBINE, "seuil"].iloc[0])
    test_pred = test[["id", "hotel", "ville", "langue", "type_voyage", "groupe", "date", "note"]].copy()
    test_pred["insatisfait"] = yt
    test_pred["risque"] = probas[COMBINE]

    # modèle final réentraîné sur tout le jeu pour les prédictions de l'application
    vf = _vect().fit(d["texte"])
    Cf = _combiner(vf.transform(d["texte"]), d["sentiment"])
    paquet = {
        "vectoriseur": vf,
        "classifieur": LogisticRegression(C=3, class_weight="balanced", max_iter=2000).fit(Cf, d["insatisfait"]),
        "ridge": Ridge(alpha=1.0).fit(Cf, d["note"]),
        "fond": Cf[:300], "benchmark": bench, "regression": reg, "test_pred": test_pred, "seuil": seuil,
        "taille": {"app": len(app), "test": len(test), "positifs_test": int(yt.sum()), "date_coupure": str(test["date"].min().date())},
    }
    joblib.dump(paquet, MODELE)
    return paquet


def charger_modele():
    if os.path.exists(MODELE):
        p = joblib.load(MODELE)
        if p["benchmark"]["modele"].eq(COMBINE).any():
            return p
    return entrainer()


def _matrice(textes, p):
    sent = _sentiment_modele().scorer(list(textes))
    return _combiner(p["vectoriseur"].transform(textes), sent)


def predire(textes, paquet=None):
    p = paquet or charger_modele()
    X = _matrice(textes, p)
    return pd.DataFrame({
        "risque": p["classifieur"].predict_proba(X)[:, 1],
        "note_prevue": np.clip(p["ridge"].predict(X), 1, 5),
    })


def expliquer(texte, paquet=None, n=8):
    """Contribution (SHAP) de chaque mot au risque d'insatisfaction : positif = augmente le risque."""
    import shap

    p = paquet or charger_modele()
    X = _matrice([texte], p)
    explic = shap.LinearExplainer(p["classifieur"], p["fond"])
    vals = np.asarray(explic.shap_values(X)).reshape(-1)
    mots = list(p["vectoriseur"].get_feature_names_out()) + ["[sentiment du modèle XLM-R]"]
    actifs = set(X.nonzero()[1]) | {len(mots) - 1}
    return sorted(((mots[i], float(vals[i])) for i in actifs), key=lambda x: -abs(x[1]))[:n]


if __name__ == "__main__":
    pq = entrainer()
    print(pq["benchmark"].round(3).to_string(index=False))
    print("régression :", {k: round(v, 3) for k, v in pq["regression"].items()})
    print(pq["taille"])
