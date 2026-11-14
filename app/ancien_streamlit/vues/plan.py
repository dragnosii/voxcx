import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sklearn.linear_model import Ridge

from voxcx.assistant import JOURNAL, journaliser
from voxcx.donnees import DOSSIER_APP
from voxcx.priorisation import table_priorites
from voxcx.ui import BLEU, BRUN, GRIS, MARINE, ROUGE, VERT, carte, entete, fr, kpi, pied

PLAN = os.path.join(DOSSIER_APP, "data", "plan_actions.csv")
EXPERIENCE = os.path.join(DOSSIER_APP, "data", "experience_chronometree.csv")

avis, aspects = entete("Plan d'actions et simulateur", "De l'analyse à la décision : prioriser, simuler, valider, suivre")
if aspects.empty:
    st.info("Le sentiment par aspect n'est pas encore calculé : lancez `python -m voxcx.nlp`.")
    st.stop()

# Actions types proposées (mode local) : pour chaque aspect, une action, un porteur, un coût indicatif et un indicateur
ACTIONS = {
    "Chambre et literie": ("Plan de rénovation et contrôle qualité des chambres les plus citées", "Direction technique", 6, "Part de commentaires négatifs sur les chambres -30 %"),
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

pri = table_priorites(aspects)
if pri.empty:
    st.info("Pas assez de commentaires négatifs sur cette période.")
    st.stop()

# ---------- Matrice impact x effort ----------
with carte("c1", "Matrice impact × effort"):
    pri["effort"] = pri["aspect"].map(lambda a: ACTIONS.get(a, ("", "", 3, ""))[2])
    fig = go.Figure()
    fig.add_shape(type="line", x0=3, x1=3, y0=0, y1=105, line=dict(color="#8E99AB", dash="dot"))
    fig.add_shape(type="line", x0=0.5, x1=5.5, y0=50, y1=50, line=dict(color="#8E99AB", dash="dot"))
    jitter = np.random.default_rng(1).uniform(-0.18, 0.18, len(pri))
    fig.add_trace(go.Scatter(x=pri["effort"] + jitter, y=pri["priorite"], mode="markers+text", text=pri["aspect"], textposition="top center",
                             marker=dict(size=(pri["negatives"] ** 0.5) * 4 + 8, color=[ROUGE if p >= 66 else BRUN if p >= 33 else BLEU for p in pri["priorite"]], opacity=0.8),
                             hovertemplate="%{text}<br>Effort %{x:.0f}/5 · Priorité %{y}<extra></extra>"))
    for x, y, t in ((1.6, 103, "Gains rapides"), (4.4, 103, "Projets structurants"), (1.6, 3, "Améliorations marginales"), (4.4, 3, "À éviter ou à reporter")):
        fig.add_annotation(x=x, y=y, text=f"<b>{t}</b>", showarrow=False, font=dict(color=GRIS, size=12))
    fig.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(range=[0.5, 5.5], title="Effort de mise en œuvre (1 faible, 5 élevé)", dtick=1), yaxis=dict(range=[-5, 112], title="Priorité (impact attendu)"), plot_bgcolor="white", showlegend=False)
    st.plotly_chart(fig, width="stretch")
    st.caption("Effort : estimation de départ par type d'action, à ajuster avec les directions concernées.")

    # ---------- Simulateur ----------
st.write("")
with carte("c2", "Simulateur « et si ? »"):
    d = avis[avis["a_texte"]].copy()
    neg = aspects[aspects["etiquette"] == "négatif"].groupby(["id", "aspect"]).size().unstack(fill_value=0).clip(upper=1)
    X = d.set_index("id")[[]].join(neg).fillna(0)
    y = d.set_index("id")["note"]
    coef = pd.Series(Ridge(alpha=5).fit(X, y).coef_, index=X.columns) if len(X) > 100 else pd.Series(dtype=float)
    a1, a2, a3 = st.columns(3)
    asp = a1.selectbox("Aspect corrigé", list(pri["aspect"]))
    part = a2.slider("Part des commentaires négatifs corrigés", 10, 100, 50, step=10, format="%d %%")
    cout = a3.number_input("Coût de l'action (DH)", min_value=0, value=180000, step=10000)
    if asp in coef.index:
        p_neg = X[asp].mean()
        gain = -coef[asp] * p_neg * part / 100  # coefficient négatif : un commentaire négatif coûte des étoiles
        n_evites = int(X[asp].sum() * part / 100)
        k = st.columns(3)
        kpi(k[0], "Gain de note estimé", f"+{fr(max(gain, 0), 3)} étoile", f"impact moyen d'un commentaire négatif : {fr(coef[asp], 2)} étoile", "ok")
        kpi(k[1], "Commentaires négatifs évités", fr(n_evites), f"sur {fr(int(X[asp].sum()))} observés", "info")
        kpi(k[2], "Coût par commentaire négatif évité", f"{fr(cout / max(n_evites, 1))} DH", None, "mid")
        st.caption("Estimation par régression de la note sur la présence de commentaires négatifs par aspect (corrélation, pas causalité). Hypothèses modifiables ci-dessus ; à valider par la direction.")

    # ---------- Plan d'actions ----------
st.write("")
with carte("c3", "Plan d'actions (méthode QQOQCCP)"):
    if st.button("Proposer des actions à partir des priorités"):
        lignes = []
        for r in pri.head(5).itertuples():
            quoi, qui, effort, kpi_cible = ACTIONS.get(r.aspect, (f"Traiter « {r.aspect} »", "À définir", 3, ""))
            hot = aspects[(aspects["aspect"] == r.aspect) & (aspects["etiquette"] == "négatif")]["hotel"].value_counts().index[0]
            lignes.append({"Quoi": quoi, "Pourquoi": f"{r.aspect} : priorité {r.priorite}/100", "Qui": qui, "Où": hot, "Quand": "T+3 mois", "Coût (DH)": effort * 30000, "KPI cible": kpi_cible, "Statut": "À valider"})
        pd.DataFrame(lignes).to_csv(PLAN, index=False, encoding="utf-8-sig")
        journaliser("recommandation", "IA", f"{len(lignes)} actions proposées")
        st.rerun()
    if os.path.exists(PLAN):
        plan = pd.read_csv(PLAN)
        edite = st.data_editor(plan, hide_index=True, width="stretch", num_rows="dynamic", column_config={
            "Statut": st.column_config.SelectboxColumn("Statut", options=["À valider", "Validée", "En cours", "Refusée", "Terminée"]),
            "Coût (DH)": st.column_config.NumberColumn("Coût (DH)", format="%d"),
        })
        if st.button("Enregistrer les décisions"):
            for i, r in edite.iterrows():
                if i < len(plan) and r["Statut"] != plan.loc[i, "Statut"]:
                    journaliser("décision", "Humain", f"{r['Quoi']} : {plan.loc[i, 'Statut']} → {r['Statut']}")
            edite.to_csv(PLAN, index=False, encoding="utf-8-sig")
            st.success("Plan enregistré, décisions inscrites dans le journal de gouvernance.")
    else:
        st.info("Aucun plan pour l'instant. Cliquez sur « Proposer des actions » : l'IA propose, un responsable valide.")

    # ---------- Expérience chronométrée ----------
st.write("")
with carte("c4", "Expérience chronométrée : l'outil fait-il gagner du temps ?"):
    st.caption("Protocole : chaque testeur analyse le même lot d'avis (par exemple 100) d'abord à la main, puis avec la plateforme. Saisissez les temps relevés.")
    base = pd.read_csv(EXPERIENCE) if os.path.exists(EXPERIENCE) else pd.DataFrame({"Testeur": ["Testeur 1", "Testeur 2", "Testeur 3"], "Avis analysés": [100, 100, 100], "Minutes à la main": [np.nan] * 3, "Minutes avec l'outil": [np.nan] * 3})
    exp = st.data_editor(base, hide_index=True, num_rows="dynamic", width="stretch", key="exp")
    if st.button("Enregistrer l'expérience"):
        exp.to_csv(EXPERIENCE, index=False, encoding="utf-8-sig")
        journaliser("expérience", "Humain", f"{len(exp)} testeurs enregistrés")
    e = exp.dropna()
    if len(e) >= 1:
        m, o = e["Minutes à la main"].mean(), e["Minutes avec l'outil"].mean()
        k = st.columns(3)
        kpi(k[0], "À la main (moyenne)", f"{fr(m, 0)} min", None, "info")
        kpi(k[1], "Avec la plateforme (moyenne)", f"{fr(o, 0)} min", None, "info")
        kpi(k[2], "Temps gagné", f"{fr(100 * (1 - o / m), 0)} %" if m else "n/d", f"sur {len(e)} testeur(s)", "ok")
    else:
        st.caption("Aucune mesure saisie : les chiffres de cette section viendront de la vraie expérience, jamais d'une valeur inventée.")

    # ---------- Journal ----------
st.write("")
with carte("c5", "Journal de gouvernance de l'IA"):
    if os.path.exists(JOURNAL):
        j = pd.read_csv(JOURNAL).sort_values("date", ascending=False)
        st.dataframe(j.head(50), hide_index=True, width="stretch")
    else:
        st.caption("Le journal se remplit au fil des questions, recommandations et décisions.")
    pied("Chaque action proposée par l'IA doit être validée par un humain. Le journal conserve qui a proposé, qui a décidé et quand.")

st.write("")