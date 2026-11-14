# VoxCX 2

Plateforme d'expérience client et d'e-réputation pour les hôtels, riads et restaurants marocains, avec plusieurs agents d'IA.

## Ce que fait la plateforme
- **Collecte** : connexion de la fiche d'avis avec import de tout l'historique, puis enquête client par lien ou QR code (WhatsApp, table, réception).
- **Rattrapage** : une note de 3 ou moins dans l'enquête ouvre un « client à rappeler », avec un conseil d'appel.
- **Réponse aux avis** : file des avis récents sans réponse, brouillon dans la langue du client (formel ou chaleureux), validation humaine avant publication.
- **Analyse** : tableau « Ce matin » (décisions du jour, note semaine par semaine, sujets de plainte) et questions en langage naturel avec les avis cités en preuve.
- **Actions** : responsable, objectif, suivi.
- **Abonnements** : essai gratuit 14 jours, offres Essentiel et Pro (paiement de démonstration), quotas d'IA par offre.
- **Administration** : comptes, revenus, consommation d'IA, journal.

## Lancer en local (Windows)
1. `cd app`, puis `python -m venv .venv` et `.venv\Scripts\pip install -r requirements.txt`
2. `.venv\Scripts\python telecharger_modeles.py` (modèles d'IA locaux, environ 1,5 Go)
3. Copier `.env.example` en `.env` (la clé d'IA est facultative)
4. Double-cliquer sur `lancer_app.bat`, puis ouvrir http://localhost:8501
5. Donner le rôle admin à un compte : `.venv\Scripts\python creer_admin.py adresse@exemple.com`

Tests : `.venv\Scripts\python tester_v2.py` (fonctions et protections, base de test séparée).

## Sécurité
Mots de passe hachés (scrypt), sessions signées (HttpOnly, SameSite=Strict), jeton CSRF sur chaque écriture, contrôle du propriétaire de chaque donnée, administration vérifiée côté serveur, limites de débit, en-têtes de sécurité (CSP), clé d'IA uniquement côté serveur, montants d'abonnement calculés par le serveur.

## Données
Aucune donnée réelle n'est publiée dans ce dépôt. La connexion à Google Business Profile est simulée avec un jeu de démonstration local ; les auteurs des avis sont pseudonymisés à l'import.
