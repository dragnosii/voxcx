"""Analyse des avis : sentiment (modèle local multilingue) et sentiment par aspect, phrase par phrase.

Lancer une fois (calculs mis en cache dans app/data) :
    .venv\\Scripts\\python -m voxcx.nlp
"""
import os
import re
import time

import numpy as np
import pandas as pd

from voxcx.donnees import DOSSIER_APP, charger

MODELE_SENTIMENT = os.path.join(DOSSIER_APP, "models", "sentiment")
CACHE_AVIS = os.path.join(DOSSIER_APP, "data", "sentiments.csv")
CACHE_ASPECTS = os.path.join(DOSSIER_APP, "data", "aspects.csv")

# Lexique d'aspects hôteliers (français, anglais, espagnol, arabe). Mots en minuscules, recherchés comme sous-chaînes.
ASPECTS = {
    "Chambre et literie": ["chambre", "lit ", "literie", "matelas", "oreiller", "suite", "salle de bain", "douche", "room", "bed", "bathroom", "shower", "habitaci", "cama", "غرفة", "سرير", "حمام"],
    "Propreté": ["propre", "propreté", "sale", "saleté", "poussière", "odeur", "ménage", "clean", "dirty", "dust", "smell", "limpi", "نظيف", "نظافة", "وسخ"],
    "Personnel et service": ["personnel", "staff", "équipe", "serveur", "serveuse", "accueil", "aimable", "gentil", "sympa", "professionnel", "service", "réceptionn", "reception", "personal", "موظف", "استقبال", "خدمة", "طاقم"],
    "Petit-déjeuner et restauration": ["petit-déj", "petit déj", "petit dej", "buffet", "restaurant", "repas", "dîner", "diner", "déjeuner", "nourriture", "cuisine", "plat", "breakfast", "food", "dinner", "desayuno", "comida", "فطور", "إفطار", "أكل", "طعام", "مطعم"],
    "Piscine, spa et animations": ["piscine", "spa", "hammam", "massage", "animation", "toboggan", "plage", "club enfant", "pool", "slide", "kids club", "piscina", "مسبح", "سبا", "حمام تقليدي"],
    "Emplacement": ["emplacement", "situé", "situation", "centre-ville", "proche", "à côté", "à pied", "quartier", "location", "located", "close to", "walking distance", "ubicaci", "موقع"],
    "Bruit": ["bruit", "bruyant", "musique", "tapage", "insonoris", "noise", "noisy", "loud", "ruido", "ضجيج", "صاخب", "ضوضاء"],
    "Prix et rapport qualité-prix": ["prix", "cher", "tarif", "rapport qualité", "coût", "payer", "facture", "price", "expensive", "overpriced", "value for money", "precio", "caro", "سعر", "غالي", "أسعار", "ثمن"],
    "Wi-Fi et équipements": ["wifi", "wi-fi", "internet", "connexion", "climatisation", "clim ", "ascenseur", "télévision", "tv ", "chauffage", "eau chaude", "air condition", "elevator", "lift", "hot water", "ascensor", "واي فاي", "مكيف", "مصعد"],
    "Arrivée et départ": ["check-in", "check in", "check-out", "checkout", "arrivée", "attente", "attendre", "file d'attente", "départ", "wait", "queue", "espera", "انتظار"],
    "Parking": ["parking", "voiture", "garage", "stationnement", "valet", "موقف"],
}
ASPECTS_COMPILES = {a: mots for a, mots in ASPECTS.items()}


def decouper_phrases(texte):
    """Découpe un avis en phrases (ponctuation, retours à la ligne, « mais »)."""
    texte = re.sub(r"\s+", " ", str(texte)).strip()
    if not texte:
        return []
    morceaux = re.split(r"(?<=[\.\!\?؟…])\s+|\n+|\s+[-–—]\s+", texte)
    phrases = []
    for m in morceaux:
        for p in re.split(r",?\s+(?:mais|but|pero|لكن)\s+", m, flags=re.I):
            p = p.strip(" .,;!?")
            if len(p) >= 8:
                phrases.append(p)
    return phrases


def detecter_aspects(phrase):
    bas = " " + phrase.lower() + " "
    return [a for a, mots in ASPECTS_COMPILES.items() if any(m in bas for m in mots)]


class Sentiment:
    """Modèle local XLM-RoBERTa multilingue : retourne un score de -1 (très négatif) à +1 (très positif)."""

    def __init__(self, dossier=MODELE_SENTIMENT):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(dossier)
        self.mod = AutoModelForSequenceClassification.from_pretrained(dossier).eval()
        etiquettes = {int(i): str(l).lower() for i, l in self.mod.config.id2label.items()}
        # ordre attendu du modèle : négatif, neutre, positif
        self.i_neg = next((i for i, l in etiquettes.items() if "neg" in l), 0)
        self.i_pos = next((i for i, l in etiquettes.items() if "pos" in l), 2)

    def scorer(self, textes, lot=32, max_len=160, progres=None):
        textes = [str(t) for t in textes]
        ordre = np.argsort([len(t) for t in textes])  # on regroupe les textes de longueur proche (plus rapide)
        res = np.zeros(len(textes), dtype=float)
        t0 = time.time()
        with self.torch.no_grad():
            for debut in range(0, len(textes), lot):
                idx = ordre[debut:debut + lot]
                enc = self.tok([textes[i] for i in idx], padding=True, truncation=True, max_length=max_len, return_tensors="pt")
                p = self.torch.softmax(self.mod(**enc).logits, dim=-1).numpy()
                res[idx] = p[:, self.i_pos] - p[:, self.i_neg]
                if progres and (debut // lot) % 10 == 0:
                    progres(debut + len(idx), len(textes), time.time() - t0)
        return res


def etiquette(score, seuil=0.25):
    return "positif" if score >= seuil else "négatif" if score <= -seuil else "neutre"


def calculer(forcer=False):
    """Calcule (ou relit) le sentiment par avis et par aspect."""
    if not forcer and os.path.exists(CACHE_AVIS) and os.path.exists(CACHE_ASPECTS):
        return pd.read_csv(CACHE_AVIS), pd.read_csv(CACHE_ASPECTS, parse_dates=["date"])
    d = charger()
    d = d[d["a_texte"]].copy()
    m = Sentiment()

    def avancement(fait, total, sec):
        print(f"   {fait}/{total} ({sec:.0f} s)", flush=True)

    print(f"Sentiment des avis ({len(d)} textes)...", flush=True)
    avis = pd.DataFrame({"id": d["id"].values, "sentiment": m.scorer(d["texte"].tolist(), progres=avancement)})
    avis["etiquette"] = avis["sentiment"].map(etiquette)

    lignes = []
    for r in d.itertuples():
        for p in decouper_phrases(r.texte):
            for a in detecter_aspects(p):
                lignes.append((r.id, r.hotel, r.ville, r.date, a, p))
    asp = pd.DataFrame(lignes, columns=["id", "hotel", "ville", "date", "aspect", "phrase"])
    print(f"Sentiment des phrases par aspect ({asp['phrase'].nunique()} phrases)...", flush=True)
    uniques = asp["phrase"].drop_duplicates().tolist()
    scores = dict(zip(uniques, m.scorer(uniques, progres=avancement)))
    asp["score"] = asp["phrase"].map(scores)
    asp["etiquette"] = asp["score"].map(etiquette)

    avis.to_csv(CACHE_AVIS, index=False)
    asp.to_csv(CACHE_ASPECTS, index=False, encoding="utf-8-sig")
    print(f"Terminé : {len(avis)} avis, {len(asp)} mentions d'aspects.")
    return avis, asp


if __name__ == "__main__":
    calculer(forcer=True)
