"""High-level client for AT&T ARRIS gateways.

Design note: rather than hardcode every hidden field on the gateway's config
forms, we log in, GET the live config page, parse the *entire* form, mutate only
the fields we care about, and POST it back. This round-trips the per-page nonce
and any firmware-specific hidden fields automatically, which is what makes writes
to these gateways reliable across firmware revisions.
"""

from __future__ import annotations

import os
from typing import Optional

import requests
from bs4 import BeautifulSoup

from . import auth
from .exceptions import (
    AuthError,
    FormError,
    NonceError,
    WriteVerificationError,
)
from .models import Device, Form, IPPassthroughState

# IP Passthrough form field names, confirmed on CGW452 firmware (ARRIS).
# `set_ip_passthrough` verifies these exist on the live form before submitting
# and raises a clear error (with the real field list) if the firmware differs.
PASSTHROUGH_ALLOC_FIELD = "allocmode"
PASSTHROUGH_MODE_FIELD = "passmode"
PASSTHROUGH_MAC_FIELD = "passmac"          # free-text field → manual MAC entry works
PASSTHROUGH_ALLOC_ON = "passthrough"
PASSTHROUGH_ALLOC_OFF = "normal"           # normal routed/NAT mode
PASSTHROUGH_MODE_FIXED = "dhcps-fixed"
PASSTHROUGH_SAVE_BUTTON = "Save"           # the submit button that commits the form

# Seconds per request. Override with ATT_GATEWAY_TIMEOUT (see .env.example).
DEFAULT_TIMEOUT = 45.0


class GatewayClient:
    """Read and configure an AT&T ARRIS gateway over its local web UI."""

    def __init__(
        self,
        host: str = "192.168.1.254",
        access_code: Optional[str] = None,
        *,
        verify_tls: bool = False,
        # The CGW452's home.ha takes ~15 s to answer every time (fw 4.33.5),
        # so the old 15 s default timed out on login.
        timeout: float = DEFAULT_TIMEOUT,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base = f"https://{host}"
        self.access_code = access_code
        self.verify_tls = verify_tls
        self.timeout = timeout
        self.session = session or requests.Session()
        if not verify_tls:
            # The gateway ships a self-signed cert; silence the noise.
            requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
        self._logged_in = False

    # ---- construction helpers -------------------------------------------------

    @classmethod
    def from_env(cls, session: Optional[requests.Session] = None) -> "GatewayClient":
        """Build a client from ATT_GATEWAY_* environment variables (.env)."""
        return cls(
            host=os.environ.get("ATT_GATEWAY_HOST", "192.168.1.254"),
            access_code=os.environ.get("ATT_GATEWAY_ACCESS_CODE") or None,
            verify_tls=os.environ.get("ATT_GATEWAY_VERIFY_TLS", "0") == "1",
            timeout=float(os.environ.get("ATT_GATEWAY_TIMEOUT") or DEFAULT_TIMEOUT),
            session=session,
        )

    # ---- low-level HTTP -------------------------------------------------------

    def _url(self, page: str) -> str:
        page = page.lstrip("/")
        if not page.startswith("cgi-bin/"):
            page = f"cgi-bin/{page}"
        return f"{self.base}/{page}"

    def get(self, page: str) -> str:
        resp = self.session.get(
            self._url(page), verify=self.verify_tls, timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.text

    def post(self, action: str, data: dict) -> str:
        resp = self.session.post(
            self._url(action), data=data, verify=self.verify_tls, timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.text

    # ---- authentication -------------------------------------------------------

    def login(self) -> None:
        """Establish a session. Idempotent within a client instance."""
        if not self.access_code:
            raise AuthError(
                "No access code set. Pass access_code= or set ATT_GATEWAY_ACCESS_CODE."
            )
        # The gateway serves a "cookies must be enabled" stub on the first GET and
        # only sets the SessionID cookie then; the real form + nonce appear on the
        # second GET that presents that cookie. Our requests.Session carries it.
        nonce = None
        for _ in range(2):
            html = self.get("login.ha")
            nonce = auth.extract_nonce(html)
            if nonce:
                break
        if not nonce:
            raise NonceError(
                "Could not find the login nonce after the cookie handshake. The "
                "login page markup may have changed — capture cgi-bin/login.ha "
                "(second GET, with the SessionID cookie) and open an issue."
            )
        payload = auth.build_login_payload(self.access_code, nonce)
        result = self.post("login.ha", payload)
        if self._looks_like_login_page(result):
            raise AuthError("Login rejected — check the Device Access Code.")
        self._logged_in = True

    def _ensure_login(self) -> None:
        if not self._logged_in:
            self.login()

    @staticmethod
    def _looks_like_login_page(html: str) -> bool:
        # The gateway serves the login page (with hashpwd JS) for any protected
        # URL until authenticated.
        return "hashpassword" in html and "hashpwd" in html

    # ---- form parsing ---------------------------------------------------------

    def parse_form(self, html: str, *, form_id: Optional[str] = None) -> Form:
        """Parse a form on a page into a :class:`Form` (action + field values)."""
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form", id=form_id) if form_id else soup.find("form")
        if form is None:
            raise FormError("No <form> found on page.")
        action = form.get("action") or ""
        fields: dict = {}
        for inp in form.find_all("input"):
            name = inp.get("name")
            if not name:
                continue
            itype = (inp.get("type") or "text").lower()
            # Skip action buttons — the caller adds the intended submit explicitly,
            # so a form with several submits (Update/Save/Cancel) round-trips cleanly.
            if itype in ("submit", "button", "reset", "image"):
                continue
            if itype in ("radio", "checkbox") and not inp.has_attr("checked"):
                continue
            fields[name] = inp.get("value", "")
        for sel in form.find_all("select"):
            name = sel.get("name")
            if not name:
                continue
            chosen = sel.find("option", selected=True) or sel.find("option")
            fields[name] = chosen.get("value", "") if chosen else ""
        for ta in form.find_all("textarea"):
            if ta.get("name"):
                fields[ta["name"]] = ta.text
        return Form(action=action or "", fields=fields)

    # ---- IP Passthrough -------------------------------------------------------

    def get_ip_passthrough(self, page: str = "ippass.ha") -> IPPassthroughState:
        """Read the current IP Passthrough configuration."""
        self._ensure_login()
        html = self.get(page)
        if self._looks_like_login_page(html):
            raise AuthError("Not authenticated when reading IP Passthrough page.")
        form = self.parse_form(html)
        alloc = form.fields.get(PASSTHROUGH_ALLOC_FIELD, "")
        return IPPassthroughState(
            allocation_mode=alloc,
            passthrough_mode=form.fields.get(PASSTHROUGH_MODE_FIELD),
            fixed_mac=form.fields.get(PASSTHROUGH_MAC_FIELD) or None,
            # passmac is a free-text input, so manual MAC entry is always available.
            manual_entry_supported=PASSTHROUGH_MAC_FIELD in form.fields,
            raw_fields=dict(form.fields),
        )

    def set_ip_passthrough(
        self,
        mac: str,
        *,
        enable: bool = True,
        page: str = "ippass.ha",
        dry_run: bool = False,
        verify: bool = True,
    ) -> dict:
        """Enable (or disable) IP Passthrough, binding it to ``mac``.

        Returns the POST payload that was (or would be) submitted. With
        ``dry_run=True`` nothing is sent — use this to inspect the exact write
        before committing it to a live gateway.
        """
        self._ensure_login()
        html = self.get(page)
        if self._looks_like_login_page(html):
            raise AuthError("Not authenticated when opening IP Passthrough page.")
        form = self.parse_form(html)

        missing = [
            f
            for f in (PASSTHROUGH_ALLOC_FIELD, PASSTHROUGH_MAC_FIELD)
            if f not in form.fields
        ]
        if missing:
            raise FormError(
                "IP Passthrough form is missing expected field(s) "
                f"{missing}. Fields present: {sorted(form.fields)}. Update the "
                "PASSTHROUGH_* constants in client.py to match this firmware."
            )

        payload = form.with_overrides(
            **{
                PASSTHROUGH_ALLOC_FIELD: (
                    PASSTHROUGH_ALLOC_ON if enable else PASSTHROUGH_ALLOC_OFF
                ),
                PASSTHROUGH_MAC_FIELD: mac if enable else "",
            }
        )
        if enable and PASSTHROUGH_MODE_FIELD in form.fields:
            payload[PASSTHROUGH_MODE_FIELD] = PASSTHROUGH_MODE_FIXED
        # Explicitly press the "Save" button (the form has several submits).
        payload[PASSTHROUGH_SAVE_BUTTON] = PASSTHROUGH_SAVE_BUTTON

        if dry_run:
            return payload

        self.post(form.action or page, payload)
        if verify:
            state = self.get_ip_passthrough(page)
            if enable and (state.fixed_mac or "").lower() != mac.lower():
                raise WriteVerificationError(
                    f"Passthrough MAC read back as {state.fixed_mac!r}, expected {mac!r}."
                )
        return payload

    # ---- restart --------------------------------------------------------------

    def reboot(self, *, dry_run: bool = False, page: str = "restart.ha") -> dict:
        """Reboot the gateway (Device → Restart Device).

        Round-trips the restart form's nonce and presses ``Restart``. With
        ``dry_run=True`` the POST body is returned without sending. The gateway
        drops its connection during reboot, so the POST may not return a clean
        response — that is expected and not treated as an error.
        """
        self._ensure_login()
        html = self.get(page)
        if self._looks_like_login_page(html):
            raise AuthError("Not authenticated when opening the restart page.")
        form = self.parse_form(html)
        payload = form.with_overrides()
        payload["Restart"] = "Restart"
        if dry_run:
            return payload
        try:
            self.post(form.action or page, payload)
        except requests.RequestException:
            # Gateway went down mid-request while rebooting — expected.
            pass
        return payload

    # ---- device list ----------------------------------------------------------

    def get_devices(self, page: str = "devices.ha") -> list[Device]:
        """Parse the gateway's device list. Best-effort across firmware layouts."""
        self._ensure_login()
        html = self.get(page)
        soup = BeautifulSoup(html, "html.parser")
        devices: list[Device] = []
        for row in soup.find_all("tr"):
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cells) < 2:
                continue
            joined = " ".join(cells).lower()
            if "on" not in joined and "off" not in joined:
                continue
            devices.append(
                Device(
                    name=cells[0],
                    online="on" in cells and "off" not in cells[:1],
                    connection=next((c for c in cells if c in ("Ethernet", "Wi-Fi")), None),
                )
            )
        return devices
