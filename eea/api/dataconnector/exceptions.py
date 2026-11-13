from zExceptions import HTTPBadGateway, HTTPGatewayTimeout


class DiscodataProviderError(Exception):
    """Base exception for Discodata provider failures."""


class BadGateway(DiscodataProviderError, HTTPBadGateway):
    """HTTP 502 Bad Gateway for upstream Discodata errors, connection drops, or malformed payloads."""


class GatewayTimeout(DiscodataProviderError, HTTPGatewayTimeout):
    """HTTP 504 Gateway Timeout for upstream Discodata connect or read timeouts."""
