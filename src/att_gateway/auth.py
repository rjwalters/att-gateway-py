"""Authentication for AT&T ARRIS gateways (CGW452, BGW320).

The gateways use a nonce + MD5 challenge that is implemented in JavaScript on the
login page (``/cgi-bin/login.ha``). Reverse-engineered from the CGW452 login page
and cross-checked against edgan/att-fiber-gateway-info (BGW320). The page's own
``hashpwd()`` computes::

    hashpassword = hex_md5(access_code + nonce)

then masks the cleartext ``password`` field before POSTing. We reproduce that
exactly, then ride the session cookie the gateway sets.
"""

from __future__ import annotations

import hashlib
import re

# The nonce is a lowercase hex hidden input on the login page. It is rendered
# client-side, so we try a few shapes to be resilient to markup/order changes.
_NONCE_PATTERNS = [
    re.compile(r'name=["\']nonce["\'][^>]*value=["\']([0-9a-fA-F]{16,})["\']'),
    re.compile(r'value=["\']([0-9a-fA-F]{16,})["\'][^>]*name=["\']nonce["\']'),
    re.compile(r'getElementsByName\(["\']nonce["\']\)\[0\]\.value\s*=\s*["\']([0-9a-fA-F]{16,})["\']'),
]


def hash_password(access_code: str, nonce: str) -> str:
    """Return ``hex_md5(access_code + nonce)`` — the gateway's login hash.

    This mirrors ``hashpwd()`` in the gateway's login page JavaScript.
    """
    return hashlib.md5((access_code + nonce).encode("utf-8")).hexdigest()


def extract_nonce(login_html: str) -> str | None:
    """Pull the login nonce out of a fetched login page, or ``None``."""
    for pattern in _NONCE_PATTERNS:
        match = pattern.search(login_html)
        if match:
            return match.group(1)
    return None


def build_login_payload(access_code: str, nonce: str) -> dict:
    """Build the POST body the login form submits.

    ``password`` is masked to asterisks (matching the JS, which replaces the
    field with one ``*`` per character) and ``hashpassword`` carries the hash.
    """
    return {
        "nonce": nonce,
        "password": "*" * len(access_code),
        "hashpassword": hash_password(access_code, nonce),
        "Continue": "Continue",
    }
