"""Donne le rôle administrateur à un compte existant (impossible depuis le site, par sécurité).
Usage : .venv\\Scripts\\python creer_admin.py adresse@exemple.com
"""
import sys

from plateforme import base

if len(sys.argv) != 2:
    sys.exit("Usage : python creer_admin.py adresse@exemple.com")
base.initialiser()
n = base.ecrire("UPDATE utilisateurs SET role='admin' WHERE email=?", (sys.argv[1].strip().lower(),))
print("Compte passé administrateur." if n else "Aucun compte avec cette adresse : inscrivez-vous d'abord sur le site.")
