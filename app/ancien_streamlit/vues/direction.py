import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

from voxcx.assistant import journaliser
from voxcx.briefing import faits
from voxcx.priorisation import alertes, table_priorites
from voxcx.ui import BLEU, BRUN, GRIS, MARINE, ROUGE, VERT, alerte, carte, entete, fr, kpi, nom_auteur, pied

avis, aspects = entete("Tableau de bord Direction", "Kenzi Hotels · {hotels} hôtels · {avis} avis du {debut} au {fin}")
if avis.empty:
    st.warning("Aucun avis pour ces filtres.")
    st.stop()

# ---------- Briefing ----------
constats = faits(avis, aspects)
with st.container(border=True, key="brief_carte"):
    st.markdown(f'<div class="brief-t"><b>Briefing du lundi · semaine du {avis["date"].max():%d/%m/%Y}</b><span>Généré automatiquement à partir de {fr(len(avis))} avis · à valider par un responsable</span></div>', unsafe_allow_html=True)
    g, d = st.columns([2.3, 1], gap="large")
    with g:
        if not constats:
            st.info("Pas assez d'avis pour un briefing sur cette période.")
        for i, c in enumerate(constats, 1):
            couleur = {"ok": VERT, "ko": ROUGE, "info": BLEU}.get(c["ton"], BLEU)
            st.markdown(f'<div style="display:flex;gap:12px;align-items:flex-start;font-size:15px;line-height:1.5;margin-top:10px"><span style="flex:0 0 22px;height:22px;border-radius:50%;background:{couleur};color:#fff;text-align:center;font-weight:700;font-size:12px;line-height:22px;margin-top:2px">{i}</span><span>{c["texte"]} <span style="display:inline-block;margin-left:4px;padding:2px 8px;border-radius:999px;background:#EAF1FA;color:{MARINE};font-size:12px;font-weight:600">{len(c["sources"])} avis cités</span></span></div>', unsafe_allow_html=True)
            with st.expander("Voir les avis sources"):
                for r in c["sources"].itertuples():
                    st.markdown(f'<div class="source"><b>{r.hotel}</b> · {r.date:%d/%m/%Y} · {r.note}/5 · {nom_auteur(r.auteur)}<br>{r.texte_fr[:400] or "(note sans commentaire)"}</div>', unsafe_allow_html=True)
    with d:
        st.write("")
        if st.button("Valider le briefing", type="primary", width="stretch"):
            journaliser("validation", "Humain", "Briefing validé")
            st.success("Briefing validé et inscrit dans le journal.")
        st.markdown('<div class="note-bas" style="margin-top:8px">Chaque phrase est reliée à des avis réels. Aucune recommandation n\'est appliquée sans validation humaine.</div>', unsafe_allow_html=True)
st.write("")

# ---------- Indicateurs ----------
fin = avis["date"].max()
r30 = avis[avis["date"] > fin - pd.Timedelta(days=30)]
p30 = avis[(avis["date"] <= fin - pd.Timedelta(days=30)) & (avis["date"] > fin - pd.Timedelta(days=60))]
nps = lambda x: 100 * ((x["note"] == 5).mean() - (x["note"] <= 3).mean())
pri = table_priorites(aspects)
nb_critiques = int((pri["niveau"] == "Élevé").sum()) if not pri.empty else 0

c = st.columns(5)
dn = (r30["note"].mean() - p30["note"].mean()) if len(r30) and len(p30) else None
kpi(c[0], "Note moyenne", f"{fr(avis['note'].mean(), 2)}<span style='font-size:15px;font-weight:500;color:{GRIS}'> / 5</span>", None if dn is None else f"{'+' if dn >= 0 else ''}{fr(dn, 2)} sur 30 j", "ok" if (dn or 0) >= 0 else "ko")
dnps = (nps(r30) - nps(p30)) if len(r30) and len(p30) else None
kpi(c[1], "NPS estimé *", f"{'+' if nps(avis) >= 0 else ''}{fr(nps(avis))}", None if dnps is None else f"{'+' if dnps >= 0 else ''}{fr(dnps)} pts sur 30 j", "ok" if (dnps or 0) >= 0 else "ko")
kpi(c[2], "Taux de plaintes (1-2 étoiles)", f"{fr(100 * (avis['note'] <= 2).mean(), 1)}<span style='font-size:15px;font-weight:500;color:{GRIS}'> %</span>", None, "info")
kpi(c[3], "Réponses de l'hôtel", f"{fr(100 * avis['reponse'].mean())}<span style='font-size:15px;font-weight:500;color:{GRIS}'> %</span>", f"délai médian {fr(avis['delai_reponse_h'].median())} h", "info")
kpi(c[4], "Thèmes à priorité élevée", str(nb_critiques), "à traiter en premier" if nb_critiques else "aucun", "ko" if nb_critiques else "ok")
pied("* NPS estimé à partir des notes Google : 5 étoiles = promoteur, 3 étoiles ou moins = détracteur (approximation, ce n'est pas le NPS d'une enquête).")
st.write("")

# ---------- Avant / après + alertes ----------
col_g, col_d = st.columns([2, 1], gap="medium")
with col_g, carte("avant_apres", "Note moyenne : avant / après une action", "Note sur 5, par mois"):
    g1, g2 = st.columns([3, 1], gap="medium")
    with g2:
        cible = st.date_input("Date de l'action testée", value=pd.Timestamp("2026-07-16").date(), min_value=avis["date"].min().date(), max_value=avis["date"].max().date(), format="DD/MM/YYYY")
        coupure = pd.Timestamp(cible)
        avant, apres = avis[avis["date"] < coupure], avis[avis["date"] >= coupure]
        if len(avant) > 20 and len(apres) > 20:
            t, p = stats.ttest_ind(apres["note"], avant["note"], equal_var=False)
            dd = apres["note"].mean() - avant["note"].mean()
            st.metric("Avant", f"{fr(avant['note'].mean(), 2)} / 5", f"{fr(len(avant))} avis", delta_color="off")
            st.metric("Après", f"{fr(apres['note'].mean(), 2)} / 5", f"{'+' if dd >= 0 else ''}{fr(dd, 2)}")
            st.markdown(f"**Test de Welch** : p = {fr(p, 3)} → " + ("écart significatif" if p < 0.05 else "écart non significatif"))
        pied("Association observée, pas causalité : saison, tarifs et clientèle varient aussi.")
    with g1:
        m = avis.groupby("mois", as_index=False).agg(note=("note", "mean"), avis=("id", "count"))
        m["date"] = pd.to_datetime(m["mois"] + "-15")
        fig = go.Figure()
        fig.add_vrect(x0=coupure, x1=m["date"].max() + pd.Timedelta(days=20), fillcolor=VERT, opacity=0.07, line_width=0)
        fig.add_trace(go.Scatter(x=m["date"], y=m["note"], mode="lines+markers", line=dict(color=MARINE, width=3), marker=dict(size=7), name="Note moyenne",
                                 hovertemplate="%{x|%m/%Y} : %{y:.2f}<extra></extra>"))
        fig.add_vline(x=coupure, line_dash="dash", line_color=BRUN)
        fig.add_annotation(x=coupure, y=1, yref="paper", text=f"Action testée : {coupure:%d/%m/%Y}", showarrow=False, font=dict(color=BRUN, size=12), yshift=12, xanchor="right", xshift=-6)
        fig.update_layout(height=330, margin=dict(l=10, r=10, t=30, b=10), yaxis=dict(range=[3.8, 5], title=None, gridcolor="#E3E8F0"), xaxis=dict(tickformat="%m/%Y", gridcolor="#E3E8F0"), plot_bgcolor="white", font=dict(family="IBM Plex Sans"))
        st.plotly_chart(fig, width="stretch")

with col_d, carte("alertes", "Alertes"):
    al = alertes(aspects, avis)
    if al.empty:
        st.success("Aucune hausse de plaintes détectée sur les 8 dernières semaines.")
    for r in al.head(4).itertuples():
        alerte(r.niveau, f"<b>{r.hotel}</b> · {r.texte}", "ko" if r.niveau == "Critique" else "mid")
    if not pri.empty:
        best = aspects[aspects["etiquette"] == "positif"].groupby(["hotel", "aspect"]).size().sort_values(ascending=False)
        if not best.empty:
            (h_best, a_best), n_best = best.index[0], int(best.iloc[0])
            alerte("Point fort", f"<b>{h_best}</b> · {a_best} : {n_best} commentaires positifs.", "ok")
st.write("")

# ---------- Benchmark + sentiments ----------
col_a, col_b = st.columns(2, gap="medium")
with col_a, carte("benchmark", "Benchmark entre hôtels"):
    h = avis.groupby("hotel", as_index=False).agg(note=("note", "mean"), avis=("id", "count")).sort_values("note")
    fig = px.bar(h, x="note", y="hotel", orientation="h", text=h["note"].map(lambda x: fr(x, 2)), color="note",
                 color_continuous_scale=[ROUGE, BRUN, BLEU, VERT], range_color=[4.2, 4.85])
    fig.update_traces(marker_cornerradius=6)
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(range=[3.8, 5], title="Note moyenne / 5", gridcolor="#E3E8F0"), yaxis_title=None, coloraxis_showscale=False, plot_bgcolor="white", font=dict(family="IBM Plex Sans"))
    st.plotly_chart(fig, width="stretch")
    worst = h.iloc[0]
    pied(f"{worst['hotel']} a la note la plus basse du groupe ({fr(worst['note'], 2)} / 5).")

with col_b, carte("sentiments", "Sentiment des commentaires"):
    t = avis[avis["a_texte"] & avis["etiquette"].notna()]
    if t.empty:
        st.info("Le sentiment n'est pas encore calculé : lancez `python -m voxcx.nlp`.")
    else:
        rep = t.groupby(["hotel", "etiquette"]).size().unstack(fill_value=0)
        rep = rep.div(rep.sum(axis=1), axis=0) * 100
        fig = go.Figure()
        for lab, col in (("positif", VERT), ("neutre", "#8E99AB"), ("négatif", ROUGE)):
            if lab in rep:
                fig.add_bar(y=rep.index, x=rep[lab], name=lab.capitalize(), orientation="h", marker_color=col, text=rep[lab].round(0).astype(int).astype(str) + " %", textposition="inside")
        fig.update_layout(barmode="stack", height=340, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="% des commentaires", plot_bgcolor="white", legend=dict(orientation="h", y=1.12), font=dict(family="IBM Plex Sans"))
        st.plotly_chart(fig, width="stretch")
        a_pos = aspects[aspects["etiquette"] == "positif"]["aspect"].value_counts().head(4).index.tolist()
        a_neg = aspects[aspects["etiquette"] == "négatif"]["aspect"].value_counts().head(4).index.tolist()
        pastilles = "".join(f'<span style="display:inline-block;margin:0 6px 6px 0;padding:5px 12px;border-radius:999px;font-size:13px;font-weight:500;background:#E6F2EC;color:{VERT}">{a}</span>' for a in a_pos)
        pastilles += "".join(f'<span style="display:inline-block;margin:0 6px 6px 0;padding:5px 12px;border-radius:999px;font-size:13px;font-weight:500;background:#FBE9E7;color:{ROUGE}">{a}</span>' for a in a_neg)
        st.markdown(f'<div style="font-size:14px;font-weight:600;color:{MARINE};margin-bottom:6px">Ce qui fait la différence</div>{pastilles}', unsafe_allow_html=True)

st.write("")
pied("Source des données : avis publics Google Maps des fiches des hôtels Kenzi (collecte automatisée, 16/10/2026). Valeurs calculées sur les filtres sélectionnés.")
