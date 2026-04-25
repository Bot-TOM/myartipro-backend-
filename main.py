import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

from routers import auth, clients, devis, pdf, factures, stripe_routes, rappels, modeles, push
from services.relance_service import relancer_devis_sans_reponse, relancer_factures_impayees

scheduler = AsyncIOScheduler(timezone="Europe/Paris")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        scheduler.add_job(
            relancer_devis_sans_reponse,
            CronTrigger(hour=9, minute=0),
            id="relance_devis",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        scheduler.add_job(
            relancer_factures_impayees,
            CronTrigger(hour=9, minute=15),
            id="relance_factures",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        scheduler.start()
        print("[scheduler] démarré — devis 09:00 + factures 09:15 Europe/Paris")
    except Exception as e:
        print(f"[scheduler] erreur démarrage: {e}")
    try:
        yield
    finally:
        try:
            scheduler.shutdown(wait=False)
            print("[scheduler] arrêté")
        except Exception as e:
            print(f"[scheduler] erreur arrêt: {e}")


limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app = FastAPI(title="MyArtipro API", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(clients.router, prefix="/clients", tags=["Clients"])
app.include_router(devis.router, prefix="/devis", tags=["Devis"])
app.include_router(factures.router, prefix="/factures", tags=["Factures"])
app.include_router(stripe_routes.router, prefix="/stripe", tags=["Stripe"])
app.include_router(pdf.router, prefix="/pdf", tags=["PDF"])
app.include_router(rappels.router, prefix="/rappels", tags=["Rappels"])
app.include_router(modeles.router, prefix="/modeles", tags=["Modeles"])
app.include_router(push.router, prefix="/push", tags=["Push"])


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/")
async def root():
    return {"message": "MyArtipro API is running"}


@app.post("/admin/relances/devis", tags=["Admin"])
async def trigger_relances_devis():
    """Déclenche manuellement la relance devis (test/debug)."""
    await relancer_devis_sans_reponse()
    return {"message": "Relances devis exécutées"}


@app.post("/admin/relances/factures", tags=["Admin"])
async def trigger_relances_factures():
    """Déclenche manuellement la relance factures (test/debug)."""
    await relancer_factures_impayees()
    return {"message": "Relances factures exécutées"}


@app.get("/health")
async def health():
    checks = {
        "SUPABASE_URL": bool(os.getenv("SUPABASE_URL")),
        "SUPABASE_KEY": bool(os.getenv("SUPABASE_KEY")),
        "SUPABASE_SERVICE_KEY": bool(os.getenv("SUPABASE_SERVICE_KEY")),
        "RESEND_API_KEY": bool(os.getenv("RESEND_API_KEY")),
        "STRIPE_SECRET_KEY": bool(os.getenv("STRIPE_SECRET_KEY")),
        "STRIPE_WEBHOOK_SECRET": bool(os.getenv("STRIPE_WEBHOOK_SECRET")),
    }
    ok = all(checks.values())
    return {"status": "ok" if ok else "degraded", "checks": checks}
