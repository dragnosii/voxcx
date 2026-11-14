"""Test automatique : démarre le serveur en mémoire et vérifie que chaque route répond sans erreur.
Lancer :  .venv\\Scripts\\python tester_api.py
"""
import json
import sys

from starlette.testclient import TestClient

from serveur import app

ECHEC = 0


def verifier(nom, reponse, cle=None):
    global ECHEC
    ok = reponse.status_code == 200 and "erreur" not in (reponse.json() if "json" in reponse.headers.get("content-type", "") else {})
    if ok and cle:
        ok = cle in reponse.json()
    print(("OK      " if ok else "ERREUR  ") + nom + ("" if ok else "  -> " + reponse.text[:200]))
    ECHEC += 0 if ok else 1


with TestClient(app) as c:
    q = "debut=2026-05-14"
    verifier("page d'accueil (HTML)", c.get("/"))
    verifier("/api/meta", c.get("/api/meta"), "hotels")
    verifier("/api/accueil", c.get(f"/api/accueil?{q}"), "kpis")
    verifier("/api/themes", c.get(f"/api/themes?{q}"), "sujets")
    verifier("/api/themes/phrases", c.get(f"/api/themes/phrases?{q}&aspect=Bruit&sens=négatif"))
    verifier("/api/predictif", c.get("/api/predictif"), "f1")
    verifier("/api/predictif/tester", c.post("/api/predictif/tester", json={"texte": "Chambre bruyante et personnel désagréable."}), "risque")
    verifier("/api/assistant (local)", c.post("/api/assistant", json={"question": "Que disent les clients du petit-déjeuner ?", "mode": "local"}), "texte")
    verifier("/api/simulateur", c.post(f"/api/simulateur?{q}", json={"aspect": "Chambre et literie", "part": 50, "cout": 180000}), "ok")
    verifier("/api/plan", c.get(f"/api/plan?{q}"), "actions")
    verifier("/api/export.csv", c.get(f"/api/export.csv?{q}"))
sys.exit(1 if ECHEC else 0)
