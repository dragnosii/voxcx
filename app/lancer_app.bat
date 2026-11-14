@echo off
rem Lance VoxCX (le navigateur s'ouvre sur http://localhost:8501)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo L'environnement .venv est introuvable. Voir le guide d'utilisation : creer l'environnement puis pip install -r requirements.txt
  pause
  exit /b 1
)
.venv\Scripts\python.exe serveur.py
