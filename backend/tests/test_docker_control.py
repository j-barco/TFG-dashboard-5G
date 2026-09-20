import pytest
from unittest.mock import MagicMock, patch

from app.services import docker_control


@pytest.mark.asyncio
async def test_start_service_rejects_unknown_nf():
    success, detail = await docker_control.start_service("no-existe")
    assert success is False
    assert "no es una función de red" in detail


@pytest.mark.asyncio
async def test_start_service_calls_ctl_script_with_sudo():
    mock_result = MagicMock(returncode=0, stdout="Container amf Started\n", stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        success, detail = await docker_control.start_service("amf")

    assert success is True
    called_args = mock_run.call_args[0][0]
    assert called_args[0:2] == ["sudo", "-n"]  # nunca sudo interactivo
    assert called_args[-2:] == ["start", "amf"]


@pytest.mark.asyncio
async def test_stop_service_calls_ctl_script_with_sudo():
    mock_result = MagicMock(returncode=0, stdout="Container amf Stopped\n", stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        success, detail = await docker_control.stop_service("amf")

    assert success is True
    called_args = mock_run.call_args[0][0]
    assert called_args[-2:] == ["stop", "amf"]


@pytest.mark.asyncio
async def test_service_action_reports_failure():
    mock_result = MagicMock(returncode=1, stdout="", stderr="ERROR: permission denied\n")
    with patch("subprocess.run", return_value=mock_result):
        success, detail = await docker_control.start_service("amf")

    assert success is False
    assert "permission denied" in detail


@pytest.mark.asyncio
async def test_restart_service_rejects_unknown_nf():
    success, detail = await docker_control.restart_service("no-existe")
    assert success is False
    assert "no es una función de red" in detail


@pytest.mark.asyncio
async def test_restart_service_calls_ctl_script_with_restart_action():
    mock_result = MagicMock(returncode=0, stdout="Container amf Restarted\n", stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        success, detail = await docker_control.restart_service("amf")

    assert success is True
    called_args = mock_run.call_args[0][0]
    assert called_args[0:2] == ["sudo", "-n"]
    assert called_args[-2:] == ["restart", "amf"]


# Fragmento realista de "docker compose logs", con el mismo formato que
# los reales capturados durante el desarrollo de este trabajo (ver
# Implementación y Desarrollo).
SAMPLE_DOCKER_LOGS = (
    "amf  | 08/19 22:13:05.229: [app] INFO: Configuration: "
    "'/etc/open5gs/custom/amf.yaml' (../lib/app/ogs-init.c:144)\n"
    "amf  | 08/19 22:13:05.230: [amf] INFO: gNB-N2 accepted[10.33.33.1] "
    "in master_sm module (../src/amf/amf-sm.c:953)\n"
)


@pytest.mark.asyncio
async def test_get_logs_rejects_unknown_nf():
    success, output = await docker_control.get_logs("no-existe")
    assert success is False
    assert "no es una función de red" in output


@pytest.mark.asyncio
async def test_get_logs_rejects_out_of_range_tail():
    success, output = await docker_control.get_logs("amf", tail=0)
    assert success is False
    success, output = await docker_control.get_logs("amf", tail=1001)
    assert success is False


@pytest.mark.asyncio
async def test_get_logs_calls_ctl_script_with_logs_action_and_tail():
    mock_result = MagicMock(returncode=0, stdout=SAMPLE_DOCKER_LOGS, stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        success, output = await docker_control.get_logs("amf", tail=50)

    assert success is True
    assert "gNB-N2 accepted" in output
    called_args = mock_run.call_args[0][0]
    assert called_args[0:2] == ["sudo", "-n"]
    assert called_args[-3:] == ["logs", "amf", "50"]


@pytest.mark.asyncio
async def test_get_logs_uses_default_tail_of_100():
    mock_result = MagicMock(returncode=0, stdout=SAMPLE_DOCKER_LOGS, stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        await docker_control.get_logs("amf")

    called_args = mock_run.call_args[0][0]
    assert called_args[-1] == "100"


@pytest.mark.asyncio
async def test_get_nat_stats_calls_ctl_script_with_nat_stats_action():
    sample_output = (
        "Chain POSTROUTING (policy ACCEPT 15 packets, 1055 bytes)\n"
        "    pkts      bytes target     prot opt in     out     source               destination\n"
        "      56      19650 MASQUERADE  all  --  *      !ogstun  10.45.0.0/16         0.0.0.0/0\n"
    )
    mock_result = MagicMock(returncode=0, stdout=sample_output, stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        success, output = await docker_control.get_nat_stats()

    assert success is True
    assert "MASQUERADE" in output
    called_args = mock_run.call_args[0][0]
    assert called_args == ["sudo", "-n", docker_control.settings.docker_ctl_script, "nat-stats"]


@pytest.mark.asyncio
async def test_core_up_calls_ctl_script_with_core_up_action():
    mock_result = MagicMock(
        returncode=0, stdout="[+] Running 10/10\n Container amf Started\n", stderr=""
    )
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        success, detail = await docker_control.core_up()

    assert success is True
    assert "Running 10/10" in detail
    called_args = mock_run.call_args[0][0]
    assert called_args == ["sudo", "-n", docker_control.settings.docker_ctl_script, "core-up"]


@pytest.mark.asyncio
async def test_core_down_calls_ctl_script_with_core_down_action():
    mock_result = MagicMock(returncode=0, stdout="Container amf Removed\n", stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        success, detail = await docker_control.core_down()

    assert success is True
    called_args = mock_run.call_args[0][0]
    assert called_args == ["sudo", "-n", docker_control.settings.docker_ctl_script, "core-down"]


@pytest.mark.asyncio
async def test_core_up_reports_failure():
    mock_result = MagicMock(returncode=1, stdout="", stderr="ERROR: port already in use\n")
    with patch("subprocess.run", return_value=mock_result):
        success, detail = await docker_control.core_up()

    assert success is False
    assert "port already in use" in detail


@pytest.mark.asyncio
async def test_get_full_logs_rejects_unknown_nf():
    success, output = await docker_control.get_full_logs("no-existe")
    assert success is False
    assert "no es una función de red" in output


@pytest.mark.asyncio
async def test_get_full_logs_calls_ctl_script_with_logs_full_action():
    mock_result = MagicMock(returncode=0, stdout=SAMPLE_DOCKER_LOGS * 50, stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        success, output = await docker_control.get_full_logs("amf")

    assert success is True
    called_args = mock_run.call_args[0][0]
    assert called_args == ["sudo", "-n", docker_control.settings.docker_ctl_script, "logs-full", "amf"]


@pytest.mark.asyncio
async def test_search_logs_rejects_unknown_nf():
    success, output = await docker_control.search_logs("no-existe", "algo")
    assert success is False
    assert "no es una función de red" in output


@pytest.mark.asyncio
async def test_search_logs_rejects_empty_or_too_long_term():
    success, _ = await docker_control.search_logs("amf", "")
    assert success is False
    success, _ = await docker_control.search_logs("amf", "x" * 201)
    assert success is False


@pytest.mark.asyncio
async def test_search_logs_calls_ctl_script_with_search_term_as_separate_argument():
    mock_result = MagicMock(returncode=0, stdout="amf | gNB-N2 accepted[10.33.33.1]\n", stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        success, output = await docker_control.search_logs("amf", "gNB-N2")

    assert success is True
    assert "1 línea" in output
    assert "gNB-N2 accepted" in output
    called_args = mock_run.call_args[0][0]
    # El término va como argumento SEPARADO, nunca concatenado en una cadena
    # de shell -- comprobación básica de que no hay "inyección" posible
    # desde este lado (la protección real vive en docker_ctl.sh, ver
    # verificación manual documentada en Implementación y Desarrollo).
    assert called_args == [
        "sudo", "-n", docker_control.settings.docker_ctl_script, "logs-search", "amf", "gNB-N2",
    ]


@pytest.mark.asyncio
async def test_search_logs_reports_zero_matches_gracefully():
    """'grep' sin coincidencias sale con código de error y sin salida --
    no debe interpretarse como un fallo del propio comando."""
    mock_result = MagicMock(returncode=1, stdout="", stderr="")
    with patch("subprocess.run", return_value=mock_result):
        success, output = await docker_control.search_logs("amf", "esto no aparece en ningún sitio")

    assert success is True
    assert "0 líneas" in output
