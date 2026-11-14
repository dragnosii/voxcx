import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from voxcx.nlp import decouper_phrases, detecter_aspects
from voxcx.priorisation import matrice_sentiment, table_priorites
from voxcx.ui import carte, entete, fr, nom_auteur, pied

avis, aspects = entete("Analyse des thèmes et des aspects", "Sentiment par aspect, calculé phrase par phrase avec un modèle multilingue local")
if aspects.empty:
    st.info("Le sentiment par aspect n'est pas encore calculé : lancez `python -m voxcx.nlp`.")
    st.stop()

# ---------- Carte de chaleur ----------
with carte("heatmap", "Carte de chaleur : score de sentiment par aspect et par hôtel", "De 0 (très négatif) à 10 (très positif)"):
    mat = matrice_sentiment(aspects)
    mat = mat.loc[mat.notna().sum(axis=1).sort_values(ascending=False).index]
    fig = go.Figure(go.Heatmap(z=mat.values, x=[c.replace("Kenzi ", "") for c in mat.columns], y=mat.index, zmin=5, zmax=9.5, xgap=4, ygap=4,
                               colorscale=[[0, "#C00000"], [0.35, "#E2A66B"], [0.6, "#9CC9B0"], [1, "#0F5132"]],
                               text=[[("" if pd.isna(v) else fr(v, 1)) for v in lig] for lig in mat.values], texttemplate="%{text}",
                               hovertemplate="%{y} · %{x} : %{z:.1f}/10<extra></extra>", colorbar=dict(title="/ 10")))
    fig.update_layout(height=440, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(autorange="reversed"), plot_bgcolor="white", font=dict(family="IBM Plex Sans"))
    st.plotly_chart(fig, width="stretch")
    pied("Moyenne du sentiment des phrases qui mentionnent l'aspect. Rouge = à corriger, vert = point fort.")
st.write("")

# ---------- Priorités + lecture d'un avis ----------
col_g, col_d = st.columns([3, 2], gap="medium")
with col_g, carte("priorites", "Problèmes classés par priorité", "Priorité = fréquence × gravité × tendance"):
    pri = table_priorites(aspects)
    if pri.empty:
        st.info("Pas assez de commentaires négatifs sur cette période.")
    else:
        aff = pri.rename(columns={"aspect": "Aspect", "mentions": "Mentions", "negatives": "Négatives", "part_negative": "Part négative", "gravite": "Gravité", "tendance": "Tendance (pts)", "priorite": "Priorité", "niveau": "Niveau"})
        aff["Part négative"] = (aff["Part négative"] * 100).round(1)
        aff["Gravité"] = aff["Gravité"].round(2)
        aff["Tendance (pts)"] = (aff["Tendance (pts)"] * 100).round(1)
        st.dataframe(aff, hide_index=True, width="stretch", height=430, column_config={
            "Priorité": st.column_config.ProgressColumn("Priorité", min_value=0, max_value=100, format="%d"),
            "Part négative": st.column_config.NumberColumn("Part négative", format="%.1f %%"),
            "Tendance (pts)": st.column_config.NumberColumn("Tendance (8 sem.)", format="%+.1f pts"),
        })
        pied("Priorité : nombre de phrases négatives × gravité moyenne × tendance sur 8 semaines, ramenée à 100 pour le thème le plus urgent.")

with col_d, carte("lecture", "Lecture d'un avis par l'IA"):
    avec_texte = avis[avis["a_texte"] & (avis["texte"].str.len() > 40)].sort_values("date", ascending=False).head(200)
    if avec_texte.empty:
        st.info("Aucun avis avec texte.")
    else:
        choix = st.selectbox("Choisir un avis récent", avec_texte.index, label_visibility="collapsed",
                             format_func=lambda i: f"{avec_texte.loc[i, 'hotel'].replace('Kenzi ', '')} · {avec_texte.loc[i, 'date']:%d/%m/%Y} · {avec_texte.loc[i, 'note']}/5 · {avec_texte.loc[i, 'texte'][:40]}…")
        r = avec_texte.loc[choix]
        sens_phr = aspects[aspects["id"] == r["id"]].drop_duplicates("phrase").set_index("phrase")
        morceaux = []
        for p in decouper_phrases(r["texte"]):
            asps = detecter_aspects(p)
            fond = "transparent"
            if p in sens_phr.index:
                lab = sens_phr.loc[p, "etiquette"]
                lab = lab.iloc[0] if isinstance(lab, pd.Series) else lab
                fond = {"positif": "#E6F2EC", "négatif": "#FBE9E7", "neutre": "#F1F3F7"}[lab]
            etiq = f' <span style="font-size:11px;color:#595959">[{", ".join(asps)}]</span>' if asps else ""
            morceaux.append(f'<span style="background:{fond};padding:2px 4px;border-radius:4px">{html.escape(p)}</span>{etiq}')
        st.markdown(f'<div class="note-bas">{r["hotel"]} · {r["date"]:%d/%m/%Y} · langue {r["langue"] or "n/d"} · {nom_auteur(r["auteur"])}</div><p style="line-height:2;font-size:15px">{" ".join(morceaux)}</p>', unsafe_allow_html=True)
        pied("Vert = positif, rouge = négatif, gris = neutre. Entre crochets : aspect détecté.")
st.write("")

# ---------- Que disent les clients ----------
with carte("avis_aspect", "Que disent les clients ?"):
    c1, c2, c3 = st.columns(3)
    asp_choisi = c1.selectbox("Aspect", sorted(aspects["aspect"].unique()), index=0)
    hotel_choisi = c2.selectbox("Hôtel", ["Tous"] + sorted(aspects["hotel"].unique()))
    sens = c3.radio("Sentiment", ["négatif", "positif"], horizontal=True)
    g = aspects[(aspects["aspect"] == asp_choisi) & (aspects["etiquette"] == sens)]
    if hotel_choisi != "Tous":
        g = g[g["hotel"] == hotel_choisi]
    st.write(f"**{len(g)} phrases** {sens}s sur « {asp_choisi} »")
    infos = avis.set_index("id")
    for r in g.sort_values("date", ascending=False).head(6).itertuples():
        a = infos.loc[r.id] if r.id in infos.index else None
        entete_txt = f"{r.hotel} · {r.date:%d/%m/%Y}" + (f" · {a['note']}/5 · {nom_auteur(a['auteur'])}" if a is not None else "")
        st.markdown(f'<div class="source"><b>{entete_txt}</b><br>« {html.escape(r.phrase)} »</div>', unsafe_allow_html=True)
st.write("")

# ---------- Fiabilité ----------
with carte("fiabilite", "Fiabilité du modèle", "Comparaison avec les notes détaillées que les clients donnent eux-mêmes sur Google"):
    corr = []
    for asp, col in (("Chambre et literie", "note_chambres"), ("Personnel et service", "note_service"), ("Emplacement", "note_emplacement")):
        x = aspects[aspects["aspect"] == asp].groupby("id")["score"].mean().rename("modele").to_frame().join(avis.set_index("id")[col]).dropna()
        if len(x) > 30:
            corr.append({"Aspect": asp, "Avis comparés": len(x), "Corrélation de rang (Spearman)": round(x["modele"].corr(x[col], method="spearman"), 2)})
    if corr:
        st.dataframe(pd.DataFrame(corr), hide_index=True, width="stretch")
    t = avis[avis["a_texte"] & avis["sentiment"].notna()]
    if len(t):
        st.write(f"Sentiment global vs note Google : corrélation de rang = **{fr(t['sentiment'].corr(t['note'], method='spearman'), 2)}** sur {fr(len(t))} avis.")
    pied("Limites : modèle généraliste (pas entraîné sur l'hôtellerie), ironie et nuances comme « moyen » parfois mal classées ; lexique d'aspects en première version.")
