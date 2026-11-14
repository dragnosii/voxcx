"""Sécurité : mots de passe hachés (scrypt), limites de débit, jeton CSRF, contrôles d'accès côté serveur."""
import hashlib
import hmac
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

from starlette.responses import JSONResponse

from plateforme import base
from plateforme.config import OFFRES

# ----------------------------------------------------------------- mots de passe
_N, _R, _P = 2 ** 14, 8, 1


def hacher(mot):
    sel = secrets.token_bytes(16)
    h = hashlib.scrypt(mot.encode("utf-8"), salt=sel, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${sel.hex()}${h.hex()}"


def verifier(mot, stocke):
    try:
        _, n, r, p, sel, h = stocke.split("$")
        calc = hashlib.scrypt(mot.encode("utf-8"), salt=bytes.fromhex(sel), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc.hex(), h)
    except (ValueError, TypeError):
        return False


# Hachage factice pour garder le même temps de réponse quand l'e-mail n'existe pas.
HASH_FACTICE = hacher(secrets.token_urlsafe(16))

EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[a-z]{2,24}$", re.I)


# ----------------------------------------------------------------- limites de débit (mémoire)
_compteurs = defaultdict(deque)
_verrou = threading.Lock()


def limite(cle, maximum, fenetre_s):
    """Renvoie True si l'appel est autorisé. Fenêtre glissante par clé (IP, compte...)."""
    now = time.monotonic()
    with _verrou:
        q = _compteurs[cle]
        while q and now - q[0] > fenetre_s:
            q.popleft()
        if len(q) >= maximum:
            return False
        q.append(now)
        return True


def ip(request):
    return request.client.host if request.client else "inconnue"


def trop(message="Trop de tentatives. Réessayez dans quelques minutes."):
    return JSONResponse({"erreur": message}, status_code=429)


def refus(message="Accès refusé.", code=403):
    return JSONResponse({"erreur": message}, status_code=code)


# ----------------------------------------------------------------- session et CSRF
def ouvrir_session(request, utilisateur):
    request.session.clear()  # nouvelle session à chaque connexion
    request.session["uid"] = utilisateur["id"]
    request.session["csrf"] = secrets.token_urlsafe(32)
    request.session["depuis"] = int(time.time())


def utilisateur_courant(request):
    uid = request.session.get("uid")
    if not uid:
        return None
    return base.lire("SELECT id, email, nom, role, cree_le FROM utilisateurs WHERE id=?", (uid,), un=True)


def csrf_ok(request):
    attendu = request.session.get("csrf", "")
    recu = request.headers.get("x-csrf", "")
    return bool(attendu) and hmac.compare_digest(attendu, recu)


def protege(admin=False, ecriture=False):
    """Décorateur de route : session obligatoire, rôle admin si demandé, jeton CSRF sur les écritures."""
    def deco(fonction):
        async def route(request):
            u = utilisateur_courant(request)
            if not u:
                return refus("Connectez-vous pour continuer.", 401)
            if admin and u["role"] != "admin":
                return refus("Cette page est réservée à l'administrateur.", 403)
            if ecriture and not csrf_ok(request):
                return refus("Session expirée. Rechargez la page.", 403)
            request.state.u = u
            return await fonction(request)
        return route
    return deco


# ----------------------------------------------------------------- abonnement et propriété
def abonnement(uid):
    a = base.lire("SELECT * FROM abonnements WHERE utilisateur_id=? ORDER BY fin DESC LIMIT 1", (uid,), un=True)
    if not a:
        return None
    a["actif"] = a["statut"] in ("essai", "actif") and a["fin"] >= base.maintenant()
    a["detail"] = OFFRES.get(a["offre"], OFFRES["essai"])
    return a


def etablissement_du(uid, eid):
    """Anti-IDOR : renvoie l'établissement seulement s'il appartient à l'utilisateur."""
    if not eid:
        return None
    return base.lire("SELECT * FROM etablissements WHERE id=? AND proprietaire_id=?", (eid, uid), un=True)


def quota_ia(uid):
    """(autorisé, utilisé, plafond) pour le mois en cours selon l'offre."""
    a = abonnement(uid)
    if not a or not a["actif"]:
        return False, 0, 0
    plafond = a["detail"]["ia_mois"]
    debut_mois = datetime.now().strftime("%Y-%m-01")
    utilise = base.lire("SELECT COUNT(*) n FROM conso_ia WHERE utilisateur_id=? AND date>=?", (uid, debut_mois), un=True)["n"]
    return utilise < plafond, utilise, plafond


def fin_dans(jours):
    return (datetime.now() + timedelta(days=jours)).replace(microsecond=0).isoformat(sep=" ")


def texte(valeur, maxi, mini=0):
    """Nettoie une entrée texte : type, longueur, espaces. Lève ValueError si invalide."""
    if not isinstance(valeur, str):
        raise ValueError("format")
    v = valeur.strip()
    if len(v) < mini or len(v) > maxi:
        raise ValueError("longueur")
    return v
