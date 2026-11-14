# Dépôt GitHub

- Adresse : https://github.com/dragnosii/voxcx (public)
- Branche : `main`
- Compte : `dragnosii` (connexion via l'outil `gh` déjà authentifié sur le PC ; aucun jeton dans les fichiers)
- Auteur des commits : adresse masquée GitHub (`…@users.noreply.github.com`), jamais l'adresse personnelle.

## Ce qui n'est jamais publié (voir `.gitignore`)
- `.env` (clé d'IA, clé de session), environnements Python, modèles d'IA (1,5 Go)
- toutes les données d'avis réels (`data/`, `app/data/`, `app/data_plateforme/`) et les maquettes qui en citent
- le rapport, le guide et la présentation du PFE (`rapport/`), les notes internes (`docs/PROJET.md`)

## Avant chaque envoi
1. `git status` et vérifier la liste des fichiers.
2. Scan des secrets : `gitleaks git . --redact` (0 fuite attendu).
3. `git push`.
