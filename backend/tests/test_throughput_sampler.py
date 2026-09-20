"""
Pruebas del muestreador de tráfico. El parseo se prueba contra la salida
real de 'iptables -t nat -L POSTROUTING -n -v -x' capturada durante las
pruebas de conexión real de un UE en este trabajo (ver Implementación y
Desarrollo, "Resolución de la incidencia de conexión del equipo de
usuario"); el cálculo de tasas es una función pura, probada de forma
aislada de cualquier E/S.
"""
from unittest.mock import patch

import pytest

from app.services import throughput_sampler
from app.services.throughput_sampler import compute_rate, parse_nat_masquerade_counters

# Capturas reales, en dos instantes distintos, durante una prueba de
# navegación real desde el UE (ver memoria del TFG).
REAL_IPTABLES_OUTPUT_BEFORE = """\
Chain POSTROUTING (policy ACCEPT 15 packets, 1055 bytes)
    pkts      bytes target     prot opt in     out     source               destination
      10        663 DOCKER_POSTROUTING  all  --  *      *       0.0.0.0/0            127.0.0.11
      52      16974 MASQUERADE  all  --  *      !ogstun  10.45.0.0/16         0.0.0.0/0
"""

REAL_IPTABLES_OUTPUT_AFTER = """\
Chain POSTROUTING (policy ACCEPT 15 packets, 1055 bytes)
    pkts      bytes target     prot opt in     out     source               destination
      10        663 DOCKER_POSTROUTING  all  --  *      *       0.0.0.0/0            127.0.0.11
      56      19650 MASQUERADE  all  --  *      !ogstun  10.45.0.0/16         0.0.0.0/0
"""


def test_parse_nat_masquerade_counters_from_real_output():
    assert parse_nat_masquerade_counters(REAL_IPTABLES_OUTPUT_BEFORE) == (52, 16974)
    assert parse_nat_masquerade_counters(REAL_IPTABLES_OUTPUT_AFTER) == (56, 19650)


def test_parse_nat_masquerade_counters_missing_rule_returns_none():
    output_without_rule = "Chain POSTROUTING (policy ACCEPT 0 packets, 0 bytes)\n"
    assert parse_nat_masquerade_counters(output_without_rule) is None


def test_compute_rate_matches_real_captured_increment():
    """Con las dos capturas reales de arriba (4 paquetes / 2676 bytes en
    un intervalo de, p. ej., 5 segundos), la tasa debe ser coherente."""
    pkts_rate, bytes_rate = compute_rate(
        prev_counters=(52, 16974), prev_timestamp=100.0, new_counters=(56, 19650), new_timestamp=105.0
    )
    assert pkts_rate == pytest.approx(4 / 5)
    assert bytes_rate == pytest.approx(2676 / 5)


def test_compute_rate_no_traffic_yields_zero():
    pkts_rate, bytes_rate = compute_rate(
        prev_counters=(0, 0), prev_timestamp=100.0, new_counters=(0, 0), new_timestamp=105.0
    )
    assert (pkts_rate, bytes_rate) == (0.0, 0.0)


def test_compute_rate_zero_elapsed_returns_zero_not_division_error():
    pkts_rate, bytes_rate = compute_rate(
        prev_counters=(100, 5000), prev_timestamp=100.0, new_counters=(200, 8000), new_timestamp=100.0
    )
    assert (pkts_rate, bytes_rate) == (0.0, 0.0)


def test_compute_rate_counter_reset_treated_as_no_data_not_negative():
    """Si el contenedor del UPF se recrea, sus reglas de iptables (y por
    tanto los contadores) se reinician a 0 -- debe tratarse como 'sin dato
    fiable', no como tráfico negativo."""
    pkts_rate, bytes_rate = compute_rate(
        prev_counters=(56, 19650), prev_timestamp=100.0, new_counters=(2, 400), new_timestamp=105.0
    )
    assert (pkts_rate, bytes_rate) == (0.0, 0.0)


@pytest.fixture(autouse=True)
def reset_sampler_state():
    """Aísla el estado del histórico (variable de módulo) entre pruebas."""
    throughput_sampler._reset_for_tests()
    yield
    throughput_sampler._reset_for_tests()


@pytest.mark.asyncio
async def test_sample_once_does_not_record_a_point_on_the_first_reading():
    with patch(
        "app.services.docker_control.get_nat_stats",
        return_value=(True, REAL_IPTABLES_OUTPUT_BEFORE),
    ):
        await throughput_sampler._sample_once()

    assert throughput_sampler.get_history() == []


@pytest.mark.asyncio
async def test_sample_once_records_a_point_on_the_second_reading_with_real_data():
    with patch(
        "app.services.docker_control.get_nat_stats",
        side_effect=[
            (True, REAL_IPTABLES_OUTPUT_BEFORE),
            (True, REAL_IPTABLES_OUTPUT_AFTER),
        ],
    ):
        await throughput_sampler._sample_once()
        await throughput_sampler._sample_once()

    history = throughput_sampler.get_history()
    assert len(history) == 1
    assert history[0].uplink_pkts_per_sec > 0
    assert history[0].uplink_bytes_per_sec > 0


@pytest.mark.asyncio
async def test_sample_once_handles_script_failure_gracefully():
    with patch(
        "app.services.docker_control.get_nat_stats",
        return_value=(False, "No se encuentra el script"),
    ):
        await throughput_sampler._sample_once()  # no debe lanzar excepción

    assert throughput_sampler.get_history() == []
