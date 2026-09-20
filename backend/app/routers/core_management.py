from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.auth import require_auth
from app.models.management import CoreActionResult, NfActionResult, NfLogsResponse
from app.services import docker_control

router = APIRouter(prefix="/core", tags=["gestión: core"])


@router.post("/up", response_model=CoreActionResult)
async def core_up(_: str = Depends(require_auth)):
    """Levanta las 10 NFs de una vez ('docker compose up -d'), sin tener
    que arrancarlas una por una desde el panel."""
    success, detail = await docker_control.core_up()
    return CoreActionResult(action="up", success=success, detail=detail)


@router.post("/down", response_model=CoreActionResult)
async def core_down(_: str = Depends(require_auth)):
    """Detiene y elimina los 10 contenedores del core ('docker compose down')."""
    success, detail = await docker_control.core_down()
    return CoreActionResult(action="down", success=success, detail=detail)


@router.post("/services/{nf_name}/start", response_model=NfActionResult)
async def start_nf(nf_name: str, _: str = Depends(require_auth)):
    success, detail = await docker_control.start_service(nf_name)
    return NfActionResult(nf=nf_name, action="start", success=success, detail=detail)


@router.post("/services/{nf_name}/stop", response_model=NfActionResult)
async def stop_nf(nf_name: str, _: str = Depends(require_auth)):
    success, detail = await docker_control.stop_service(nf_name)
    return NfActionResult(nf=nf_name, action="stop", success=success, detail=detail)


@router.post("/services/{nf_name}/restart", response_model=NfActionResult)
async def restart_nf(nf_name: str, _: str = Depends(require_auth)):
    success, detail = await docker_control.restart_service(nf_name)
    return NfActionResult(nf=nf_name, action="restart", success=success, detail=detail)


@router.get("/services/{nf_name}/logs", response_model=NfLogsResponse)
async def get_nf_logs(
    nf_name: str,
    tail: int = Query(default=100, ge=1, le=1000, description="Número de líneas a devolver"),
    _: str = Depends(require_auth),
):
    """Últimas líneas del log del contenedor de la NF, vía 'docker compose logs'."""
    success, output = await docker_control.get_logs(nf_name, tail)
    return NfLogsResponse(nf=nf_name, success=success, logs=output)


@router.get("/services/{nf_name}/logs/search", response_model=NfLogsResponse)
async def search_nf_logs(
    nf_name: str,
    q: str = Query(min_length=1, max_length=200, description="Texto a buscar"),
    _: str = Depends(require_auth),
):
    """
    Busca `q` en TODO el log de la NF (no solo en la ventana de `tail`),
    devolviendo únicamente las líneas que coinciden -- para encontrar
    información sin depender de en qué punto del log esté.
    """
    success, output = await docker_control.search_logs(nf_name, q)
    return NfLogsResponse(nf=nf_name, success=success, logs=output)


@router.get("/services/{nf_name}/logs/download")
async def download_nf_logs(nf_name: str, _: str = Depends(require_auth)):
    """
    Descarga el log COMPLETO de la NF, sin límite de líneas -- para cuando
    de verdad se necesite ver todo, en vez de un extracto. Se ofrece como
    descarga de texto, no renderizado en pantalla, por el mismo motivo que
    limitamos get_logs() a 1000 líneas (evitar sobrecargar el navegador
    con un contenedor de larga duración).
    """
    success, output = await docker_control.get_full_logs(nf_name)
    if not success:
        raise HTTPException(status_code=400, detail=output)
    return PlainTextResponse(
        output,
        headers={"Content-Disposition": f'attachment; filename="{nf_name}.log"'},
    )
