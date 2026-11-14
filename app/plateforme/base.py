"""Base SQLite. Toute requête passe par des paramètres (jamais de texte concaténé)."""
import sqlite3
import threading
import uuid
from datetime import datetime

from plateforme.config import BASE

_verrou = threading.Lock()

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS utilisateurs (
  id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, nom TEXT NOT NULL, hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'gerant' CHECK (role IN ('gerant','admin')),
  echecs INTEGER NOT NULL DEFAULT 0, bloque_jusqua TEXT, cree_le TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS abonnements (
  id TEXT PRIMARY KEY, utilisateur_id TEXT NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
  offre TEXT NOT NULL, statut TEXT NOT NULL, debut TEXT NOT NULL, fin TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS paiements (
  id TEXT PRIMARY KEY, utilisateur_id TEXT NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
  offre TEXT NOT NULL, montant_centimes INTEGER NOT NULL, devise TEXT NOT NULL DEFAULT 'MAD',
  mode TEXT NOT NULL, date TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS etablissements (
  id TEXT PRIMARY KEY, proprietaire_id TEXT NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
  nom TEXT NOT NULL, ville TEXT NOT NULL, type TEXT NOT NULL, lien_avis TEXT NOT NULL DEFAULT '',
  jeton_enquete TEXT UNIQUE NOT NULL, source_connectee TEXT NOT NULL DEFAULT '',
  import_statut TEXT NOT NULL DEFAULT 'aucun', import_fait INTEGER NOT NULL DEFAULT 0, import_total INTEGER NOT NULL DEFAULT 0,
  cree_le TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS avis (
  id TEXT PRIMARY KEY, etablissement_id TEXT NOT NULL REFERENCES etablissements(id) ON DELETE CASCADE,
  source TEXT NOT NULL, id_externe TEXT, auteur TEXT NOT NULL, note INTEGER NOT NULL, texte TEXT NOT NULL DEFAULT '',
  texte_fr TEXT NOT NULL DEFAULT '', langue TEXT NOT NULL DEFAULT '', date TEXT NOT NULL,
  sentiment REAL, aspects TEXT NOT NULL DEFAULT '[]', aspects_neg TEXT NOT NULL DEFAULT '[]',
  repondu INTEGER NOT NULL DEFAULT 0, reponse TEXT NOT NULL DEFAULT '', reponse_date TEXT,
  statut TEXT NOT NULL DEFAULT 'historique', brouillon TEXT NOT NULL DEFAULT '',
  UNIQUE (etablissement_id, id_externe));
CREATE INDEX IF NOT EXISTS i_avis_etab_date ON avis (etablissement_id, date);
CREATE TABLE IF NOT EXISTS enquetes (
  id TEXT PRIMARY KEY, etablissement_id TEXT NOT NULL REFERENCES etablissements(id) ON DELETE CASCADE,
  note INTEGER NOT NULL, commentaire TEXT NOT NULL DEFAULT '', contact TEXT NOT NULL DEFAULT '',
  consentement INTEGER NOT NULL, date TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cas_rattrapage (
  id TEXT PRIMARY KEY, etablissement_id TEXT NOT NULL REFERENCES etablissements(id) ON DELETE CASCADE,
  enquete_id TEXT NOT NULL REFERENCES enquetes(id) ON DELETE CASCADE,
  statut TEXT NOT NULL DEFAULT 'ouvert' CHECK (statut IN ('ouvert','rappele','rattrape','perdu')),
  suggestion TEXT NOT NULL DEFAULT '', note_suivi TEXT NOT NULL DEFAULT '', cree_le TEXT NOT NULL, maj_le TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS actions (
  id TEXT PRIMARY KEY, etablissement_id TEXT NOT NULL REFERENCES etablissements(id) ON DELETE CASCADE,
  titre TEXT NOT NULL, sujet TEXT NOT NULL DEFAULT '', responsable TEXT NOT NULL DEFAULT '', objectif TEXT NOT NULL DEFAULT '',
  statut TEXT NOT NULL DEFAULT 'a_lancer' CHECK (statut IN ('a_lancer','en_cours','termine')),
  cree_le TEXT NOT NULL, termine_le TEXT);
CREATE TABLE IF NOT EXISTS conso_ia (
  id INTEGER PRIMARY KEY AUTOINCREMENT, utilisateur_id TEXT NOT NULL, type TEXT NOT NULL, mode TEXT NOT NULL, date TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reglages (cle TEXT PRIMARY KEY, valeur TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS journal (
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, utilisateur_id TEXT, evenement TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '');
"""


def maintenant():
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def nouvel_id():
    return str(uuid.uuid4())


def connexion():
    c = sqlite3.connect(BASE, timeout=15, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def initialiser():
    with _verrou, connexion() as c:
        c.executescript(SCHEMA)


def lire(sql, params=(), un=False):
    with connexion() as c:
        cur = c.execute(sql, params)
        lignes = cur.fetchone() if un else cur.fetchall()
    if un:
        return dict(lignes) if lignes else None
    return [dict(l) for l in lignes]


def ecrire(sql, params=()):
    with _verrou, connexion() as c:
        cur = c.execute(sql, params)
        return cur.rowcount


def ecrire_plusieurs(sql, lignes):
    with _verrou, connexion() as c:
        c.executemany(sql, lignes)


def journaliser(evenement, utilisateur_id=None, detail=""):
    ecrire("INSERT INTO journal (date, utilisateur_id, evenement, detail) VALUES (?,?,?,?)",
           (maintenant(), utilisateur_id, evenement, str(detail)[:500]))
