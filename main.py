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

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)
load_dotenv(env_path.parent / ".env")

from routers import auth, clients, devis, pdf, factures, stripe_routes, rappels


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Démarrage scheduler relances
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from services.relance_service import relancer_devis_sans_reponse

        scheduler = BackgroundScheduler()
        scheduler.add_job(relancer_devis_sans_reponse, "cron", hour=8, minute=0, id="relance_devis")
        scheduler.start()
        app.state.scheduler = scheduler
        print("[Scheduler] Démarré")
    except Exception as e:
        print(f"[Scheduler] ERREUR démarrage: {e}")
        app.state.scheduler = None

    yield

    # Arrêt scheduler
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler:
        try:
            scheduler.shutdown(wait=False)
            print("[Scheduler] Arrêté")
        except Exception:
            pass


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


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/")
async def root():
    return {"message": "MyArtipro API is running"}


@app.get("/health")
async def health():
    checks = {
        "SUPABASE_URL": bool(os.getenv("SUPABASE_URL")),
        "SUPABASE_KEY": bool(os.getenv("SUPABASE_KEY")),
        "SUPABASE_SERVICE_KEY": bool(os.getenv("SUPABASE_SERVICE_KEY")),
        "RESEND_API_KEY": bool(os.getenv("RESEND_API_KEY")),
        "scheduler": getattr(app.state, "scheduler", None) is not None,
    }
    ok = all(v for k, v in checks.items() if k != "scheduler")
    return {"status": "ok" if ok else "degraded", "checks": checks}
