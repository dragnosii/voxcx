import html

import pandas as pd
import streamlit as st

from voxcx.assistant import Assistant, journaliser
from voxcx.ui import carte, entete, nom_auteur, pied



@st.cache_resource(show_spinner="Chargement du moteur de recherche local…")
def moteur():
    return Assistant()


avis, _ = entete("Pose ta question", "Un assistant qui répond uniquement à partir des avis, avec les sources citées (recherche sémantique + génération)")
bot = moteur()

c1, c2, c3 = st.columns([2, 2, 2])
hotel = c1.selectbox("Hôtel", ["Tous"] + sorted(avis["hotel"].unique()))
negatifs = c2.checkbox("Avis insatisfaits seulement (3 étoiles ou moins)")
k = c3.slider("Nombre d'avis consultés", 4, 15, 8)

if "historique" not in st.session_state:
    st.session_state["historique"] = []

suggestions = ["Pourquoi les clients se plaignent-ils du bruit ?", "Quels sont les points forts du Kenzi Menara Palace ?",
               "Que disent les clients du petit-déjeuner ?", "Y a-t-il des problèmes de propreté ?"]
cols = st.columns(len(suggestions))
question = None
for col, s in zip(cols, suggestions):
    if col.button(s, width="stretch"):
        question = s
saisie = st.chat_input("Posez une question sur vos avis clients…")
question = saisie or question

if question:
    with st.spinner("Recherche dans les avis…"):
        rep = bot.repondre(question, k=k, mode=st.session_state.get("mode_ia", "local"), hotel=None if hotel == "Tous" else hotel,
                           depuis=avis["date"].min(), negatifs_seulement=negatifs)
    st.session_state["historique"].append({"question": question, "rep": rep})

for i, tour in enumerate(reversed(st.session_state["historique"])):
    with st.chat_message("user"):
        st.write(tour["question"])
    with st.chat_message("assistant"):
        rep = tour["rep"]
        st.markdown(f'<span class="note-bas">Mode : {rep["mode"]} · confiance {rep["confiance"]} · {len(rep["sources"])} sources · {rep["duree"]:.1f} s</span>', unsafe_allow_html=True)
        st.write(rep["texte"])
        if not rep["sources"].empty:
            with st.expander("Sources utilisées"):
                for j, r in enumerate(rep["sources"].itertuples(), 1):
                    st.markdown(f'<div class="source"><b>[{j}] {r.hotel}</b> · {r.date:%d/%m/%Y} · {r.note}/5 · {nom_auteur(r.auteur)} · similarité {r.similarite:.2f}<br>« {html.escape(r.texte_fr[:500])} »</div>', unsafe_allow_html=True)
        b1, b2, _ = st.columns([1, 1, 4])
        if b1.button("Réponse correcte", key=f"ok{i}"):
            journaliser("validation", "Humain", f"{tour['question']} | réponse jugée correcte")
            st.success("Enregistré dans le journal de gouvernance.")
        if b2.button("Signaler une erreur", key=f"ko{i}"):
            journaliser("signalement", "Humain", f"{tour['question']} | erreur signalée")
            st.warning("Signalement enregistré.")

pied("Garde-fous : l'assistant refuse de répondre sans avis pertinent, ne génère rien en mode local, et chaque échange est consigné dans le journal de gouvernance.")
