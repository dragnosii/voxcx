"""VoxCX : serveur web (API + interface). Lancement : python serveur.py  (ouvre http://localhost:8501)."""
import math
import os
import threading
import traceback
import webbrowser
from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
import uvicorn
from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles


class StatiqueSansCache(StaticFiles):
    async def get_response(self, path, scope):
        r = await super().get_response(path, scope)
        r.headers["Cache-Control"] = "no-cache"
        return r

# les bibliothèques d'IA sont chargées ici, avant les fils d'exécution, pour éviter les chargements simultanés
import sentence_transformers  # noqa: F401,E402
import transformers  # noqa: F401,E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: F401,E402

from voxcx import service  # noqa: E402

RACINE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(RACINE, "static")
PORT = int(os.environ.get("VOXCX_PORT", "8501"))


def propre(x):
    """Rend n'importe quel résultat sérialisable en JSON (types numpy, NaN, dates)."""
    if isinstance(x, dict):
        return {str(k): propre(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [propre(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if (math.isnan(x) or math.isinf(x)) else float(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (pd.Timestamp,)):
        return x.strftime("%Y-%m-%d")
    return x


def rep(obj, code=200):
    return JSONResponse(propre(obj), status_code=code)


def erreur(e):
    traceback.print_exc()
    return rep({"erreur": f"{type(e).__name__} : {e}"}, 500)


def filtres(request):
    q = request.query_params
    liste = lambda cle: [v for v in q.get(cle, "").split("|") if v]
    return service.filtrer(q.get("debut") or None, q.get("fin") or None, liste("hotels") or None, liste("villes") or None)


# ----------------------------------------------------------------- routes
async def index(request):
    return FileResponse(os.path.join(STATIC, "index.html"))


def api_meta(request):
    from voxcx.assistant import mode_en_ligne_disponible

    m = service.meta()
    m["en_ligne_disponible"] = mode_en_ligne_disponible()
    return rep(m)


def api_accueil(request):
    try:
        a, s = filtres(request)
        return rep(service.accueil(a, s, request.query_params.get("action", "2026-07-16")))
    except Exception as e:
        return erreur(e)


def api_themes(request):
    try:
        a, s = filtres(request)
        return rep(service.themes(a, s, int(request.query_params.get("rang", 0))))
    except Exception as e:
        return erreur(e)


def api_phrases(request):
    try:
        a, s = filtres(request)
        q = request.query_params
        return rep(service.phrases_aspect(a, s, q.get("aspect", ""), q.get("sens", "négatif")))
    except Exception as e:
        return erreur(e)


async def api_assistant(request):
    try:
        b = await request.json()
        return rep(await run(lambda: service.question(b.get("question", ""), b.get("hotel"), bool(b.get("negatifs")), int(b.get("k", 8)), b.get("mode", "local"), b.get("debut"))))
    except Exception as e:
        return erreur(e)


async def api_journal_ajout(request):
    try:
        b = await request.json()
        service.journaliser(b.get("evenement", "validation"), b.get("auteur", "Humain"), b.get("detail", ""))
        return rep({"ok": True})
    except Exception as e:
        return erreur(e)


def api_predictif(request):
    try:
        return rep(service.predictif())
    except Exception as e:
        return erreur(e)


async def api_tester(request):
    try:
        b = await request.json()
        texte = (b.get("texte") or "").strip()
        if len(texte) < 5:
            return rep({"erreur": "Texte trop court"}, 400)
        return rep(await run(lambda: service.tester_avis(texte[:3000])))
    except Exception as e:
        return erreur(e)


def api_plan(request):
    try:
        a, s = filtres(request)
        return rep({"actions": service.plan(), "aspects": service.aspects_simulables(s), "journal": service.journal(8), "experience": service.lire_experience()})
    except Exception as e:
        return erreur(e)


async def api_plan_proposer(request):
    try:
        a, s = filtres(request)
        return rep({"ajoutees": service.proposer_actions(a, s)})
    except Exception as e:
        return erreur(e)


async def api_plan_statut(request):
    try:
        b = await request.json()
        service.changer_statut(b["id"], b["statut"])
        return rep({"ok": True})
    except Exception as e:
        return erreur(e)


async def api_simulateur(request):
    try:
        b = await request.json()
        a, s = filtres(request)
        return rep(service.simulateur(a, s, b.get("aspect", ""), float(b.get("part", 50)), float(b.get("cout", 180000))))
    except Exception as e:
        return erreur(e)


async def api_experience(request):
    try:
        b = await request.json()
        service.ecrire_experience(b.get("lignes", []))
        return rep({"ok": True, "experience": service.lire_experience()})
    except Exception as e:
        return erreur(e)


def api_export(request):
    a, _ = filtres(request)
    cols = [c for c in a.columns if c not in ("url_avis", "semaine")]
    return Response(a[cols].to_csv(index=False).encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="avis_filtres.csv"'})


async def run(fonction):
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(fonction)


@asynccontextmanager
async def vie(app):
    threading.Thread(target=service.prechauffer, daemon=True).start()
    yield


app = Starlette(
    lifespan=vie,
    routes=[
        Route("/", index),
        Route("/api/meta", api_meta),
        Route("/api/accueil", api_accueil),
        Route("/api/themes", api_themes),
        Route("/api/themes/phrases", api_phrases),
        Route("/api/assistant", api_assistant, methods=["POST"]),
        Route("/api/journal", api_journal_ajout, methods=["POST"]),
        Route("/api/predictif", api_predictif),
        Route("/api/predictif/tester", api_tester, methods=["POST"]),
        Route("/api/plan", api_plan),
        Route("/api/plan/proposer", api_plan_proposer, methods=["POST"]),
        Route("/api/plan/statut", api_plan_statut, methods=["POST"]),
        Route("/api/simulateur", api_simulateur, methods=["POST"]),
        Route("/api/experience", api_experience, methods=["POST"]),
        Route("/api/export.csv", api_export),
        Mount("/static", StatiqueSansCache(directory=STATIC), name="static"),
    ],
)

if __name__ == "__main__":
    if not os.environ.get("VOXCX_NOBROWSER"):
        threading.Timer(2.0, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
