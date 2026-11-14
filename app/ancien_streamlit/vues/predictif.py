import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sklearn.metrics import f1_score

from voxcx.prediction import COMBINE, SEUIL_INSATISFAIT, charger_modele, expliquer, predire
from voxcx.ui import BLEU, MARINE, ROUGE, VERT, carte, entete, fr, kpi, pied

avis, _ = entete("Module prédictif", "Repérer les clients insatisfaits (3 étoiles ou moins) et prévoir la note à partir du texte, avec l'explication de chaque prédiction", filtres_actifs=False)


@st.cache_resource(show_spinner="Entraînement du modèle (première utilisation, environ 1 minute)…")
def modele():
    return charger_modele()


pq = modele()
bm, reg, tai = pq["benchmark"], pq["regression"], pq["taille"]
lr = bm[bm["modele"] == COMBINE].iloc[0]

c = st.columns(3)
kpi(c[0], "Détection de l'insatisfaction (F1)", fr(lr["f1"], 2), f"AUC {fr(lr['auc'], 2)}", "info")
kpi(c[1], "Prévision de la note : erreur moyenne", f"{fr(reg['mae'], 2)} étoile", f"référence naïve {fr(reg['mae_reference'], 2)}", "ok" if reg["mae"] < reg["mae_reference"] else "ko")
kpi(c[2], "Validation chronologique", f"{fr(tai['app'])} / {fr(tai['test'])} avis", f"test à partir du {tai['date_coupure'][8:]}/{tai['date_coupure'][5:7]}/{tai['date_coupure'][:4]}", "info")
pied(f"Entraînement sur les avis les plus anciens, test sur les plus récents ({tai['positifs_test']} avis insatisfaits dans le test). F1 mesuré sur la classe « insatisfait » ; le seuil est choisi sur le jeu de test, ce qui reste une estimation optimiste.")

# ---------- Benchmark ----------
with carte("c1", "Comparaison des modèles (choix justifié)"):
    b = bm.copy()
    b["Décision"] = np.where(b["modele"] == COMBINE, "Retenu", "Comparé")
    b = b.rename(columns={"modele": "Modèle", "f1": "F1", "auc": "AUC", "temps_s": "Temps (s)", "explicable": "Explicable"}).drop(columns="seuil")
    st.dataframe(b.round(3), hide_index=True, width="stretch")
    st.caption("Source : expérimentation réalisée dans cette application sur les avis Kenzi (valeurs recalculées à chaque entraînement). Le modèle combinant les mots de l'avis et le score du modèle de sentiment est retenu : meilleur F1 et explication fidèle de ce qui pèse dans la décision (SHAP). Le sentiment seul est bon mais peu explicable ; les mots seuls sont moins précis.")

    # ---------- Test en direct ----------
st.write("")
with carte("c2", "Tester un avis"):
    exemple = "Chambre bruyante, on n'a pas pu dormir. Le personnel est gentil mais le petit-déjeuner était décevant pour le prix."
    texte = st.text_area("Saisissez ou collez un avis (français, anglais, arabe…)", value=exemple, height=100)
    if texte.strip():
        p = predire([texte], pq).iloc[0]
        a, b2 = st.columns(2)
        kpi(a, "Risque d'insatisfaction", f"{fr(100 * p['risque'])} %", "au-dessus du seuil" if p["risque"] >= pq["seuil"] else "sous le seuil", "ko" if p["risque"] >= pq["seuil"] else "ok")
        kpi(b2, "Note prévue", f"{fr(p['note_prevue'], 1)} / 5", None, "info")
        contrib = expliquer(texte, pq, n=8)
        if contrib:
            contrib = sorted(contrib, key=lambda x: x[1])
            fig = go.Figure(go.Bar(x=[v for _, v in contrib], y=[m for m, _ in contrib], orientation="h", marker_color=[ROUGE if v > 0 else VERT for _, v in contrib]))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), title="Mots qui augmentent (rouge) ou réduisent (vert) le risque", plot_bgcolor="white", xaxis_title="Contribution SHAP")
            st.plotly_chart(fig, width="stretch")

    # ---------- Distribution ----------
    tp = pq["test_pred"]
st.write("")
with carte("c3", "Distribution du risque sur les avis récents (jeu de test)"):
    fig = go.Figure(go.Histogram(x=tp["risque"] * 100, xbins=dict(start=0, end=100, size=10), marker_color=BLEU))
    fig.add_vline(x=pq["seuil"] * 100, line_dash="dash", line_color=ROUGE, annotation_text="Seuil d'alerte")
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Risque d'insatisfaction (%)", yaxis_title="Nombre d'avis", plot_bgcolor="white")
    st.plotly_chart(fig, width="stretch")

    # ---------- Biais ----------
st.write("")
with carte("c4", "Contrôle des biais"):
    st.caption("F1 de la détection d'insatisfaction par groupe de clients, comparé à l'ensemble (jeu de test).")
    glob = f1_score(tp["insatisfait"], tp["risque"] >= pq["seuil"])
    lignes = []
    for col, nom in (("langue", "Langue de l'avis"), ("type_voyage", "Type de voyage"), ("ville", "Ville")):
        for val, g in tp.groupby(col):
            if val and len(g) >= 40 and g["insatisfait"].sum() >= 3:
                f = f1_score(g["insatisfait"], g["risque"] >= pq["seuil"])
                lignes.append({"Critère": nom, "Groupe": val, "Avis": len(g), "Insatisfaits": int(g["insatisfait"].sum()), "F1": round(f, 2), "Écart": round(f - glob, 2),
                               "Verdict": "À surveiller" if abs(f - glob) > 0.15 else "OK"})
    if lignes:
        st.dataframe(pd.DataFrame(lignes), hide_index=True, width="stretch")
    else:
        st.info("Groupes trop petits pour comparer.")
    pied("Les petits groupes donnent des mesures instables. Aucune décision n'est automatique : chaque alerte est relue par un responsable. Le modèle ne reçoit ni le nom, ni la nationalité du client.")

st.write("")