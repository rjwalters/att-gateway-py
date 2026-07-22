"""Tests for the reboot form round-trip (no live gateway needed)."""

from att_gateway.client import GatewayClient

RESTART_FORM = """
<html><body>
<form action="/cgi-bin/restart.ha" method="post">
  <input type="hidden" name="nonce" value="c67ca7510104b74f">
  <input type="submit" name="Restart" value="Restart">
  <input type="submit" name="Cancel" value="Cancel">
</form>
</body></html>
"""


class _FakeClient(GatewayClient):
    """Client with network calls stubbed out, to test payload construction."""

    def __init__(self):
        super().__init__(access_code="x")
        self._logged_in = True
        self.posted = None

    def get(self, page):  # noqa: D401 - stub
        return RESTART_FORM

    def post(self, action, data):  # noqa: D401 - stub
        self.posted = (action, data)
        return "ok"


def test_reboot_dry_run_presses_restart_and_keeps_nonce():
    payload = _FakeClient().reboot(dry_run=True)
    assert payload["nonce"] == "c67ca7510104b74f"
    assert payload["Restart"] == "Restart"
    # Cancel must not be submitted
    assert "Cancel" not in payload


def test_reboot_posts_to_form_action():
    client = _FakeClient()
    client.reboot()
    action, data = client.posted
    assert action == "/cgi-bin/restart.ha"
    assert data["Restart"] == "Restart"
