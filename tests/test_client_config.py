"""Client construction: timeout default and ATT_GATEWAY_TIMEOUT (issue #2)."""

from att_gateway.client import DEFAULT_TIMEOUT, GatewayClient


def test_default_timeout_clears_slow_home_page():
    # home.ha takes ~15 s on a CGW452; the default must leave headroom.
    assert GatewayClient().timeout == DEFAULT_TIMEOUT
    assert DEFAULT_TIMEOUT >= 30


def test_from_env_reads_timeout(monkeypatch):
    monkeypatch.setenv("ATT_GATEWAY_TIMEOUT", "60")
    assert GatewayClient.from_env().timeout == 60.0


def test_from_env_blank_timeout_uses_default(monkeypatch):
    monkeypatch.setenv("ATT_GATEWAY_TIMEOUT", "")
    assert GatewayClient.from_env().timeout == DEFAULT_TIMEOUT
