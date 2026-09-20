"""
Arranque/parada individual de las funciones de red del core.

Delegado en un script externo (scripts/docker_ctl.sh) acotado por una regla
sudoers específica (ver Metodología del TFG, Sección "Seguridad: privilegio
mínimo y autenticación configurable"), en lugar de invocar 'docker compose'
directamente o añadir al usuario del backend al grupo 'docker' -- ambas
alternativas otorgarían, en la práctica, privilegios equivalentes a root
sobre todo el sistema, no solo sobre estas diez funciones de red concretas.

Corrección importante (ver Implementación y Desarrollo, incidencia real de
este trabajo): las funciones públicas de este módulo son `async`, y
delegan la llamada bloqueante a `subprocess.run` en un hilo aparte
(`asyncio.to_thread`), en vez de ejecutarla directamente dentro de una
función `async`. Sin esto, mientras un comando tarda en completarse
(`docker compose down` de las 10 NFs puede tardar más de lo que parece),
el servidor entero queda bloqueado y no puede atender ninguna otra
petición -- incluida la propia respuesta al navegador, que puede llegar a
parecer "fallida" pese a que el comando sí se ejecutara correctamente.
"""
import asyncio
import logging
import subprocess

from app.config import settings

logger = logging.getLogger("dashboard.docker_control")


def _run_ctl_script_sync(*args: str, timeout: int = 30) -> tuple[bool, str]:
    """Bloqueante -- se invoca siempre a través de asyncio.to_thread desde
    las funciones públicas de este módulo, nunca directamente."""
    try:
        result = subprocess.run(
            ["sudo", "-n", settings.docker_ctl_script, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        success = result.returncode == 0
        output = result.stdout if success else (result.stderr or result.stdout)
        return success, output.strip()
    except subprocess.TimeoutExpired:
        logger.warning(
            "docker_ctl.sh %s no respondió en %ss -- puede que el comando siga "
            "completándose en segundo plano pese a este aviso (ver Implementación "
            "y Desarrollo)",
            args,
            timeout,
        )
        return False, "El script de control del core no respondió a tiempo"
    except FileNotFoundError:
        return False, f"No se encuentra el script {settings.docker_ctl_script}"


async def _run_ctl_script(*args: str, timeout: int = 30) -> tuple[bool, str]:
    return await asyncio.to_thread(_run_ctl_script_sync, *args, timeout=timeout)


async def start_service(nf_name: str) -> tuple[bool, str]:
    if nf_name not in settings.core_services:
        return False, f"'{nf_name}' no es una función de red gestionada por este panel"
    return await _run_ctl_script("start", nf_name)


async def stop_service(nf_name: str) -> tuple[bool, str]:
    if nf_name not in settings.core_services:
        return False, f"'{nf_name}' no es una función de red gestionada por este panel"
    return await _run_ctl_script("stop", nf_name)


async def restart_service(nf_name: str) -> tuple[bool, str]:
    if nf_name not in settings.core_services:
        return False, f"'{nf_name}' no es una función de red gestionada por este panel"
    return await _run_ctl_script("restart", nf_name)


async def get_logs(nf_name: str, tail: int = 100) -> tuple[bool, str]:
    """Últimas `tail` líneas del contenedor, vía 'docker compose logs'."""
    if nf_name not in settings.core_services:
        return False, f"'{nf_name}' no es una función de red gestionada por este panel"
    if not 1 <= tail <= 1000:
        return False, "El número de líneas debe estar entre 1 y 1000"
    return await _run_ctl_script("logs", nf_name, str(tail))


async def get_full_logs(nf_name: str) -> tuple[bool, str]:
    """
    Log COMPLETO del contenedor, sin límite de líneas -- pensado para
    descarga, no para mostrar directamente en pantalla (puede ser grande
    en contenedores de larga duración, con el mismo riesgo de sobrecargar
    el navegador que motivó limitar get_logs() a 1000 líneas).
    """
    if nf_name not in settings.core_services:
        return False, f"'{nf_name}' no es una función de red gestionada por este panel"
    return await _run_ctl_script("logs-full", nf_name)


async def search_logs(nf_name: str, search: str) -> tuple[bool, str]:
    """
    Busca `search` (cadena literal, sin distinguir mayúsculas/minúsculas)
    en TODO el log del contenedor, devolviendo solo las líneas que
    coinciden -- para encontrar información sin depender de en qué punto
    del log esté, sin cargar el log entero en el navegador.
    """
    if nf_name not in settings.core_services:
        return False, f"'{nf_name}' no es una función de red gestionada por este panel"
    if not search or len(search) > 200:
        return False, "El término de búsqueda debe tener entre 1 y 200 caracteres"
    success, output = await _run_ctl_script("logs-search", nf_name, search)
    if not success and not output:
        # 'grep' sin coincidencias sale con código de error y sin salida --
        # no es un fallo del propio comando, solo "no se encontró nada".
        return True, f"# 0 líneas coinciden con '{search}'\n"
    if success:
        count = len(output.splitlines())
        header = f"# {count} línea(s) coinciden con '{search}'\n\n"
        return True, header + output
    return success, output


async def get_nat_stats() -> tuple[bool, str]:
    """
    Salida en bruto de 'iptables -t nat -L POSTROUTING -n -v -x' dentro del
    contenedor del UPF -- fuente real de tráfico de subida del UE, empleada
    en lugar de las métricas GTP nativas de Open5GS
    (fivegs_ep_n3_gtp_in/outdatapktn3upf), deliberadamente deshabilitadas
    por el propio proyecto por motivos de rendimiento del plano de datos
    (ver Implementación y Desarrollo). El parseo de la línea concreta
    (regla MASQUERADE sobre 10.45.0.0/16) se hace en el llamador.
    """
    return await _run_ctl_script("nat-stats")


async def get_upf_nat_counters() -> tuple[int, int] | None:
    """
    Extrae (paquetes, bytes) acumulados de la regla MASQUERADE que
    enmascara el tráfico saliente de la subred de UEs (10.45.0.0/16) hacia
    la red de datos -- contador real y verificado en este trabajo, a
    diferencia de las métricas nativas de Open5GS para N3 (ver
    get_nat_stats). Devuelve None si el UPF no respondió o si la línea
    esperada no aparece en la salida.
    """
    success, output = await get_nat_stats()
    if not success:
        logger.warning("No se pudo consultar el contador NAT del UPF: %s", output)
        return None

    for line in output.splitlines():
        if "MASQUERADE" in line:
            fields = line.split()
            # Formato de 'iptables -L -v -x': pkts bytes target prot ...
            try:
                pkts, byte_count = int(fields[0]), int(fields[1])
                return pkts, byte_count
            except (IndexError, ValueError):
                logger.warning("Línea MASQUERADE con formato inesperado: %r", line)
                return None

    logger.warning("No se encontró ninguna línea MASQUERADE en la salida de nat-stats")
    return None


async def core_up() -> tuple[bool, str]:
    """Levanta las 10 NFs de una vez ('docker compose up -d' completo),
    en vez de tener que arrancarlas una por una desde el panel. Límite de
    tiempo más generoso que las acciones sobre una sola NF (ver
    _run_ctl_script_sync): 10 contenedores, con la red personalizada de
    por medio, pueden tardar más de 30s en un core que lleve tiempo
    corriendo con conexiones reales establecidas."""
    return await _run_ctl_script("core-up", timeout=60)


async def core_down() -> tuple[bool, str]:
    """Detiene y elimina los 10 contenedores del core ('docker compose
    down' completo). Mismo motivo de timeout ampliado que core_up()."""
    return await _run_ctl_script("core-down", timeout=60)
