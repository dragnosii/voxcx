"""VoxCX : plateforme d'écoute client assistée par IA (groupe hôtelier Kenzi).

Lancement :   .venv\\Scripts\\streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="VoxCX · Écoute client", layout="wide", initial_sidebar_state="expanded")

from voxcx.assistant import mode_en_ligne_disponible  # noqa: E402
from voxcx.ui import LOGO, appliquer_charte  # noqa: E402

appliquer_charte()

pages = [
    st.Page("vues/direction.py", title="1  Direction", default=True),
    st.Page("vues/themes.py", title="2  Thèmes et aspects"),
    st.Page("vues/assistant.py", title="3  Pose ta question"),
    st.Page("vues/predictif.py", title="4  Prédictif"),
    st.Page("vues/plan.py", title="5  Plan d'actions"),
]
navigation = st.navigation(pages, position="hidden")

with st.sidebar:
    st.markdown(f'<div class="marque">{LOGO}<div><div class="n">VoxCX</div><div class="s">Écoute client · IA</div></div></div>', unsafe_allow_html=True)
    for p in pages:
        st.page_link(p)

    en_ligne = mode_en_ligne_disponible()
    st.markdown('<div class="mode-ia"><div class="t">Mode IA</div></div>', unsafe_allow_html=True)
    en_ligne_choisi = st.toggle("En ligne · Claude", value=en_ligne, key="choix_mode")
    st.session_state["mode_ia"] = "en ligne" if en_ligne_choisi and en_ligne else "local"
    if en_ligne_choisi and not en_ligne:
        st.caption("Aucune clé d'API trouvée : mode local gratuit utilisé.")
    elif en_ligne_choisi:
        st.caption("Mode en ligne actif. Bascule automatique en local si le réseau ou l'API tombe.")
    else:
        st.caption("Mode local gratuit : aucun envoi de données hors de l'ordinateur.")
    st.markdown('<div class="pied-menu">Jeu de données : avis publics Google Maps de 7 hôtels Kenzi (Casablanca, Marrakech, Agadir, Tanger), collectés le 16/10/2026.</div>', unsafe_allow_html=True)

navigation.run()
