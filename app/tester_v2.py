"""Tests de VoxCX 2 (fonctions + protections). Base de test séparée, supprimée à la fin.
Lancement : .venv\\Scripts\\python tester_v2.py
"""
import os
import sys
import tempfile
import time

dossier = tempfile.mkdtemp(prefix="voxcx_test_")
import plateforme.config as cfg  # noqa: E402

cfg.BASE = os.path.join(dossier, "test.sqlite3")
import plateforme.base as base_mod  # noqa: E402

base_mod.BASE = cfg.BASE
from starlette.testclient import TestClient  # noqa: E402

import serveur  # noqa: E402

resultats = []


def ok(nom, condition, detail=""):
    resultats.append((nom, bool(condition)))
    print(("OK    " if condition else "ÉCHEC ") + nom + (f"  ({detail})" if detail and not condition else ""))


def client():
    return TestClient(serveur.app, base_url="http://localhost")


def inscrire(c, email):
    r = c.post("/api/inscription", json={"nom": "Test", "email": email, "mot": "motdepasse-solide-42"})
    return r, c.get("/api/moi").json()


base_mod.initialiser()
A, B, X = client(), client(), client()
r, moiA = inscrire(A, "a@test.ma")
ok("Inscription A", r.status_code == 200 and moiA["connecte"])
ck = r.headers.get("set-cookie", "").lower()
ok("Cookie de session HttpOnly + SameSite=Strict", "httponly" in ck and "samesite=strict" in ck, ck)
_, moiB = inscrire(B, "b@test.ma")
hA, hB = {"X-CSRF": moiA["csrf"]}, {"X-CSRF": moiB["csrf"]}

ok("Mot de passe trop court refusé", X.post("/api/inscription", json={"nom": "x", "email": "c@test.ma", "mot": "court"}).status_code == 400)
ok("Mot de passe haché en base", base_mod.lire("SELECT hash FROM utilisateurs WHERE email='a@test.ma'", un=True)["hash"].startswith("scrypt$"))
ok("Écriture sans jeton CSRF refusée", A.post("/api/etablissements", json={"nom": "Riad", "ville": "Fès"}).status_code == 403)

r = A.post("/api/etablissements", json={"nom": "Riad Test", "ville": "Marrakech", "type": "Riad", "lien_avis": "https://g.page/r/test/review"}, headers=hA)
ok("Création d'établissement", r.status_code == 200, r.text)
eA = r.json()["id"]
ok("Offre d'essai : 1 seul établissement", A.post("/api/etablissements", json={"nom": "Deux", "ville": "Fès"}, headers=hA).status_code == 402)

# Anti-IDOR : B ne voit jamais les données de A
ok("IDOR tableau refusé", B.get(f"/api/etablissements/{eA}/tableau").status_code == 404)
ok("IDOR modification refusée", B.post(f"/api/etablissements/{eA}/modifier", json={"nom": "Pirate", "ville": "X"}, headers=hB).status_code == 404)
ok("IDOR suppression refusée", B.post(f"/api/etablissements/{eA}/supprimer", json={}, headers=hB).status_code == 404)

# Admin
ok("Admin sans connexion refusé", X.get("/api/admin/vue").status_code == 401)
ok("Admin avec compte simple refusé", A.get("/api/admin/vue").status_code == 403)
ok("Rôle non modifiable par l'API", client().post("/api/inscription", json={"nom": "Zed", "email": "z@test.ma", "mot": "motdepasse-solide-42", "role": "admin"}).status_code in (200, 429)
   and base_mod.lire("SELECT role FROM utilisateurs WHERE email='z@test.ma'", un=True) in (None, {"role": "gerant"}))

ok("Choix du modèle IA refusé à un gérant", B.post("/api/admin/niveau-ia", json={"niveau": "puissant"}, headers=hB).status_code == 403)
base_mod.ecrire("UPDATE utilisateurs SET role='admin' WHERE email='b@test.ma'")
ok("Choix du modèle IA par l'admin", B.post("/api/admin/niveau-ia", json={"niveau": "economique"}, headers=hB).status_code == 200
   and B.get("/api/admin/vue").json()["niveau"] == "economique")
ok("Niveau inconnu refusé", B.post("/api/admin/niveau-ia", json={"niveau": "gratuit-illimite"}, headers=hB).status_code == 400)

# Import de l'historique (fiche de démonstration)
fiches = A.get("/api/fiches-demo").json()["fiches"]
ok("Fiches de démonstration disponibles", len(fiches) > 0)
fiche = min(fiches, key=lambda f: f["avis"])["fiche"]
A.post(f"/api/etablissements/{eA}/connecter", json={"fiche": fiche}, headers=hA)
for _ in range(120):
    s = A.get(f"/api/etablissements/{eA}/import").json()
    if s["import_statut"] in ("termine", "erreur"):
        break
    time.sleep(1)
ok("Import de tout l'historique", s["import_statut"] == "termine" and s["import_total"] > 0, str(s))
t = A.get(f"/api/etablissements/{eA}/tableau").json()
ok("Tableau « Ce matin » calculé", not t.get("vide") and t["kpi"]["avis"] == s["import_total"] and len(t["pouls"]) > 0)
ok("Auteurs pseudonymisés", all(a["auteur"].startswith("Client ") for a in base_mod.lire("SELECT auteur FROM avis LIMIT 50")))

# Enquête publique + rattrapage
jeton = A.get("/api/moi").json()["etablissements"][0]["jeton_enquete"]
ok("Page d'enquête publique", X.get(f"/e/{jeton}").status_code == 200)
ok("Jeton d'enquête inconnu refusé", X.get("/api/public/enquete/inconnu").status_code == 404)
r = X.post(f"/api/public/enquete/{jeton}", json={"note": 5, "commentaire": "Accueil parfait, merci !", "consentement": False})
ok("Client content invité sur Google", r.json().get("resultat") == "content" and r.json().get("lien_avis", "").startswith("https://"))
r = X.post(f"/api/public/enquete/{jeton}", json={"note": 2, "commentaire": "Chambre sale et personnel désagréable à l'accueil", "consentement": True, "contact": "0600000000"})
ok("Client mécontent : cas de rattrapage ouvert", r.json().get("resultat") == "mecontent")
cas = A.get(f"/api/etablissements/{eA}/rattrapage").json()["cas"]
ok("Conseil d'appel proposé", len(cas) == 1 and len(cas[0]["suggestion"]) > 20)
ok("IDOR cas refusé", B.post(f"/api/cas/{cas[0]['id']}/statut", json={"statut": "perdu"}, headers=hB).status_code == 404)
ok("Cas marqué rattrapé", A.post(f"/api/cas/{cas[0]['id']}/statut", json={"statut": "rattrape"}, headers=hA).status_code == 200)
for _ in range(6):
    r = X.post(f"/api/public/enquete/{jeton}", json={"note": 4})
ok("Limite d'envoi d'enquêtes par IP (429)", r.status_code == 429)

# Réponse aux avis
file_ = A.get(f"/api/etablissements/{eA}/reponses").json()["avis"]
ok("File « à répondre » disponible", isinstance(file_, list))
avis_id = file_[0]["id"] if file_ else base_mod.lire("SELECT id FROM avis WHERE etablissement_id=? AND texte!='' LIMIT 1", (eA,), un=True)["id"]
r = A.post(f"/api/avis/{avis_id}/brouillon", json={"ton": "formel"}, headers=hA)
ok("Brouillon de réponse", r.status_code == 200 and len(r.json().get("texte", "")) > 40, r.text[:200])
ok("IDOR brouillon refusé", B.post(f"/api/avis/{avis_id}/brouillon", json={"ton": "formel"}, headers=hB).status_code == 404)
ok("Publication de la réponse", A.post(f"/api/avis/{avis_id}/publier", json={"texte": "Merci pour votre retour, nous corrigeons cela."}, headers=hA).status_code == 200)

# Assistant
r = A.post(f"/api/etablissements/{eA}/question", json={"question": "Que disent les clients du petit-déjeuner ?"}, headers=hA)
ok("Question à l'assistant avec sources", r.status_code == 200 and len(r.json().get("sources", [])) > 0, r.text[:200])

# Actions
ok("Création d'action", A.post(f"/api/etablissements/{eA}/actions", json={"titre": "Vérifier les serviettes", "sujet": "Propreté"}, headers=hA).status_code == 200)

# Abonnement (démonstration) : le montant vient du serveur
r = A.post("/api/abonnement/payer", json={"offre": "pro", "montant_centimes": 1}, headers=hA)
paiement = base_mod.lire("SELECT montant_centimes FROM paiements", un=True)
ok("Paiement démo : montant fixé par le serveur", r.status_code == 200 and paiement["montant_centimes"] == 49900)
ok("Offre Pro : 2e établissement autorisé", A.post("/api/etablissements", json={"nom": "Deux", "ville": "Fès"}, headers=hA).status_code == 200)

# Connexion
X2 = client()
for _ in range(5):
    X2.post("/api/connexion", json={"email": "a@test.ma", "mot": "mauvais-mot-de-passe"})
ok("Compte bloqué après 5 échecs", X2.post("/api/connexion", json={"email": "a@test.ma", "mot": "motdepasse-solide-42"}).status_code == 429)
ok("Message identique e-mail inconnu / mauvais mot de passe",
   client().post("/api/connexion", json={"email": "inconnu@test.ma", "mot": "x"}).json()["erreur"] == "E-mail ou mot de passe incorrect.")

# En-têtes et fichiers sensibles
r = X.get("/")
ok("En-têtes de sécurité", "frame-ancestors 'none'" in r.headers.get("content-security-policy", "") and r.headers.get("x-content-type-options") == "nosniff")
ok(".env inaccessible par le web", X.get("/static/../.env").status_code == 404 and X.get("/.env").status_code == 404)

# Suppression
ok("Suppression d'un établissement", A.post(f"/api/etablissements/{eA}/supprimer", json={}, headers=hA).status_code == 200
   and base_mod.lire("SELECT COUNT(*) n FROM avis WHERE etablissement_id=?", (eA,), un=True)["n"] == 0)

total = len(resultats)
reussis = sum(1 for _, r in resultats if r)
print(f"\n{reussis} / {total} vérifications réussies.")
sys.exit(0 if reussis == total else 1)
