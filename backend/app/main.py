import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, core_management, gnb, status, subscribers
from app.services import open5gs_client, throughput_sampler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("dashboard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.auth_enabled:
        logger.warning(
            "⚠ AUTENTICACIÓN DESACTIVADA — no recomendado fuera de un entorno "
            "de laboratorio aislado. Actívala con AUTH_ENABLED=true en el .env."
        )
    else:
        logger.info("Autenticación activada (valor por defecto).")

    throughput_sampler.start()
    yield
    await throughput_sampler.stop()
    await open5gs_client.close_clients()


app = FastAPI(
    title="Panel de monitorización y gestión 5G",
    description="Backend del panel — TFG Juan Barco Gil",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(status.router)
app.include_router(gnb.router)
app.include_router(core_management.router)
app.include_router(subscribers.router)


@app.get("/health", tags=["salud"])
async def health():
    """Comprobación trivial de que el propio backend está vivo."""
    return {"status": "ok"}
