"""Tests for form parsing and field round-tripping (no live gateway needed)."""

from att_gateway.client import GatewayClient
from att_gateway.models import Form

# Mirrors the real CGW452 ippass.ha form (field names/values confirmed live).
SAMPLE_FORM = """
<html><body>
<form action="/cgi-bin/ippass.ha" method="post">
  <input type="hidden" name="nonce" value="deadbeefcafe0123">
  <input type="hidden" name="defsrvint" value="">
  <input type="submit" name="Update" value="Update">
  <input type="text" name="passmac" value="">
  <select name="allocmode">
    <option value="normal">Default Server</option>
    <option value="defaultserver">Default Server (DHCPS)</option>
    <option value="passthrough" selected>Passthrough</option>
  </select>
  <select name="passmode">
    <option value="dhcps-fixed" selected>DHCPS-fixed</option>
    <option value="manual">Manual</option>
  </select>
  <input type="submit" name="Save" value="Save">
  <input type="submit" name="Cancel" value="Cancel">
</form>
</body></html>
"""


def _client() -> GatewayClient:
    return GatewayClient(access_code="x")


def test_parse_form_collects_fields_and_skips_submit_buttons():
    form = _client().parse_form(SAMPLE_FORM)
    assert form.action == "/cgi-bin/ippass.ha"
    assert form.fields["nonce"] == "deadbeefcafe0123"
    assert form.fields["defsrvint"] == ""
    assert form.fields["allocmode"] == "passthrough"  # selected option
    assert form.fields["passmode"] == "dhcps-fixed"
    assert form.fields["passmac"] == ""
    # submit buttons must NOT be round-tripped
    assert "Update" not in form.fields
    assert "Save" not in form.fields
    assert "Cancel" not in form.fields


def test_with_overrides_preserves_nonce_and_hidden_fields():
    form = Form(action="/x", fields={"nonce": "abc", "hidden_flag": "keepme", "a": "0"})
    payload = form.with_overrides(a="1")
    assert payload["a"] == "1"
    assert payload["nonce"] == "abc"          # nonce survives
    assert payload["hidden_flag"] == "keepme"  # unknown hidden field survives


def test_with_overrides_ignores_none_values():
    form = Form(action="/x", fields={"a": "0"})
    assert form.with_overrides(a=None) == {"a": "0"}
