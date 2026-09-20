"""
Persistencia de configuraciones del gNB guardadas por el propio usuario
desde el panel, con un nombre elegido por él (a diferencia de los
'presets' fijos y verificados de gnb_control.KNOWN_GOOD_PRESETS).

Se usa un fichero JSON simple en disco, no MongoDB: son datos de
configuración del propio panel, no suscriptores de Open5GS -- mezclar
ambos en la misma base de datos no tendría sentido conceptual, y un
fichero JSON es más que suficiente para una lista de unas pocas
configuraciones guardadas.

La ruta de este fichero es configurable desde el propio panel (no solo
editando el .env): un navegador no puede abrir un diálogo nativo que
navegue por el sistema de ficheros del SERVIDOR (los navegadores lo
impiden deliberadamente, por seguridad -- cualquier página web podría
si no curiosear el disco de quien la visite), así que en su lugar se
permite ESCRIBIR la ruta exacta deseada, validando que sea escribible y
migrando lo ya guardado. La elección se recuerda entre reinicios
mediante un pequeño fichero "puntero" (settings.gnb_custom_presets_pointer_path),
en vez de reescribir el propio .env desde la aplicación.
"""
import json
import logging
from pathlib import Path

from app.config import settings
from app.models.management import GnbConfig, SavedGnbConfig

logger = logging.getLogger("dashboard.gnb_custom_presets")


def get_effective_path() -> str:
    """Ruta REAL donde se guardan los presets ahora mismo: la elegida por
    el usuario si ya cambió alguna vez la ruta (fichero puntero), o la de
    settings.gnb_custom_presets_path por defecto en caso contrario."""
    pointer = Path(settings.gnb_custom_presets_pointer_path)
    if pointer.exists():
        override = pointer.read_text().strip()
        if override:
            return override
    return settings.gnb_custom_presets_path


def set_path(new_path: str) -> tuple[bool, str]:
    """
    Cambia la ruta de almacenamiento a `new_path`, validando primero que
    se pueda escribir ahí de verdad, y migrando automáticamente lo que ya
    hubiera guardado en la ruta anterior (si la nueva todavía no existe).

    Si `new_path` es una CARPETA (termina en '/', o ya existe como
    directorio), se usa un nombre de fichero por defecto dentro de ella
    -- en vez de tratar el último segmento del texto como si fuera el
    propio nombre del fichero, que generaría un fichero mal nombrado sin
    que quien lo escribió se diera cuenta.
    """
    new_path = new_path.strip()
    if not new_path:
        return False, "La ruta no puede estar vacía"

    new_path_obj = Path(new_path)
    if not new_path_obj.is_absolute():
        return False, "La ruta debe ser absoluta (empezar por '/')"

    looked_like_a_folder = new_path.endswith("/") or new_path_obj.is_dir()
    if looked_like_a_folder:
        new_path_obj = new_path_obj / "gnb_custom_presets.json"

    try:
        new_path_obj.parent.mkdir(parents=True, exist_ok=True)
        probe = new_path_obj.parent / ".dashboard_write_test"
        probe.write_text("ok")
        probe.unlink()
    except OSError as exc:
        return False, f"No se puede escribir en esa ruta: {exc}"

    old_path = get_effective_path()
    if old_path != str(new_path_obj) and Path(old_path).exists() and not new_path_obj.exists():
        new_path_obj.write_text(Path(old_path).read_text())
        migrated_note = " (se copiaron las configuraciones ya guardadas)"
    else:
        migrated_note = ""

    pointer = Path(settings.gnb_custom_presets_pointer_path)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(str(new_path_obj))

    folder_note = " (se guardará dentro, como 'gnb_custom_presets.json')" if looked_like_a_folder else ""
    return True, f"A partir de ahora se guardará en {new_path_obj}{folder_note}{migrated_note}"


def _load_all() -> list[SavedGnbConfig]:
    path = Path(get_effective_path())
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
        return [SavedGnbConfig(**item) for item in raw]
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning(
            "No se pudo leer %s (fichero corrupto o con formato inesperado): %s", path, exc
        )
        return []


def _save_all(presets: list[SavedGnbConfig]) -> None:
    path = Path(get_effective_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([p.model_dump() for p in presets], indent=2, ensure_ascii=False))


def list_custom_presets() -> list[SavedGnbConfig]:
    return _load_all()


def save_custom_preset(name: str, config: GnbConfig) -> None:
    """Guarda (o sustituye, si ya existía uno con ese nombre exacto) una
    configuración personalizada."""
    presets = _load_all()
    presets = [p for p in presets if p.name != name]
    presets.append(SavedGnbConfig(name=name, config=config))
    _save_all(presets)


def delete_custom_preset(name: str) -> bool:
    """Devuelve True si se eliminó alguno, False si no existía ese nombre."""
    presets = _load_all()
    remaining = [p for p in presets if p.name != name]
    if len(remaining) == len(presets):
        return False
    _save_all(remaining)
    return True
