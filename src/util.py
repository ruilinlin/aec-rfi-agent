"""Shared helpers used across pipeline stages."""

import ssl


def ssl_context() -> ssl.SSLContext:
    """Return an SSL context that works around the python.org macOS cert issue."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()
