from zExceptions import HTTPBadGateway, HTTPGatewayTimeout


class DiscodataProviderError(Exception):
    """Base exception for Discodata provider failures."""


class BadGateway(DiscodataProviderError, HTTPBadGateway):
    """HTTP 502 for Discodata errors, connection drops or bad payloads."""


class GatewayTimeout(DiscodataProviderError, HTTPGatewayTimeout):
    """HTTP 504 Gateway Timeout for upstream Discodata connect or read timeouts."""
