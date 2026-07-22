"""Typed data structures parsed from gateway pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Device:
    """A device the gateway has seen on the LAN (from the device list page)."""

    name: str
    ipv4: Optional[str] = None
    mac: Optional[str] = None
    connection: Optional[str] = None  # "Ethernet" / "Wi-Fi"
    online: bool = False


@dataclass
class IPPassthroughState:
    """Current IP Passthrough configuration on the gateway.

    ``allocation_mode`` is the gateway's own wording, e.g. "Default Server" (off)
    or "Passthrough". ``fixed_mac`` is the DHCPS-fixed bound MAC, when set.
    """

    allocation_mode: str
    passthrough_mode: Optional[str] = None  # e.g. "DHCPS-fixed"
    fixed_mac: Optional[str] = None
    manual_entry_supported: bool = False
    # Raw form field values, kept so a write can round-trip unknown hidden fields.
    raw_fields: dict = field(default_factory=dict)

    @property
    def enabled(self) -> bool:
        return "passthrough" in self.allocation_mode.lower()


@dataclass
class Form:
    """A parsed HTML form: its POST target plus every input's current value."""

    action: str
    fields: dict  # name -> value (hidden fields, nonce, selects, text inputs)

    def with_overrides(self, **overrides: str) -> dict:
        """Return a copy of ``fields`` with ``overrides`` applied.

        Unknown hidden fields (including the per-page nonce) are preserved,
        which is what makes re-submitting these gateway forms reliable.
        """
        merged = dict(self.fields)
        merged.update({k: v for k, v in overrides.items() if v is not None})
        return merged
