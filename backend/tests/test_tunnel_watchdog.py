import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("watchdog", Path(__file__).resolve().parents[2] / "scripts/tunnel_watchdog.py")
watchdog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watchdog)
OK = (200, b'{"status":"ok","mode":"public-release"}')
READY = (200, b'{"readyConnections":4}')
DOWN = (503, b'{"readyConnections":0}')


@pytest.mark.parametrize("public,origin,connector,expected", [
    (OK, OK, DOWN, "healthy"),
    ((530, b"error code: 1033"), OK, READY, "tunnel-disconnected"),
    ((0, b""), OK, DOWN, "tunnel-disconnected"),
    ((530, b"other error"), OK, READY, "public-check-inconclusive"),
    ((403, b"access denied"), OK, DOWN, "public-check-inconclusive"),
    ((503, b""), (500, b""), DOWN, "origin-unavailable"),
    ((200, b"maintenance page"), OK, READY, "public-check-inconclusive"),
])
def test_only_restart_for_tunnel_failure(public, origin, connector, expected):
    assert watchdog.classify(public, origin, connector) == expected


def test_confirm_repeated_failure_and_persisted_cooldown():
    assert not watchdog.should_restart(2, 3600, 0)
    assert not watchdog.should_restart(3, 3600, 3590)
    assert watchdog.should_restart(3, 3600, 1800)

