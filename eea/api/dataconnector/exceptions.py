"""Exceptions raised when the Discodata provider fails."""

from zExceptions import HTTPBadGateway, HTTPGatewayTimeout


class DiscodataProviderError(Exception):
    """Base class for Discodata provider failures."""


class BadGateway(DiscodataProviderError, HTTPBadGateway):
    """The upstream Discodata endpoint failed or answered unusably."""


class GatewayTimeout(DiscodataProviderError, HTTPGatewayTimeout):
    """The upstream Discodata endpoint did not answer in time."""
