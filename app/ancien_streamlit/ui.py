"""Éléments communs à toutes les pages : charte (identique à la maquette), chargement des données, filtres en en-tête, cartes."""
import io
import os
from contextlib import contextmanager

import pandas as pd
import streamlit as st

from voxcx.donnees import DATE_FENETRE_COMMUNE, charger

MARINE, BLEU, BRUN, VERT, ROUGE, GRIS = "#1F3864", "#2E74B5", "#8B4513", "#0F5132", "#C00000", "#595959"
LIGNE = "#DDE3EC"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stApp, button, input, textarea, select {{ font-family: 'IBM Plex Sans', system-ui, sans-serif !important; }}
.stApp {{ background: #F3F5F9; }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding: 1.6rem 2.2rem 3rem 2.2rem; max-width: 1500px; }}
h1, h2, h3 {{ color: {MARINE}; font-family: 'IBM Plex Sans', sans-serif !important; }}
.titre {{ margin: 0; padding: 0; font-size: 28px; font-weight: 700; color: {MARINE}; line-height: 1.2; }}
.sous {{ font-size: 14px; color: {GRIS}; margin-top: 4px; }}
.stMarkdown h2.ct, h2.ct {{ margin: 0 0 8px 0; padding: 0; font-size: 17px !important; font-weight: 600; color: {MARINE}; line-height: 1.3; }}

/* menu latéral marine, comme la maquette */
[data-testid="stSidebar"] {{ background: {MARINE}; min-width: 262px; max-width: 262px; }}
[data-testid="stSidebar"] * {{ color: #FFFFFF; }}
[data-testid="stSidebarHeader"] {{ display: none; }}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{ padding: 0.4rem 0.9rem 1rem 0.9rem; }}
.marque {{ display:flex; align-items:center; gap:10px; margin: 8px 0 22px 4px; }}
.marque .n {{ font-weight:700; font-size:18px; line-height:1.1; }} .marque .s {{ font-size:11px; opacity:.75; }}
[data-testid="stPageLink-NavLink"] {{ border-radius:10px; padding: 9px 10px; margin-bottom: 4px; }}
[data-testid="stPageLink-NavLink"] p {{ font-size: 14px; }}
[data-testid="stPageLink-NavLink"]:hover {{ background: rgba(255,255,255,.10); }}
[data-testid="stPageLink-NavLink"][aria-current="page"] {{ background: rgba(255,255,255,.16); }}
[data-testid="stPageLink-NavLink"][aria-current="page"] p {{ font-weight: 600; }}
.mode-ia {{ background: rgba(255,255,255,.08); border-radius:12px; padding:12px 14px 4px 14px; margin-top: 18px; }}
.mode-ia .t {{ font-size:11px; letter-spacing:.06em; text-transform:uppercase; opacity:.7; margin-bottom:6px; }}
.pied-menu {{ font-size:11px; line-height:1.5; opacity:.7; margin-top: 14px; }}

/* sélecteur Mode IA (menu marine) */
[data-testid="stSidebar"] button[kind="segmented_control"], [data-testid="stSidebar"] button[kind="segmented_controlActive"] {{
  border: 1px solid rgba(255,255,255,.35); font-size: 12px; padding: 0.35rem 0.5rem; }}
[data-testid="stSidebar"] button[kind="segmented_control"] {{ background: transparent; }}
[data-testid="stSidebar"] button[kind="segmented_control"] p {{ color: #FFFFFF; }}
[data-testid="stSidebar"] button[kind="segmented_controlActive"] {{ background: #FFFFFF; }}
[data-testid="stSidebar"] button[kind="segmented_controlActive"] p {{ color: {MARINE}; font-weight: 600; }}

/* boutons-pastilles des filtres (en-tête) */
[data-testid="stPopover"] > div > button, [data-testid="stDownloadButton"] button {{
  border: 1px solid {LIGNE}; background:#FFFFFF; border-radius:10px; font-size:13px; padding: 0.45rem 0.8rem; color:#1B2433; }}
[data-testid="stDownloadButton"] button {{ background:{BLEU}; color:#FFFFFF; border:0; font-weight:600; }}
[data-testid="stDownloadButton"] button p {{ color:#FFFFFF; }}

/* cartes blanches */
[class*="st-key-carte_"] {{ background:#FFFFFF; border:1px solid {LIGNE}; border-radius:16px; padding: 18px 22px; }}
[class*="st-key-brief_"] {{ background:#FFFFFF; border:1px solid {LIGNE}; border-radius:16px; padding: 0; overflow: hidden; }}
.brief-t {{ background:{MARINE}; color:#FFFFFF; padding:12px 22px; display:flex; flex-wrap:wrap; justify-content:space-between; gap:8px; font-size:14px; }}
.brief-t b {{ font-weight:600; }} .brief-t span {{ font-size:12px; opacity:.8; }}

.kpi {{ background:#fff; border:1px solid {LIGNE}; border-radius:16px; padding:16px 18px; height:100%; }}
.kpi .l {{ font-size:13px; color:{GRIS}; }}
.kpi .v {{ font-size:30px; font-weight:700; color:{MARINE}; line-height:1.15; }}
.kpi .d {{ display:inline-block; margin-top:6px; padding:2px 10px; border-radius:999px; font-size:12px; font-weight:600; }}
.ok {{ background:#E6F2EC; color:{VERT}; }} .ko {{ background:#FBE9E7; color:{ROUGE}; }}
.mid {{ background:#FBF1E6; color:{BRUN}; }} .info {{ background:#EAF1FA; color:{MARINE}; }}
.alerte {{ border-radius:12px; padding:12px 14px; margin-bottom:10px; font-size:14px; line-height:1.45; }}
.alerte .niv {{ font-size:11px; font-weight:700; letter-spacing:.05em; text-transform:uppercase; display:block; margin-bottom:4px; }}
.alerte-ko {{ background:#FBEDEB; }} .alerte-ko .niv {{ color:{ROUGE}; }}
.alerte-mid {{ background:#FBF1E6; }} .alerte-mid .niv {{ color:{BRUN}; }}
.alerte-ok {{ background:#E6F2EC; }} .alerte-ok .niv {{ color:{VERT}; }}
.carte {{ background:#fff; border:1px solid {LIGNE}; border-radius:16px; padding:16px 20px; margin-bottom:12px; }}
.source {{ background:#fff; border:1px solid {LIGNE}; border-radius:12px; padding:12px 14px; margin-bottom:8px; font-size:14px; }}
.note-bas {{ font-size:12px; color:{GRIS}; }}
.stButton > button {{ border-radius:10px; font-weight:600; }}
.stButton > button[kind="primary"] {{ background:{BLEU}; border:0; }}
</style>
"""

LOGO = f"""<svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" fill="{BLEU}"/>
<path d="M7 20 L12 12 L17 17 L25 7" fill="none" stroke="#FFFFFF" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>"""


def appliquer_charte():
    st.markdown(CSS, unsafe_allow_html=True)


def kpi(colonne, libelle, valeur, delta=None, classe="info"):
    d = f'<span class="d {classe}">{delta}</span>' if delta else ""
    colonne.markdown(f'<div class="kpi"><div class="l">{libelle}</div><div class="v">{valeur}</div>{d}</div>', unsafe_allow_html=True)


def fr(nombre, decimales=0):
    """Format français : 1 234,5"""
    return f"{nombre:,.{decimales}f}".replace(",", " ").replace(".", ",")


@contextmanager
def carte(cle, titre=None, sous_titre=None):
    """Carte blanche arrondie, comme dans la maquette."""
    with st.container(border=True, key="carte_" + cle):
        if titre:
            droite = f'<span class="note-bas" style="float:right">{sous_titre}</span>' if sous_titre else ""
            st.markdown(f'<h2 class="ct">{titre}{droite}</h2>', unsafe_allow_html=True)
        yield


def alerte(niveau, texte, classe):
    st.markdown(f'<div class="alerte alerte-{classe}"><span class="niv">{niveau}</span>{texte}</div>', unsafe_allow_html=True)


@st.cache_data(show_spinner="Chargement des avis…")
def donnees():
    """Avis nettoyés + sentiment par avis ; tableau des aspects."""
    from voxcx.nlp import CACHE_ASPECTS, CACHE_AVIS

    d = charger()
    if os.path.exists(CACHE_AVIS):
        d = d.merge(pd.read_csv(CACHE_AVIS), on="id", how="left")
    else:
        d["sentiment"], d["etiquette"] = pd.NA, pd.NA
    asp = pd.read_csv(CACHE_ASPECTS, parse_dates=["date"]) if os.path.exists(CACHE_ASPECTS) else pd.DataFrame(
        columns=["id", "hotel", "ville", "date", "aspect", "phrase", "score", "etiquette"])
    return d, asp


def _reinitialiser_periode():
    d, _ = donnees()
    debut = pd.Timestamp(DATE_FENETRE_COMMUNE) if st.session_state.get("f_commune", True) else d["date"].min()
    st.session_state["f_periode"] = (debut.date(), d["date"].max().date())


def entete(titre, sous_titre="", filtres_actifs=True):
    """En-tête de page : titre à gauche, boutons-filtres à droite. Retourne (avis filtrés, aspects filtrés)."""
    d, asp = donnees()
    ss = st.session_state
    villes = sorted(d["ville"].unique())
    ss.setdefault("f_villes", villes)
    ss["f_villes"] = [v for v in ss["f_villes"] if v in villes] or villes
    dispo = sorted(d[d["ville"].isin(ss["f_villes"])]["hotel"].unique())
    ss["f_hotels"] = [h for h in ss.get("f_hotels", dispo) if h in dispo] or dispo
    ss.setdefault("f_commune", True)
    ss.setdefault("f_masquer", False)
    if "f_periode" not in ss:
        _reinitialiser_periode()
    p = ss["f_periode"]
    if not (isinstance(p, (tuple, list)) and len(p) == 2):
        _reinitialiser_periode()
        p = ss["f_periode"]
    debut, fin = pd.Timestamp(p[0]), pd.Timestamp(p[1]) + pd.Timedelta(days=1)
    f = d[d["hotel"].isin(ss["f_hotels"]) & (d["date"] >= debut) & (d["date"] < fin)].copy()
    fa = asp[asp["hotel"].isin(ss["f_hotels"]) & (asp["date"] >= debut) & (asp["date"] < fin)].copy()

    if "{" in sous_titre and not f.empty:
        sous_titre = sous_titre.format(hotels=f["hotel"].nunique(), avis=fr(len(f)), debut=f["date"].min().strftime("%d/%m/%Y"), fin=f["date"].max().strftime("%d/%m/%Y"))
    gauche, droite = st.columns([6, 7], vertical_alignment="bottom")
    gauche.markdown(f'<h1 class="titre">{titre}</h1><div class="sous">{sous_titre}</div>', unsafe_allow_html=True)
    if filtres_actifs:
        c = droite.columns([2.3, 1.5, 1.1, 1.9])
        with c[0].popover(f"Période : {p[0]:%d/%m/%Y} – {p[1]:%d/%m/%Y}", width="stretch"):
            st.date_input("Période", key="f_periode", min_value=d["date"].min().date(), max_value=d["date"].max().date(), format="DD/MM/YYYY")
            st.checkbox("Fenêtre commune (depuis le 14/05/2026)", key="f_commune", on_change=_reinitialiser_periode,
                        help="Kenzi Solazur est limité à 1 300 avis et ne remonte qu'au 14/05/2026 : cette option compare tous les hôtels sur la même période.")
        with c[1].popover(f"Hôtels : {len(ss['f_hotels'])} sur {d['hotel'].nunique()}", width="stretch"):
            st.multiselect("Villes", villes, key="f_villes")
            st.multiselect("Hôtels", dispo, key="f_hotels")
        with c[2].popover("Options", width="stretch"):
            st.checkbox("Masquer les noms des auteurs", key="f_masquer")
        c[3].download_button("Exporter les avis (CSV)", f.drop(columns=["url_avis"]).to_csv(index=False).encode("utf-8-sig"),
                             file_name="avis_filtres.csv", mime="text/csv", width="stretch")
    st.write("")
    return f, fa


def pied(texte):
    st.markdown(f'<div class="note-bas">{texte}</div>', unsafe_allow_html=True)


def nom_auteur(nom):
    if st.session_state.get("f_masquer"):
        return "Auteur masqué"
    return nom or "Auteur inconnu"
