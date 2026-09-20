"""
Pruebas de persistencia de configuraciones personalizadas del gNB. Se usa
un fichero JSON temporal (tmp_path de pytest) en cada prueba, para no
depender de ni afectar a ningún fichero real del sistema.
"""
import pytest

from app.models.management import GnbConfig
from app.services import gnb_custom_presets

SAMPLE_CONFIG = GnbConfig(
    band=78, dl_arfcn=632628, channel_bandwidth_mhz=20, common_scs=30,
    srate=23.04, tx_gain=60, rx_gain=40,
)


@pytest.fixture
def presets_file(tmp_path, monkeypatch):
    path = tmp_path / "gnb_custom_presets.json"
    monkeypatch.setattr(gnb_custom_presets.settings, "gnb_custom_presets_path", str(path))
    return path


def test_list_custom_presets_empty_if_file_does_not_exist(presets_file):
    assert gnb_custom_presets.list_custom_presets() == []


def test_save_and_list_custom_preset(presets_file):
    gnb_custom_presets.save_custom_preset("Mi configuración", SAMPLE_CONFIG)

    presets = gnb_custom_presets.list_custom_presets()
    assert len(presets) == 1
    assert presets[0].name == "Mi configuración"
    assert presets[0].config.band == 78
    assert presets[0].config.tx_gain == 60


def test_save_creates_parent_directory_if_missing(tmp_path, monkeypatch):
    # Ruta con una subcarpeta que todavía no existe -- debe crearla sola.
    path = tmp_path / "no_existe_todavia" / "presets.json"
    monkeypatch.setattr(gnb_custom_presets.settings, "gnb_custom_presets_path", str(path))

    gnb_custom_presets.save_custom_preset("test", SAMPLE_CONFIG)

    assert path.exists()


def test_save_with_same_name_replaces_the_previous_one(presets_file):
    gnb_custom_presets.save_custom_preset("A", SAMPLE_CONFIG)
    updated_config = SAMPLE_CONFIG.model_copy(update={"tx_gain": 80})
    gnb_custom_presets.save_custom_preset("A", updated_config)

    presets = gnb_custom_presets.list_custom_presets()
    assert len(presets) == 1  # no se duplicó
    assert presets[0].config.tx_gain == 80  # se sustituyó por el nuevo valor


def test_delete_custom_preset(presets_file):
    gnb_custom_presets.save_custom_preset("A", SAMPLE_CONFIG)

    assert gnb_custom_presets.delete_custom_preset("A") is True
    assert gnb_custom_presets.list_custom_presets() == []


def test_delete_nonexistent_preset_returns_false(presets_file):
    assert gnb_custom_presets.delete_custom_preset("no existe") is False


def test_list_returns_empty_and_logs_warning_if_file_corrupted(presets_file):
    presets_file.write_text("esto no es JSON válido {{{")
    assert gnb_custom_presets.list_custom_presets() == []


@pytest.fixture
def pointer_file(tmp_path, monkeypatch):
    path = tmp_path / ".presets_path_override"
    monkeypatch.setattr(gnb_custom_presets.settings, "gnb_custom_presets_pointer_path", str(path))
    return path


def test_get_effective_path_returns_default_if_never_changed(presets_file, pointer_file):
    assert gnb_custom_presets.get_effective_path() == str(presets_file)


def test_set_path_rejects_relative_path(presets_file, pointer_file):
    success, detail = gnb_custom_presets.set_path("ruta/relativa.json")
    assert success is False
    assert "absoluta" in detail


def test_set_path_rejects_empty_path(presets_file, pointer_file):
    success, detail = gnb_custom_presets.set_path("   ")
    assert success is False


def test_set_path_changes_effective_path_and_persists(presets_file, pointer_file, tmp_path):
    new_path = tmp_path / "otra_carpeta" / "mis_presets.json"

    success, detail = gnb_custom_presets.set_path(str(new_path))

    assert success is True
    assert str(new_path) in detail
    assert gnb_custom_presets.get_effective_path() == str(new_path)


def test_set_path_migrates_existing_presets_to_new_location(presets_file, pointer_file, tmp_path):
    gnb_custom_presets.save_custom_preset("Preset original", SAMPLE_CONFIG)

    new_path = tmp_path / "nueva_ubicacion.json"
    success, detail = gnb_custom_presets.set_path(str(new_path))

    assert success is True
    assert "se copiaron" in detail
    # A partir de ahora, list_custom_presets() lee de la ruta NUEVA, y el
    # preset ya guardado debe seguir estando ahí.
    presets = gnb_custom_presets.list_custom_presets()
    assert len(presets) == 1
    assert presets[0].name == "Preset original"


def test_set_path_rejects_unwritable_location(presets_file, pointer_file):
    # Una ruta absoluta cuyo directorio padre no se puede crear ni escribir
    # (dentro de una carpeta del sistema sin permiso, simulado con /proc).
    success, detail = gnb_custom_presets.set_path("/proc/no_deberia_poder_escribir/x.json")
    assert success is False
    assert "no se puede escribir" in detail.lower()


def test_set_path_with_folder_ending_in_slash_uses_default_filename(tmp_path, pointer_file):
    """Caso real reportado: el usuario escribe una carpeta con barra final
    (p. ej. '/home/<usuario>/Desktop/Test Presets/', con espacio en el nombre),
    esperando que se use un fichero DENTRO de esa carpeta, no que el
    último segmento se interprete como el propio nombre del fichero."""
    folder = tmp_path / "Test Presets"
    success, detail = gnb_custom_presets.set_path(f"{folder}/")

    assert success is True
    expected_file = folder / "gnb_custom_presets.json"
    assert gnb_custom_presets.get_effective_path() == str(expected_file)
    assert "se guardará dentro" in detail


def test_set_path_with_existing_folder_without_trailing_slash_also_detected(tmp_path, pointer_file):
    """Si la carpeta ya existe de antes, se detecta como carpeta aunque el
    usuario no haya puesto la barra final."""
    folder = tmp_path / "ya_existe"
    folder.mkdir()

    success, detail = gnb_custom_presets.set_path(str(folder))

    assert success is True
    expected_file = folder / "gnb_custom_presets.json"
    assert gnb_custom_presets.get_effective_path() == str(expected_file)
