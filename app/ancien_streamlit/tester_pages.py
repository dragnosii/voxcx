"""Test automatique : exécute chaque page de l'application et signale toute erreur.
Lancer :  .venv\\Scripts\\python tester_pages.py
"""
import sys

from streamlit.testing.v1 import AppTest

PAGES = ["app.py", "vues/direction.py", "vues/themes.py", "vues/assistant.py", "vues/predictif.py", "vues/plan.py"]
echec = 0
for page in PAGES:
    at = AppTest.from_file(page, default_timeout=300).run()
    if at.exception:
        echec += 1
        print(f"ERREUR  {page}")
        for e in at.exception:
            print("   ", str(e.value)[:400])
    else:
        print(f"OK      {page}  ({len(at.markdown)} blocs de texte, {len(at.dataframe)} tableaux)")
sys.exit(1 if echec else 0)
