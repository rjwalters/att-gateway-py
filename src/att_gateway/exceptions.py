"""Exception hierarchy for att_gateway."""


class GatewayError(Exception):
    """Base class for all gateway errors."""


class AuthError(GatewayError):
    """Login failed, or a config request was rejected for lack of a session."""


class NonceError(AuthError):
    """The login nonce could not be located on the page."""


class FormError(GatewayError):
    """A config form could not be found or parsed on a page."""


class WriteVerificationError(GatewayError):
    """A configuration write did not read back with the expected value."""
