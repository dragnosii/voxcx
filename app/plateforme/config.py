"""Configuration : chemins, secrets (lus dans .env, jamais écrits dans le code), offres d'abonnement."""
import os
import secrets

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DONNEES = os.path.join(APP, "data_plateforme")
BASE = os.path.join(DONNEES, "voxcx.sqlite3")
STATIC = os.path.join(APP, "static")
FICHIER_ENV = os.path.join(APP, ".env")
MODELE_SENTIMENT = os.path.join(APP, "models", "sentiment")
MODELE_EMBEDDINGS = os.path.join(APP, "models", "embeddings")

# Jeu de démonstration pour la connexion « Google » simulée (à remplacer par l'API Google Business Profile).
SOURCE_DEMO = os.path.join(APP, "data", "avis_propres.csv")
CACHE_SENTIMENT_DEMO = os.path.join(APP, "data", "sentiments.csv")
CACHE_ASPECTS_DEMO = os.path.join(APP, "data", "aspects.csv")

os.makedirs(DONNEES, exist_ok=True)


def _charger_env():
    try:
        from dotenv import load_dotenv

        load_dotenv(FICHIER_ENV)
    except ImportError:
        pass


def _secret_session():
    """Clé de signature des sessions : lue dans .env, créée une fois si absente (le .env n'est jamais versionné)."""
    _charger_env()
    cle = os.environ.get("VOXCX_SECRET", "").strip()
    if len(cle) >= 32:
        return cle
    cle = secrets.token_urlsafe(48)
    with open(FICHIER_ENV, "a", encoding="utf-8") as f:
        f.write(f"\nVOXCX_SECRET={cle}\n")
    os.environ["VOXCX_SECRET"] = cle
    return cle


SECRET = _secret_session()
PORT = int(os.environ.get("VOXCX_PORT", "8501"))
PRODUCTION = os.environ.get("VOXCX_PRODUCTION", "0") == "1"  # cookies Secure + HSTS en production (HTTPS)
MODE_DEMO_PAIEMENT = os.environ.get("VOXCX_PAIEMENT_DEMO", "1") == "1"
MODELE_CLAUDE = os.environ.get("MODELE_CLAUDE", "claude-sonnet-5-5")


def cle_ia():
    _charger_env()
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


# Offres : montants en centimes de dirham, calculés côté serveur uniquement.
OFFRES = {
    "essai": {"nom": "Essai gratuit", "prix": 0, "jours": 14, "etablissements": 1, "ia_mois": 30,
              "atouts": ["14 jours", "1 établissement", "30 actions IA"]},
    "essentiel": {"nom": "Essentiel", "prix": 24900, "jours": 30, "etablissements": 1, "ia_mois": 200,
                  "atouts": ["1 établissement", "Import de tout l'historique", "Enquêtes QR et WhatsApp", "Rattrapage des mécontents", "200 réponses IA par mois"]},
    "pro": {"nom": "Pro", "prix": 49900, "jours": 30, "etablissements": 3, "ia_mois": 800,
            "atouts": ["Jusqu'à 3 établissements", "Tout Essentiel", "Assistant d'analyse", "Résumé du lundi", "800 actions IA par mois"]},
}
