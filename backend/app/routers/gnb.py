from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.auth import require_auth
from app.config import settings
from app.models.management import (
    GnbActionResult,
    GnbConfig,
    GnbHardwareStatus,
    GnbLogsResponse,
    GnbPresetListResponse,
    SavedGnbConfig,
    SavedGnbConfigListResponse,
    SetPresetsPathRequest,
)
from app.services import gnb_control, gnb_custom_presets

router = APIRouter(prefix="/gnb", tags=["gestión: gNB"])


@router.get("/config", response_model=GnbConfig)
async def get_gnb_config(_: str = Depends(require_auth)):
    """Configuración actual del gNB (banda, ancho de banda, srate, ganancias)."""
    try:
        return gnb_control.read_config()
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(
            status_code=500, detail=f"No se pudo leer la configuración del gNB: {exc}"
        )


@router.get("/presets", response_model=GnbPresetListResponse)
async def get_gnb_presets(_: str = Depends(require_auth)):
    """
    Combinaciones de banda/ARFCN/ancho de banda/SCS/srate ya verificadas
    en este trabajo -- recomendadas frente a introducir estos valores de
    forma libre e independiente, dado que no son campos ortogonales entre
    sí (ver Implementación y Desarrollo, incidencia real de configuración
    inválida de PRACH/srate sufrida durante el desarrollo).
    """
    return GnbPresetListResponse(presets=gnb_control.get_presets())


@router.get("/custom-presets", response_model=SavedGnbConfigListResponse)
async def list_custom_presets(_: str = Depends(require_auth)):
    """Configuraciones del gNB guardadas por el propio usuario desde el panel."""
    return SavedGnbConfigListResponse(
        presets=gnb_custom_presets.list_custom_presets(),
        storage_path=gnb_custom_presets.get_effective_path(),
    )


@router.put("/custom-presets/path")
async def set_custom_presets_path(body: SetPresetsPathRequest, _: str = Depends(require_auth)):
    """
    Cambia dónde se guardan las configuraciones personalizadas. Un
    navegador no puede abrir un diálogo nativo que navegue por el sistema
    de ficheros del SERVIDOR (los navegadores lo impiden deliberadamente,
    por seguridad); en su lugar, se escribe la ruta exacta deseada, que
    se valida (debe ser absoluta y escribible) y se migra automáticamente
    lo ya guardado si la nueva ruta todavía no existe.
    """
    success, detail = gnb_custom_presets.set_path(body.path)
    if not success:
        raise HTTPException(status_code=400, detail=detail)
    return {"detail": detail}


@router.post("/custom-presets", status_code=201)
async def save_custom_preset(preset: SavedGnbConfig, _: str = Depends(require_auth)):
    """Guarda (o sustituye, si ya existía) una configuración con ese nombre."""
    gnb_custom_presets.save_custom_preset(preset.name, preset.config)
    return {"detail": f"Configuración '{preset.name}' guardada correctamente"}


@router.delete("/custom-presets/{name}")
async def delete_custom_preset(name: str, _: str = Depends(require_auth)):
    deleted = gnb_custom_presets.delete_custom_preset(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No existe ninguna configuración '{name}'")
    return {"detail": f"Configuración '{name}' eliminada correctamente"}


@router.get("/hardware", response_model=GnbHardwareStatus)
async def get_gnb_hardware(_: str = Depends(require_auth)):
    """
    Estado de ejecución y hardware SDR detectado en el último arranque.
    Nota de portabilidad: el nombre del dispositivo se lee de una línea
    de log específica del controlador UHD actualmente gestionado por este
    backend -- ver docstring de gnb_control.detected_hardware().
    """
    return GnbHardwareStatus(
        running=await gnb_control.is_running(),
        detected_device=gnb_control.detected_hardware(),
    )


@router.get("/logs", response_model=GnbLogsResponse)
async def get_gnb_logs(
    tail: int = Query(default=100, ge=1, le=1000),
    mode: str = Query(default="tail", pattern="^(head|tail)$"),
    search: str | None = Query(default=None, max_length=200),
    _: str = Depends(require_auth),
):
    """
    Líneas del log real y detallado del gNB (no del log de arranque de
    gnb_ctl.sh -- ver Implementación y Desarrollo, incidencia real de este
    trabajo sobre la diferencia entre ambos). `mode=head` muestra las
    primeras líneas (información de arranque); `mode=tail` (por defecto),
    las últimas. Si se indica `search`, se ignoran `tail`/`mode` y se
    devuelven todas las líneas de todo el fichero que lo contengan.
    """
    success, output = gnb_control.get_logs(tail, mode, search)
    return GnbLogsResponse(success=success, logs=output)


@router.get("/logs/download")
async def download_gnb_logs(_: str = Depends(require_auth)):
    """
    Descarga el fichero de log completo del gNB, sin cargarlo en memoria
    del backend ni renderizarlo en el navegador -- para cuando de verdad
    se necesite ver todo, en vez de un extracto (inicio/final/búsqueda).
    """
    if not Path(settings.gnb_log_path).exists():
        raise HTTPException(
            status_code=404,
            detail=f"No existe {settings.gnb_log_path} todavía -- el gNB no ha arrancado nunca.",
        )
    return FileResponse(
        settings.gnb_log_path, filename="gnb.log", media_type="text/plain"
    )


@router.put("/config", response_model=GnbActionResult)
async def update_gnb_config(new_config: GnbConfig, _: str = Depends(require_auth)):
    """
    Actualiza la configuración del gNB y lo reinicia con los nuevos valores.

    Nota: esta operación INTERRUMPE el servicio de radio mientras el gNB
    se reinicia -- ver la advertencia de alcance en la Metodología del TFG
    sobre las implicaciones de dar capacidad de actuación al panel.
    """
    try:
        gnb_control.write_config(new_config)
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(
            status_code=500, detail=f"No se pudo escribir la configuración del gNB: {exc}"
        )

    success, detail = await gnb_control.restart()
    return GnbActionResult(action="restart", success=success, detail=detail)


@router.post("/start", response_model=GnbActionResult)
async def start_gnb(_: str = Depends(require_auth)):
    """Arranca el gNB con la configuración actual del disco, sin
    modificarla (a diferencia de PUT /gnb/config)."""
    success, detail = await gnb_control.start()
    return GnbActionResult(action="start", success=success, detail=detail)


@router.post("/stop", response_model=GnbActionResult)
async def stop_gnb(_: str = Depends(require_auth)):
    success, detail = await gnb_control.stop()
    return GnbActionResult(action="stop", success=success, detail=detail)
