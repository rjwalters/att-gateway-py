"""att_gateway — read and configure AT&T ARRIS fiber gateways from Python.

Supports the CGW452 (AT&T Business Fiber "All-Fi Hub") and, by family, the
BGW320. The headline capability is programmatic **IP Passthrough**, so a router
like a UniFi UDM-Pro can be handed the public IP.
"""

from .client import GatewayClient
from .exceptions import (
    AuthError,
    FormError,
    GatewayError,
    NonceError,
    WriteVerificationError,
)
from .models import Device, Form, IPPassthroughState

__version__ = "0.1.0"

__all__ = [
    "GatewayClient",
    "Device",
    "Form",
    "IPPassthroughState",
    "GatewayError",
    "AuthError",
    "NonceError",
    "FormError",
    "WriteVerificationError",
]
