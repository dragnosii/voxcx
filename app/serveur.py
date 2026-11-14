"""VoxCX 2 : serveur web (API + interface). Lancement : python serveur.py (ouvre http://localhost:8501)."""
import json
import os
import secrets
import threading
import traceback
import webbrowser

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

# Les bibliothèques d'IA sont importées avant les fils d'exécution (évite les chargements simultanés).
import sentence_transformers  # noqa: F401,E402
import transformers  # noqa: F401,E402

from plateforme import agents, base, ia  # noqa: E402
from plateforme import securite as S  # noqa: E402
from plateforme.config import MODE_DEMO_PAIEMENT, NIVEAUX_IA, OFFRES, PORT, PRODUCTION, SECRET, STATIC  # noqa: E402

TYPES = ["Hôtel", "Riad", "Restaurant", "Café", "Autre"]
MAX_CORPS = 64 * 1024


def rep(obj, code=200):
    return JSONResponse(obj, status_code=code)


def mauvais(message="Données invalides."):
    return rep({"erreur": message}, 400)


async def corps(request):
    if int(request.headers.get("content-length") or 0) > MAX_CORPS:
        raise ValueError("trop gros")
    brut = await request.body()
    if len(brut) > MAX_CORPS:
        raise ValueError("trop gros")
    d = json.loads(brut or b"{}")
    if not isinstance(d, dict):
        raise ValueError("format")
    return d


def route(fonction):
    """Erreurs : message court pour l'utilisateur, détail seulement dans le journal serveur."""
    async def r(request):
        try:
            return await fonction(request)
        except (ValueError, KeyError, json.JSONDecodeError):
            return mauvais()
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            base.journaliser("erreur_serveur", None, f"{request.url.path} {type(e).__name__}")
            return rep({"erreur": "Une erreur est survenue. Réessayez dans un instant."}, 500)
    return r


# ----------------------------------------------------------------- pages
async def page_app(request):
    return FileResponse(os.path.join(STATIC, "index.html"))


async def page_enquete(request):
    return FileResponse(os.path.join(STATIC, "enquete.html"))


# ----------------------------------------------------------------- public : offres et enquête
@route
async def api_offres(request):
    return rep({"offres": OFFRES, "paiement_demo": MODE_DEMO_PAIEMENT})


def _etab_par_jeton(jeton):
    if not jeton or len(jeton) > 64:
        return None
    return base.lire("SELECT id, nom, ville, type, lien_avis FROM etablissements WHERE jeton_enquete=?", (jeton,), un=True)


@route
async def api_enquete_info(request):
    if not S.limite(f"enq_get:{S.ip(request)}", 60, 600):
        return S.trop()
    e = _etab_par_jeton(request.path_params["jeton"])
    if not e:
        return rep({"erreur": "Ce lien d'enquête n'existe pas ou n'est plus actif."}, 404)
    return rep({"nom": e["nom"], "ville": e["ville"], "type": e["type"]})


@route
async def api_enquete_envoyer(request):
    if not S.limite(f"enq_post:{S.ip(request)}", 5, 600):
        return S.trop("Merci, votre avis a déjà été envoyé. Réessayez plus tard si besoin.")
    e = _etab_par_jeton(request.path_params["jeton"])
    if not e:
        return rep({"erreur": "Ce lien d'enquête n'existe pas ou n'est plus actif."}, 404)
    d = await corps(request)
    note = d.get("note")
    if not isinstance(note, int) or not 1 <= note <= 5:
        return mauvais("Choisissez une note de 1 à 5.")
    commentaire = S.texte(d.get("commentaire", ""), 1500)
    consent = bool(d.get("consentement"))
    contact = S.texte(d.get("contact", ""), 120) if consent else ""
    resultat = agents.enregistrer_enquete(e, note, commentaire, contact, consent)
    lien = e["lien_avis"] if resultat == "content" and e["lien_avis"].startswith("https://") else ""
    return rep({"resultat": resultat, "lien_avis": lien})


# ----------------------------------------------------------------- comptes
@route
async def api_inscription(request):
    if not S.limite(f"inscr:{S.ip(request)}", 5, 3600):
        return S.trop()
    d = await corps(request)
    nom = S.texte(d.get("nom", ""), 80, 2)
    email = S.texte(d.get("email", ""), 190).lower()
    mot = d.get("mot", "")
    if not S.EMAIL.match(email):
        return mauvais("Adresse e-mail invalide.")
    if not isinstance(mot, str) or len(mot) < 10 or len(mot) > 200:
        return mauvais("Le mot de passe doit contenir au moins 10 caractères.")
    if base.lire("SELECT 1 FROM utilisateurs WHERE email=?", (email,), un=True):
        return mauvais("Impossible de créer ce compte avec cette adresse. Connectez-vous si vous avez déjà un compte.")
    uid = base.nouvel_id()
    base.ecrire("INSERT INTO utilisateurs (id, email, nom, hash, role, cree_le) VALUES (?,?,?,?, 'gerant', ?)",
                (uid, email, nom, S.hacher(mot), base.maintenant()))
    base.ecrire("INSERT INTO abonnements (id, utilisateur_id, offre, statut, debut, fin) VALUES (?,?,?,?,?,?)",
                (base.nouvel_id(), uid, "essai", "essai", base.maintenant(), S.fin_dans(OFFRES["essai"]["jours"])))
    base.journaliser("inscription", uid)
    S.ouvrir_session(request, {"id": uid})
    return rep({"ok": True})


@route
async def api_connexion(request):
    if not S.limite(f"cnx:{S.ip(request)}", 10, 600):
        return S.trop()
    d = await corps(request)
    email = S.texte(d.get("email", ""), 190).lower()
    mot = d.get("mot", "") if isinstance(d.get("mot"), str) else ""
    u = base.lire("SELECT * FROM utilisateurs WHERE email=?", (email,), un=True)
    message = "E-mail ou mot de passe incorrect."
    if not u:
        S.verifier(mot, S.HASH_FACTICE)
        return rep({"erreur": message}, 401)
    if u["bloque_jusqua"] and u["bloque_jusqua"] > base.maintenant():
        return S.trop("Compte bloqué quelques minutes après plusieurs essais. Réessayez plus tard.")
    if not S.verifier(mot, u["hash"]):
        echecs = u["echecs"] + 1
        bloque = None
        if echecs >= 5:  # blocage de 15 minutes après 5 échecs
            bloque = S.fin_dans(15 / 1440)
            echecs = 0
        base.ecrire("UPDATE utilisateurs SET echecs=?, bloque_jusqua=? WHERE id=?", (echecs, bloque, u["id"]))
        return rep({"erreur": message}, 401)
    base.ecrire("UPDATE utilisateurs SET echecs=0, bloque_jusqua=NULL WHERE id=?", (u["id"],))
    S.ouvrir_session(request, u)
    base.journaliser("connexion", u["id"])
    return rep({"ok": True})


@route
async def api_deconnexion(request):
    request.session.clear()
    return rep({"ok": True})


@route
async def api_moi(request):
    u = S.utilisateur_courant(request)
    if not u:
        return rep({"connecte": False, "ia_en_ligne": ia.en_ligne()})
    a = S.abonnement(u["id"])
    ok, utilise, plafond = S.quota_ia(u["id"])
    etabs = base.lire("SELECT id, nom, ville, type, lien_avis, jeton_enquete, source_connectee, import_statut, import_fait, import_total "
                      "FROM etablissements WHERE proprietaire_id=? ORDER BY cree_le", (u["id"],))
    return rep({"connecte": True, "utilisateur": {"nom": u["nom"], "email": u["email"], "role": u["role"]},
                "csrf": request.session.get("csrf"), "ia_en_ligne": ia.en_ligne(), "modele_ia": ia.modele_actuel(),
                "abonnement": None if not a else {"offre": a["offre"], "nom": a["detail"]["nom"], "statut": a["statut"],
                                                  "fin": a["fin"][:10], "actif": a["actif"], "max_etab": a["detail"]["etablissements"]},
                "quota": {"utilise": utilise, "plafond": plafond}, "etablissements": etabs, "types": TYPES})


# ----------------------------------------------------------------- établissements
def _champs_etab(d):
    nom = S.texte(d.get("nom", ""), 80, 2)
    ville = S.texte(d.get("ville", ""), 60, 2)
    type_ = d.get("type") if d.get("type") in TYPES else "Autre"
    lien = S.texte(d.get("lien_avis", ""), 300)
    if lien and not lien.startswith("https://"):
        raise ValueError("lien")
    return nom, ville, type_, lien


@route
@S.protege(ecriture=True)
async def api_etab_creer(request):
    u = request.state.u
    a = S.abonnement(u["id"])
    if not a or not a["actif"]:
        return S.refus("Votre abonnement n'est plus actif. Choisissez une offre pour continuer.", 402)
    n = base.lire("SELECT COUNT(*) n FROM etablissements WHERE proprietaire_id=?", (u["id"],), un=True)["n"]
    if n >= a["detail"]["etablissements"]:
        return S.refus(f"Votre offre permet {a['detail']['etablissements']} établissement(s). Passez à l'offre Pro pour en ajouter.", 402)
    nom, ville, type_, lien = _champs_etab(await corps(request))
    eid = base.nouvel_id()
    base.ecrire("INSERT INTO etablissements (id, proprietaire_id, nom, ville, type, lien_avis, jeton_enquete, cree_le) VALUES (?,?,?,?,?,?,?,?)",
                (eid, u["id"], nom, ville, type_, lien, secrets.token_urlsafe(12), base.maintenant()))
    return rep({"id": eid})


@route
@S.protege(ecriture=True)
async def api_etab_modifier(request):
    e = S.etablissement_du(request.state.u["id"], request.path_params["eid"])
    if not e:
        return S.refus("Établissement introuvable.", 404)
    nom, ville, type_, lien = _champs_etab(await corps(request))
    base.ecrire("UPDATE etablissements SET nom=?, ville=?, type=?, lien_avis=? WHERE id=?", (nom, ville, type_, lien, e["id"]))
    return rep({"ok": True})


@route
@S.protege(ecriture=True)
async def api_etab_supprimer(request):
    e = S.etablissement_du(request.state.u["id"], request.path_params["eid"])
    if not e:
        return S.refus("Établissement introuvable.", 404)
    base.ecrire("DELETE FROM etablissements WHERE id=?", (e["id"],))
    base.journaliser("etab_supprime", request.state.u["id"], e["nom"])
    return rep({"ok": True})


@route
@S.protege()
async def api_fiches_demo(request):
    return rep({"fiches": agents.fiches_demo()})


@route
@S.protege(ecriture=True)
async def api_connecter(request):
    e = S.etablissement_du(request.state.u["id"], request.path_params["eid"])
    if not e:
        return S.refus("Établissement introuvable.", 404)
    if e["import_statut"] == "en_cours":
        return mauvais("Un import est déjà en cours.")
    fiche = (await corps(request)).get("fiche", "")
    if fiche not in {f["fiche"] for f in agents.fiches_demo()}:
        return mauvais("Fiche inconnue.")
    if not S.limite(f"import:{request.state.u['id']}", 3, 3600):
        return S.trop()
    agents.lancer_import(e["id"], fiche)
    return rep({"ok": True})


@route
@S.protege()
async def api_import_etat(request):
    e = S.etablissement_du(request.state.u["id"], request.path_params["eid"])
    if not e:
        return S.refus("Établissement introuvable.", 404)
    return rep({k: e[k] for k in ("import_statut", "import_fait", "import_total", "source_connectee")})


@route
@S.protege()
async def api_tableau(request):
    e = S.etablissement_du(request.state.u["id"], request.path_params["eid"])
    if not e:
        return S.refus("Établissement introuvable.", 404)
    return rep(agents.tableau(e["id"]))


# ----------------------------------------------------------------- Réponse aux avis
def _avis_du(uid, aid):
    return base.lire("SELECT a.*, e.nom AS etab_nom FROM avis a JOIN etablissements e ON e.id=a.etablissement_id "
                     "WHERE a.id=? AND e.proprietaire_id=?", (aid, uid), un=True)


@route
@S.protege()
async def api_file_reponses(request):
    e = S.etablissement_du(request.state.u["id"], request.path_params["eid"])
    if not e:
        return S.refus("Établissement introuvable.", 404)
    return rep({"avis": agents.file_reponses(e["id"])})


@route
@S.protege(ecriture=True)
async def api_brouillon(request):
    uid = request.state.u["id"]
    a = _avis_du(uid, request.path_params["aid"])
    if not a:
        return S.refus("Avis introuvable.", 404)
    if not S.limite(f"ia:{uid}", 12, 60):
        return S.trop("Trop de demandes d'un coup. Patientez une minute.")
    ok, utilise, plafond = S.quota_ia(uid)
    if not ok:
        return S.refus(f"Vous avez utilisé vos {plafond} actions IA du mois. Passez à l'offre supérieure pour continuer.", 402)
    ton = "chaleureux" if (await corps(request)).get("ton") == "chaleureux" else "formel"
    a["aspects_neg_liste"] = json.loads(a["aspects_neg"] or "[]")
    texte, mode = ia.brouillon(a, ton, a["etab_nom"])
    ia.compter(uid, "brouillon", mode)
    base.ecrire("UPDATE avis SET brouillon=?, statut='brouillon' WHERE id=?", (texte, a["id"]))
    return rep({"texte": texte, "mode": mode})


@route
@S.protege(ecriture=True)
async def api_publier(request):
    uid = request.state.u["id"]
    a = _avis_du(uid, request.path_params["aid"])
    if not a:
        return S.refus("Avis introuvable.", 404)
    texte = S.texte((await corps(request)).get("texte", ""), 3000, 10)
    base.ecrire("UPDATE avis SET reponse=?, repondu=1, reponse_date=?, statut='repondu', brouillon='' WHERE id=?",
                (texte, base.maintenant(), a["id"]))
    base.journaliser("reponse_publiee", uid, a["id"])
    return rep({"ok": True, "publie_sur_google": False})


@route
@S.protege(ecriture=True)
async def api_ignorer(request):
    a = _avis_du(request.state.u["id"], request.path_params["aid"])
    if not a:
        return S.refus("Avis introuvable.", 404)
    base.ecrire("UPDATE avis SET statut='historique' WHERE id=?", (a["id"],))
    return rep({"ok": True})


# ----------------------------------------------------------------- Rattrapage
@route
@S.protege()
async def api_cas(request):
    e = S.etablissement_du(request.state.u["id"], request.path_params["eid"])
    if not e:
        return S.refus("Établissement introuvable.", 404)
    cas = base.lire("SELECT c.id, c.statut, c.suggestion, c.note_suivi, c.cree_le, q.note, q.commentaire, q.contact "
                    "FROM cas_rattrapage c JOIN enquetes q ON q.id=c.enquete_id WHERE c.etablissement_id=? "
                    "ORDER BY CASE c.statut WHEN 'ouvert' THEN 0 WHEN 'rappele' THEN 1 ELSE 2 END, c.cree_le DESC LIMIT 200", (e["id"],))
    enq = base.lire("SELECT COUNT(*) n, AVG(note) m, SUM(note>=4) c FROM enquetes WHERE etablissement_id=?", (e["id"],), un=True)
    return rep({"cas": cas, "enquetes": enq})


@route
@S.protege(ecriture=True)
async def api_cas_statut(request):
    uid = request.state.u["id"]
    c = base.lire("SELECT c.id FROM cas_rattrapage c JOIN etablissements e ON e.id=c.etablissement_id WHERE c.id=? AND e.proprietaire_id=?",
                  (request.path_params["cid"], uid), un=True)
    if not c:
        return S.refus("Cas introuvable.", 404)
    d = await corps(request)
    statut = d.get("statut")
    if statut not in ("ouvert", "rappele", "rattrape", "perdu"):
        return mauvais()
    note = S.texte(d.get("note_suivi", ""), 500)
    base.ecrire("UPDATE cas_rattrapage SET statut=?, note_suivi=?, maj_le=? WHERE id=?", (statut, note, base.maintenant(), c["id"]))
    return rep({"ok": True})


# ----------------------------------------------------------------- Analyste et actions
@route
@S.protege(ecriture=True)
async def api_question(request):
    uid = request.state.u["id"]
    e = S.etablissement_du(uid, request.path_params["eid"])
    if not e:
        return S.refus("Établissement introuvable.", 404)
    if not S.limite(f"ia:{uid}", 12, 60):
        return S.trop("Trop de demandes d'un coup. Patientez une minute.")
    ok, _, plafond = S.quota_ia(uid)
    if not ok:
        return S.refus(f"Vous avez utilisé vos {plafond} actions IA du mois.", 402)
    q = S.texte((await corps(request)).get("question", ""), 300, 3)
    res = agents.question(e, q)
    ia.compter(uid, "question", res["mode"])
    return rep(res)


@route
@S.protege()
async def api_actions(request):
    e = S.etablissement_du(request.state.u["id"], request.path_params["eid"])
    if not e:
        return S.refus("Établissement introuvable.", 404)
    actions = base.lire("SELECT * FROM actions WHERE etablissement_id=? ORDER BY cree_le DESC", (e["id"],))
    for x in actions:
        x["mesure"] = agents.mesurer_action(x)
    return rep({"actions": actions})


@route
@S.protege()
async def api_strategie(request):
    e = S.etablissement_du(request.state.u["id"], request.path_params["eid"])
    if not e:
        return S.refus("Établissement introuvable.", 404)
    return rep({"propositions": agents.propositions(e["id"]), "prevision": agents.prevision(e["id"])})


@route
@S.protege(ecriture=True)
async def api_resume(request):
    uid = request.state.u["id"]
    e = S.etablissement_du(uid, request.path_params["eid"])
    if not e:
        return S.refus("Établissement introuvable.", 404)
    if not S.limite(f"ia:{uid}", 12, 60):
        return S.trop("Trop de demandes d'un coup. Patientez une minute.")
    ok, _, plafond = S.quota_ia(uid)
    if not ok:
        return S.refus(f"Vous avez utilisé vos {plafond} actions IA du mois.", 402)
    texte, mode = agents.resume_semaine(e)
    ia.compter(uid, "resume", mode)
    return rep({"texte": texte, "mode": mode})


@route
@S.protege()
async def api_fidelisation(request):
    e = S.etablissement_du(request.state.u["id"], request.path_params["eid"])
    if not e:
        return S.refus("Établissement introuvable.", 404)
    return rep(agents.fidelisation(e))


@route
@S.protege(ecriture=True)
async def api_action_creer(request):
    e = S.etablissement_du(request.state.u["id"], request.path_params["eid"])
    if not e:
        return S.refus("Établissement introuvable.", 404)
    d = await corps(request)
    base.ecrire("INSERT INTO actions (id, etablissement_id, titre, sujet, responsable, objectif, cree_le) VALUES (?,?,?,?,?,?,?)",
                (base.nouvel_id(), e["id"], S.texte(d.get("titre", ""), 160, 3), S.texte(d.get("sujet", ""), 80),
                 S.texte(d.get("responsable", ""), 80), S.texte(d.get("objectif", ""), 160), base.maintenant()))
    return rep({"ok": True})


@route
@S.protege(ecriture=True)
async def api_action_statut(request):
    uid = request.state.u["id"]
    x = base.lire("SELECT a.id FROM actions a JOIN etablissements e ON e.id=a.etablissement_id WHERE a.id=? AND e.proprietaire_id=?",
                  (request.path_params["xid"], uid), un=True)
    if not x:
        return S.refus("Action introuvable.", 404)
    statut = (await corps(request)).get("statut")
    if statut not in ("a_lancer", "en_cours", "termine"):
        return mauvais()
    base.ecrire("UPDATE actions SET statut=?, termine_le=? WHERE id=?",
                (statut, base.maintenant() if statut == "termine" else None, x["id"]))
    return rep({"ok": True})


# ----------------------------------------------------------------- abonnement
@route
@S.protege(ecriture=True)
async def api_payer(request):
    """Paiement de DÉMONSTRATION : aucun moyen de paiement réel. Montant calculé ici, jamais lu depuis le navigateur.
    En production : page de paiement hébergée du prestataire + webhook signé qui active l'abonnement."""
    if not MODE_DEMO_PAIEMENT:
        return S.refus("Le paiement en ligne n'est pas encore activé.", 503)
    uid = request.state.u["id"]
    if not S.limite(f"payer:{uid}", 5, 3600):
        return S.trop()
    offre = (await corps(request)).get("offre")
    if offre not in ("essentiel", "pro"):
        return mauvais("Offre inconnue.")
    o = OFFRES[offre]
    base.ecrire("INSERT INTO paiements (id, utilisateur_id, offre, montant_centimes, mode, date) VALUES (?,?,?,?, 'demo', ?)",
                (base.nouvel_id(), uid, offre, o["prix"], base.maintenant()))
    base.ecrire("UPDATE abonnements SET statut='termine' WHERE utilisateur_id=? AND statut IN ('essai','actif')", (uid,))
    base.ecrire("INSERT INTO abonnements (id, utilisateur_id, offre, statut, debut, fin) VALUES (?,?,?,?,?,?)",
                (base.nouvel_id(), uid, offre, "actif", base.maintenant(), S.fin_dans(o["jours"])))
    base.journaliser("abonnement_demo", uid, offre)
    return rep({"ok": True})


# ----------------------------------------------------------------- administration
@route
@S.protege(admin=True)
async def api_admin(request):
    from datetime import datetime

    mois = datetime.now().strftime("%Y-%m-01")
    comptes = base.lire(
        "SELECT u.nom, u.email, u.role, u.cree_le, "
        "(SELECT offre FROM abonnements a WHERE a.utilisateur_id=u.id ORDER BY a.fin DESC LIMIT 1) AS offre, "
        "(SELECT fin FROM abonnements a WHERE a.utilisateur_id=u.id ORDER BY a.fin DESC LIMIT 1) AS fin, "
        "(SELECT COUNT(*) FROM etablissements e WHERE e.proprietaire_id=u.id) AS etablissements, "
        "(SELECT COUNT(*) FROM conso_ia c WHERE c.utilisateur_id=u.id AND c.date>=?) AS ia_mois "
        "FROM utilisateurs u ORDER BY u.cree_le DESC LIMIT 500", (mois,))
    revenus = base.lire("SELECT offre, COUNT(*) n, SUM(montant_centimes) total FROM paiements GROUP BY offre")
    conso = base.lire("SELECT type, mode, COUNT(*) n FROM conso_ia WHERE date>=? GROUP BY type, mode", (mois,))
    totaux = base.lire("SELECT (SELECT COUNT(*) FROM etablissements) etab, (SELECT COUNT(*) FROM avis) avis, "
                       "(SELECT COUNT(*) FROM enquetes) enquetes, (SELECT COUNT(*) FROM cas_rattrapage) cas", un=True)
    journal = base.lire("SELECT date, evenement, detail FROM journal ORDER BY id DESC LIMIT 60")
    return rep({"comptes": comptes, "revenus": revenus, "conso": conso, "totaux": totaux, "journal": journal,
                "ia_en_ligne": ia.en_ligne(), "paiement_demo": MODE_DEMO_PAIEMENT,
                "niveaux": NIVEAUX_IA, "niveau": ia.niveau_actuel(), "modele": ia.modele_actuel(),
                "openrouter": bool(ia.cle_openrouter())})


@route
@S.protege(admin=True, ecriture=True)
async def api_admin_niveau(request):
    niveau = (await corps(request)).get("niveau")
    if niveau not in NIVEAUX_IA:
        return mauvais("Niveau inconnu.")
    base.ecrire("INSERT INTO reglages (cle, valeur) VALUES ('niveau_ia', ?) ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur", (niveau,))
    base.journaliser("niveau_ia", request.state.u["id"], NIVEAUX_IA[niveau]["modele"])
    return rep({"ok": True})


# ----------------------------------------------------------------- en-têtes de sécurité
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
       "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


class EnTetes(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        r = await call_next(request)
        r.headers["Content-Security-Policy"] = CSP
        r.headers["X-Content-Type-Options"] = "nosniff"
        r.headers["Referrer-Policy"] = "same-origin"
        r.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        r.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/") or request.url.path == "/" or request.url.path.startswith("/e/"):
            r.headers["Cache-Control"] = "no-store"
        else:
            r.headers["Cache-Control"] = "no-cache"
        if PRODUCTION:
            r.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return r


eid = "{eid:str}"
app = Starlette(
    routes=[
        Route("/", page_app),
        Route("/e/{jeton:str}", page_enquete),
        Route("/api/offres", api_offres),
        Route("/api/public/enquete/{jeton:str}", api_enquete_info),
        Route("/api/public/enquete/{jeton:str}", api_enquete_envoyer, methods=["POST"]),
        Route("/api/inscription", api_inscription, methods=["POST"]),
        Route("/api/connexion", api_connexion, methods=["POST"]),
        Route("/api/deconnexion", api_deconnexion, methods=["POST"]),
        Route("/api/moi", api_moi),
        Route("/api/fiches-demo", api_fiches_demo),
        Route("/api/etablissements", api_etab_creer, methods=["POST"]),
        Route(f"/api/etablissements/{eid}/modifier", api_etab_modifier, methods=["POST"]),
        Route(f"/api/etablissements/{eid}/supprimer", api_etab_supprimer, methods=["POST"]),
        Route(f"/api/etablissements/{eid}/connecter", api_connecter, methods=["POST"]),
        Route(f"/api/etablissements/{eid}/import", api_import_etat),
        Route(f"/api/etablissements/{eid}/tableau", api_tableau),
        Route(f"/api/etablissements/{eid}/reponses", api_file_reponses),
        Route(f"/api/etablissements/{eid}/rattrapage", api_cas),
        Route(f"/api/etablissements/{eid}/question", api_question, methods=["POST"]),
        Route(f"/api/etablissements/{eid}/actions", api_actions),
        Route(f"/api/etablissements/{eid}/strategie", api_strategie),
        Route(f"/api/etablissements/{eid}/resume", api_resume, methods=["POST"]),
        Route(f"/api/etablissements/{eid}/fidelisation", api_fidelisation),
        Route(f"/api/etablissements/{eid}/actions", api_action_creer, methods=["POST"]),
        Route("/api/avis/{aid:str}/brouillon", api_brouillon, methods=["POST"]),
        Route("/api/avis/{aid:str}/publier", api_publier, methods=["POST"]),
        Route("/api/avis/{aid:str}/ignorer", api_ignorer, methods=["POST"]),
        Route("/api/cas/{cid:str}/statut", api_cas_statut, methods=["POST"]),
        Route("/api/actions/{xid:str}/statut", api_action_statut, methods=["POST"]),
        Route("/api/abonnement/payer", api_payer, methods=["POST"]),
        Route("/api/admin/vue", api_admin),
        Route("/api/admin/niveau-ia", api_admin_niveau, methods=["POST"]),
        Mount("/static", StaticFiles(directory=STATIC), name="static"),
    ],
    middleware=[
        Middleware(EnTetes),
        Middleware(SessionMiddleware, secret_key=SECRET, session_cookie="voxcx", max_age=7 * 24 * 3600,
                   same_site="strict", https_only=PRODUCTION),
    ],
)

base.initialiser()

if __name__ == "__main__":
    adresse = f"http://localhost:{PORT}"
    if os.environ.get("VOXCX_SANS_NAVIGATEUR") != "1":
        threading.Timer(2.5, lambda: webbrowser.open(adresse)).start()
    print(f"VoxCX 2 démarre sur {adresse}")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
