"""
Pruebas del servicio de control del gNB. La lectura/escritura del YAML se
prueba contra un fichero temporal con la misma estructura real que emplea
el proyecto (ver gnb_bladerf_n78_20mhz.yml / gnb_b200_n78_20mhz.yml en el
Capítulo de Implementación y Desarrollo); el arranque/parada real (que
requiere sudo y el propio gNB) se prueba simulando subprocess.run, ya que
no puede ejecutarse dentro de la batería de pruebas.
"""
from unittest.mock import MagicMock, patch

import pytest
import pytest

from app.models.management import GnbConfig
from app.services import gnb_control

SAMPLE_YAML = """\
cu_cp:
  amf:
    addr: 192.168.0.17
    port: 38412
    bind_addr: 127.0.0.1
    supported_tracking_areas:
      - tac: 7
        plmn_list:
          - plmn: "90170"
            tai_slice_support_list:
              - sst: 1

ru_sdr:
  device_driver: uhd
  device_args: type=b200,num_recv_frames=64,num_send_frames=64
  srate: 23.04
  otw_format: sc12
  tx_gain: 80
  rx_gain: 40

cell_cfg:
  dl_arfcn: 632628
  band: 78
  channel_bandwidth_MHz: 20
  common_scs: 30
  plmn: "90170"
  tac: 7
  pci: 1

log:
  filename: /tmp/gnb.log
  all_level: warning
"""


@pytest.fixture
def gnb_yaml_file(tmp_path, monkeypatch):
    yaml_path = tmp_path / "gnb_test.yml"
    yaml_path.write_text(SAMPLE_YAML)
    monkeypatch.setattr(gnb_control.settings, "gnb_config_path", str(yaml_path))
    return yaml_path


def test_read_config(gnb_yaml_file):
    config = gnb_control.read_config()
    assert config.band == 78
    assert config.dl_arfcn == 632628
    assert config.channel_bandwidth_mhz == 20
    assert config.common_scs == 30
    assert config.srate == 23.04
    assert config.tx_gain == 80
    assert config.rx_gain == 40


def test_write_config_preserves_other_fields(gnb_yaml_file):
    new_config = GnbConfig(
        band=78,
        dl_arfcn=632628,
        channel_bandwidth_mhz=10,
        common_scs=30,
        srate=15.36,
        tx_gain=60,  # antes -20, ya no válido: la B210 nunca acepta ganancia negativa
        rx_gain=40,
    )
    gnb_control.write_config(new_config)

    # Releer con la propia función, para comprobar que el cambio se aplicó...
    reread = gnb_control.read_config()
    assert reread.channel_bandwidth_mhz == 10
    assert reread.srate == 15.36
    assert reread.tx_gain == 60

    # ...y comprobar, parseando de nuevo el YAML (no comparando texto literal,
    # ya que PyYAML puede cambiar el estilo de comillas al volcar el fichero
    # sin que eso altere su significado), que el resto de campos que NO
    # gestiona este servicio (PLMN, dirección del AMF, logging) siguen ahí.
    import yaml as _yaml

    with open(gnb_yaml_file) as f:
        raw = _yaml.safe_load(f)

    assert raw["cell_cfg"]["plmn"] == "90170"
    assert raw["cu_cp"]["amf"]["addr"] == "192.168.0.17"
    assert raw["log"]["filename"] == "/tmp/gnb.log"


def test_gnb_config_rejects_negative_tx_gain():
    """La B210 nunca acepta ganancia negativa (a diferencia de la
    bladeRF) -- ver límites reales documentados por Ettus."""
    with pytest.raises(Exception):  # ValidationError de Pydantic
        GnbConfig(
            band=78, dl_arfcn=632628, channel_bandwidth_mhz=20,
            common_scs=30, srate=23.04, tx_gain=-1, rx_gain=40,
        )


def test_gnb_config_rejects_tx_gain_above_hardware_limit():
    with pytest.raises(Exception):
        GnbConfig(
            band=78, dl_arfcn=632628, channel_bandwidth_mhz=20,
            common_scs=30, srate=23.04, tx_gain=90, rx_gain=40,  # límite real: 89.8
        )


def test_get_presets_returns_known_validated_combinations():
    presets = gnb_control.get_presets()
    assert len(presets) >= 2
    ids = {p.id for p in presets}
    assert "n78_20mhz" in ids
    assert "n78_10mhz" in ids
    # Cada preset debe ser, en sí mismo, una configuración válida según
    # los mismos límites que exige GnbConfig.
    for preset in presets:
        GnbConfig(
            band=preset.band,
            dl_arfcn=preset.dl_arfcn,
            channel_bandwidth_mhz=preset.channel_bandwidth_mhz,
            common_scs=preset.common_scs,
            srate=preset.srate,
            tx_gain=40,
            rx_gain=40,
        )


@pytest.mark.asyncio
async def test_restart_calls_ctl_script_with_sudo():
    mock_result = MagicMock(returncode=0, stdout="gNB arrancado correctamente (PID 1234)\n", stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        success, detail = await gnb_control.restart()

    assert success is True
    assert "arrancado" in detail
    called_args = mock_run.call_args[0][0]
    assert called_args[0:2] == ["sudo", "-n"]  # nunca sudo interactivo


@pytest.mark.asyncio
async def test_restart_reports_failure_from_script():
    mock_result = MagicMock(returncode=1, stdout="", stderr="ERROR: configuración inválida\n")
    with patch("subprocess.run", return_value=mock_result):
        success, detail = await gnb_control.restart()

    assert success is False
    assert "inválida" in detail


@pytest.mark.asyncio
async def test_start_calls_ctl_script_with_start_action():
    mock_result = MagicMock(returncode=0, stdout="gNB arrancado correctamente (PID 1234)\n", stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        success, detail = await gnb_control.start()

    assert success is True
    called_args = mock_run.call_args[0][0]
    assert called_args[0:2] == ["sudo", "-n"]
    assert called_args[-2] == "start"  # no "restart"


@pytest.mark.asyncio
async def test_is_running_true_when_script_reports_active():
    mock_result = MagicMock(returncode=0, stdout="activo (PID 1234)\n", stderr="")
    with patch("subprocess.run", return_value=mock_result):
        assert await gnb_control.is_running() is True


@pytest.mark.asyncio
async def test_is_running_false_when_script_reports_stopped():
    mock_result = MagicMock(returncode=0, stdout="parado\n", stderr="")
    with patch("subprocess.run", return_value=mock_result):
        assert await gnb_control.is_running() is False


# Fragmento real capturado durante las pruebas de este trabajo (ver
# Implementación y Desarrollo, "Prueba de control con una USRP B210").
REAL_GNB_LOG_WITH_DETECTION = """\
[INFO] [UHD] linux; GNU C++ version 14.2.0; Boost_108300; UHD_4.6.0.HEAD-0-g50fa3baa
[INFO] [LOGGING] Fastpath logging disabled at runtime.
[DEBUG] [B200] the firmware image: /opt/uhd-4.6.0/share/uhd/images/usrp_b200_fw.hex
[INFO] [B200] Loading firmware image: /opt/uhd-4.6.0/share/uhd/images/usrp_b200_fw.hex...
[INFO] [B200] Detected Device: B210
[INFO] [B200] Loading FPGA image: /opt/uhd-4.6.0/share/uhd/images/usrp_b210_fpga.bin...
"""


def test_detected_hardware_parses_real_log_line(tmp_path, monkeypatch):
    log_file = tmp_path / "gnb_ctl.log"
    log_file.write_text(REAL_GNB_LOG_WITH_DETECTION)
    monkeypatch.setattr(gnb_control.settings, "gnb_ctl_log_path", str(log_file))

    assert gnb_control.detected_hardware() == "B210"


def test_detected_hardware_returns_none_if_log_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(gnb_control.settings, "gnb_ctl_log_path", str(tmp_path / "no_existe.log"))
    assert gnb_control.detected_hardware() is None


def test_detected_hardware_returns_none_if_pattern_absent(tmp_path, monkeypatch):
    log_file = tmp_path / "gnb_ctl.log"
    log_file.write_text("[INFO] Algo que no menciona ningún dispositivo\n")
    monkeypatch.setattr(gnb_control.settings, "gnb_ctl_log_path", str(log_file))

    assert gnb_control.detected_hardware() is None


def test_detected_hardware_returns_most_recent_if_started_multiple_times(tmp_path, monkeypatch):
    log_file = tmp_path / "gnb_ctl.log"
    log_file.write_text(
        "[INFO] [B200] Detected Device: B210\n"
        "...\n"
        "[INFO] [B200] Detected Device: B210\n"  # segundo arranque, mismo dispositivo
    )
    monkeypatch.setattr(gnb_control.settings, "gnb_ctl_log_path", str(log_file))

    assert gnb_control.detected_hardware() == "B210"


# Fragmento real de /tmp/gnb.log capturado durante la resolución de la
# incidencia de conexión del equipo de usuario (ver Implementación y
# Desarrollo, "Resolución de la incidencia de conexión del equipo de
# usuario") -- distinto de gnb_ctl.log, que no reflejaba este nivel de detalle.
REAL_GNB_DETAILED_LOG = """\
2026-08-27T10:19:09.846 [gmm] INFO: Registration request (../src/amf/gmm-sm.c:1670)
2026-08-27T10:19:10.040 [gmm] INFO: [imsi-001019876543218] Registration complete (../src/amf/gmm-sm.c:3146)
2026-08-27T10:19:10.042 [amf] INFO: UE Context Release [Action:1] (../src/amf/ngap-handler.c:1757)
"""


def test_get_gnb_logs_returns_real_detailed_log(tmp_path, monkeypatch):
    log_file = tmp_path / "gnb.log"
    log_file.write_text(REAL_GNB_DETAILED_LOG)
    monkeypatch.setattr(gnb_control.settings, "gnb_log_path", str(log_file))

    success, output = gnb_control.get_logs(tail=100)

    assert success is True
    assert "Registration complete" in output


def test_get_gnb_logs_respects_tail_limit(tmp_path, monkeypatch):
    log_file = tmp_path / "gnb.log"
    log_file.write_text("\n".join(f"línea {i}" for i in range(1, 21)))  # 20 líneas
    monkeypatch.setattr(gnb_control.settings, "gnb_log_path", str(log_file))

    success, output = gnb_control.get_logs(tail=5)

    assert success is True
    lines = output.strip().splitlines()
    assert len(lines) == 5
    assert lines[-1] == "línea 20"  # las últimas, no las primeras


def test_get_gnb_logs_rejects_out_of_range_tail(tmp_path, monkeypatch):
    log_file = tmp_path / "gnb.log"
    log_file.write_text("algo\n")
    monkeypatch.setattr(gnb_control.settings, "gnb_log_path", str(log_file))

    success, _ = gnb_control.get_logs(tail=0)
    assert success is False
    success, _ = gnb_control.get_logs(tail=1001)
    assert success is False


def test_get_gnb_logs_handles_missing_file_gracefully(tmp_path, monkeypatch):
    monkeypatch.setattr(gnb_control.settings, "gnb_log_path", str(tmp_path / "no_existe.log"))

    success, detail = gnb_control.get_logs()

    assert success is False
    assert "no ha arrancado nunca" in detail or "no existe" in detail.lower()


def test_get_gnb_logs_head_mode_returns_first_lines(tmp_path, monkeypatch):
    log_file = tmp_path / "gnb.log"
    log_file.write_text("\n".join(f"línea {i}" for i in range(1, 21)))  # 20 líneas
    monkeypatch.setattr(gnb_control.settings, "gnb_log_path", str(log_file))

    success, output = gnb_control.get_logs(tail=5, mode="head")

    assert success is True
    lines = output.strip().splitlines()
    assert len(lines) == 5
    assert lines[0] == "línea 1"  # las primeras, no las últimas


def test_get_gnb_logs_rejects_invalid_mode(tmp_path, monkeypatch):
    log_file = tmp_path / "gnb.log"
    log_file.write_text("algo\n")
    monkeypatch.setattr(gnb_control.settings, "gnb_log_path", str(log_file))

    success, detail = gnb_control.get_logs(tail=10, mode="lateral")

    assert success is False
    assert "head" in detail and "tail" in detail


def test_get_gnb_logs_search_finds_matches_anywhere_in_file(tmp_path, monkeypatch):
    log_file = tmp_path / "gnb.log"
    # La coincidencia está muy al principio de un fichero largo -- no
    # aparecería ni con mode='tail' ni, salvo casualidad, con 'head' si el
    # fichero fuera más largo que la ventana pedida.
    log_file.write_text(
        "línea con Registration complete aquí\n" + "\n".join(f"línea {i}" for i in range(2, 500))
    )
    monkeypatch.setattr(gnb_control.settings, "gnb_log_path", str(log_file))

    success, output = gnb_control.get_logs(tail=10, mode="tail", search="registration")

    assert success is True
    assert "Registration complete" in output
    assert "1 línea" in output  # resumen de coincidencias


def test_get_gnb_logs_search_case_insensitive_and_no_matches(tmp_path, monkeypatch):
    log_file = tmp_path / "gnb.log"
    log_file.write_text("nada relevante aquí\n")
    monkeypatch.setattr(gnb_control.settings, "gnb_log_path", str(log_file))

    success, output = gnb_control.get_logs(search="ERROR")

    assert success is True
    assert "0 línea" in output
