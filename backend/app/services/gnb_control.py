"""
Control del gNB: lectura y modificación de su fichero de configuración,
y arranque/parada delegados en un script externo acotado por sudoers
(privilegio mínimo, ver Metodología -- Sección "Seguridad: privilegio
mínimo y autenticación configurable").

Este backend NUNCA ejecuta el gNB directamente ni corre como root: se
limita a editar el YAML y a invocar gnb_ctl.sh, que es quien de verdad
tiene (mediante una regla sudoers acotada a este único script) permiso
para arrancar/parar el proceso del gNB.

Nota sobre portabilidad a otro tipo de tarjeta SDR: este backend controla
un ÚNICO binario del gNB, el que apunte GNB_BIN en deployment.conf (ver
Metodología, Portabilidad). No selecciona ni cambia de tarjeta por sí
mismo -- si se quisiera gestionar otro SDR (p. ej. volver a la bladeRF),
habría que apuntar GNB_BIN a ese otro build manualmente.
"""
import asyncio
import logging
import re
import subprocess

import yaml

from app.config import settings
from app.models.management import GnbConfig, GnbPreset

logger = logging.getLogger("dashboard.gnb_control")

# Combinaciones de banda/ARFCN/ancho de banda/SCS/srate REALMENTE
# verificadas en este trabajo (ver Implementación y Desarrollo) -- no una
# lista exhaustiva de todo lo teóricamente válido según 3GPP, que excede
# el alcance de este proyecto, sino las que se han usado y confirmado
# funcionando de verdad con la USRP B210.
KNOWN_GOOD_PRESETS: list[GnbPreset] = [
    GnbPreset(
        id="n78_20mhz",
        label="Banda n78 · 20 MHz",
        band=78,
        dl_arfcn=632628,
        channel_bandwidth_mhz=20,
        common_scs=30,
        srate=23.04,
        note="Configuración con la que se logró la primera conexión N2 estable con la B210.",
    ),
    GnbPreset(
        id="n78_10mhz",
        label="Banda n78 · 10 MHz",
        band=78,
        dl_arfcn=632628,
        channel_bandwidth_mhz=10,
        common_scs=30,
        srate=15.36,
        note="Empleada durante la investigación de timeouts de transmisión; también verificada.",
    ),
]


def get_presets() -> list[GnbPreset]:
    return KNOWN_GOOD_PRESETS

# Patrón de la línea que UHD imprime al detectar una USRP B2xx real (ver
# Implementación y Desarrollo, "Prueba de control con una USRP B210").
# Específico del controlador UHD empleado actualmente por el binario
# gestionado por este backend -- no genérico a cualquier SDR.
_DETECTED_DEVICE_RE = re.compile(r"Detected Device:\s*(\S+)")


def read_config() -> GnbConfig:
    with open(settings.gnb_config_path) as f:
        raw = yaml.safe_load(f)

    ru_sdr = raw["ru_sdr"]
    cell_cfg = raw["cell_cfg"]
    return GnbConfig(
        band=cell_cfg["band"],
        dl_arfcn=cell_cfg["dl_arfcn"],
        channel_bandwidth_mhz=cell_cfg["channel_bandwidth_MHz"],
        common_scs=cell_cfg["common_scs"],
        srate=ru_sdr["srate"],
        tx_gain=ru_sdr["tx_gain"],
        rx_gain=ru_sdr["rx_gain"],
    )


def write_config(new_config: GnbConfig) -> None:
    """Actualiza únicamente los campos gestionados, preservando el resto
    del fichero (PLMN, AMF, logging, pcap...) tal como estén.

    Incluye 'srate', a diferencia de la primera versión de este mecanismo
    -- su ausencia permitía generar, desde el propio panel, una
    combinación banda/ancho de banda/srate inválida (ver Implementación y
    Desarrollo, incidencia real sufrida con el formato PRACH)."""
    with open(settings.gnb_config_path) as f:
        raw = yaml.safe_load(f)

    raw["cell_cfg"]["band"] = new_config.band
    raw["cell_cfg"]["dl_arfcn"] = new_config.dl_arfcn
    raw["cell_cfg"]["channel_bandwidth_MHz"] = new_config.channel_bandwidth_mhz
    raw["cell_cfg"]["common_scs"] = new_config.common_scs
    raw["ru_sdr"]["srate"] = new_config.srate
    raw["ru_sdr"]["tx_gain"] = new_config.tx_gain
    raw["ru_sdr"]["rx_gain"] = new_config.rx_gain

    with open(settings.gnb_config_path, "w") as f:
        yaml.safe_dump(raw, f, default_flow_style=False, sort_keys=False)


def _run_ctl_script_sync(*args: str) -> tuple[bool, str]:
    """Bloqueante -- se invoca siempre a través de asyncio.to_thread desde
    las funciones públicas de este módulo, nunca directamente (ver
    Implementación y Desarrollo, incidencia real de bloqueo del servidor
    con el mismo problema en docker_control.py)."""
    try:
        result = subprocess.run(
            ["sudo", "-n", settings.gnb_ctl_script, *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
        success = result.returncode == 0
        output = result.stdout if success else (result.stderr or result.stdout)
        return success, output.strip()
    except subprocess.TimeoutExpired:
        return False, "El script de control del gNB no respondió a tiempo"
    except FileNotFoundError:
        return False, f"No se encuentra el script {settings.gnb_ctl_script}"


async def _run_ctl_script(*args: str) -> tuple[bool, str]:
    return await asyncio.to_thread(_run_ctl_script_sync, *args)


async def start() -> tuple[bool, str]:
    """Arranca el gNB con la configuración actual del disco, sin
    modificarla -- a diferencia de restart(), que primero escribe los
    cambios pendientes. Si ya estaba en marcha, gnb_ctl.sh lo informa sin
    error (ver su propia lógica interna)."""
    return await _run_ctl_script("start", settings.gnb_config_path)


async def restart() -> tuple[bool, str]:
    return await _run_ctl_script("restart", settings.gnb_config_path)


async def stop() -> tuple[bool, str]:
    return await _run_ctl_script("stop")


async def is_running() -> bool:
    success, detail = await _run_ctl_script("status")
    return success and "activo" in detail.lower()


def detected_hardware() -> str | None:
    """
    Nombre del dispositivo SDR realmente detectado en el último arranque,
    leído del propio log de arranque del gNB (no del YAML de
    configuración) -- confirma lo que UHD detectó de verdad, no solo lo
    que está configurado, que podrían no coincidir si algo fallara.

    Devuelve None si el gNB no ha arrancado nunca en esta máquina, si el
    log no existe, o si no se encuentra la línea (p. ej. con otro
    controlador SDR que no sea el UHD B2xx, ver nota de portabilidad al
    inicio del módulo).
    """
    try:
        with open(settings.gnb_ctl_log_path) as f:
            content = f.read()
    except FileNotFoundError:
        return None

    matches = _DETECTED_DEVICE_RE.findall(content)
    return matches[-1] if matches else None  # el más reciente, si arrancó varias veces


def get_logs(tail: int = 100, mode: str = "tail", search: str | None = None) -> tuple[bool, str]:
    """
    Líneas del log REAL y detallado del gNB (settings.gnb_log_path, debe
    coincidir con 'log.filename' del propio YAML), no del log de arranque
    de gnb_ctl.sh -- ver incidencia real de este trabajo en la que el
    segundo no reflejaba el nivel de detalle configurado (Implementación
    y Desarrollo, "Confirmación final...").

    `mode="tail"` (por defecto) devuelve las últimas `tail` líneas;
    `mode="head"` devuelve las primeras -- útil para ver la información de
    arranque (detección de la UHD, carga de la FPGA...) cuando el gNB
    lleva ya un rato corriendo y esa información ha quedado fuera de las
    últimas líneas.

    Si se indica `search`, se ignoran `tail`/`mode` y se devuelven TODAS
    las líneas de TODO el fichero que contengan ese texto (sin distinguir
    mayúsculas/minúsculas) -- para encontrar información sin depender de
    en qué punto del fichero esté, sin tener que cargar ni mostrar el
    fichero entero de golpe.

    Es un fichero de texto plano, legible sin privilegios especiales --
    se lee directamente aquí, sin pasar por ningún script con sudo.
    """
    if search is None:
        if not 1 <= tail <= 1000:
            return False, "El número de líneas debe estar entre 1 y 1000"
        if mode not in ("head", "tail"):
            return False, "El modo debe ser 'head' o 'tail'"

    try:
        with open(settings.gnb_log_path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False, (
            f"No existe {settings.gnb_log_path} todavía -- el gNB no ha "
            "arrancado nunca en esta máquina, o su log.filename apunta a otra ruta."
        )
    except PermissionError:
        return False, f"Sin permiso de lectura sobre {settings.gnb_log_path}"

    if search:
        needle = search.lower()
        matches = [line for line in lines if needle in line.lower()]
        header = f"# {len(matches)} línea(s) de {len(lines)} coinciden con '{search}'\n\n"
        return True, header + "".join(matches)

    selected = lines[:tail] if mode == "head" else lines[-tail:]
    return True, "".join(selected)

