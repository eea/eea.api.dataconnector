"""Circuit breakers for Discodata endpoints and connector definitions.

All connectors share the same Discodata host, so a single service-level
breaker would let one slow statement fail every other connector. Failures
are therefore tracked at two levels: service failures (connection errors,
connect timeouts, 5xx) open the breaker of the whole endpoint, while read
timeouts open only the breaker of the connector definition that hit them.
"""

import hashlib
import logging
import os
from time import monotonic

from eea.api.dataconnector.exceptions import BadGateway, GatewayTimeout
from eea.api.dataconnector.utils import parse_positive_float

logger = logging.getLogger(__name__)

DEFAULT_COOLDOWN = 15.0

_endpoint_open_until = {}
_query_open_until = {}


def _cooldown():
    """Return the configured cooldown in seconds."""
    return parse_positive_float(
        os.environ.get("DISCODATA_CIRCUIT_COOLDOWN"), DEFAULT_COOLDOWN
    )


def _query_key(endpoint_url, sql_query):
    """Return the key identifying one connector definition on an endpoint."""
    digest = hashlib.sha1((sql_query or "").encode("utf-8")).hexdigest()[:12]
    return f"{endpoint_url}|{digest}"


def _remaining(store, key):
    """Return cooldown seconds left for key, pruning it once expired."""
    deadline = store.get(key)
    if deadline is None:
        return 0.0
    remaining = deadline - monotonic()
    if remaining > 0:
        return remaining
    if store.get(key) == deadline:
        store.pop(key, None)
    return 0.0


def _trip(store, key, label):
    """Open the breaker behind store for one cooldown window."""
    cooldown = _cooldown()
    now = monotonic()
    for expired in [k for k, deadline in store.items() if deadline <= now]:
        store.pop(expired, None)
    store[key] = now + cooldown
    logger.error("Discodata circuit opened for %s for %.1fs", label, cooldown)


def check(endpoint_url, sql_query):
    """Raise while either the endpoint or the query breaker is open."""
    remaining = _remaining(_endpoint_open_until, endpoint_url)
    if remaining > 0:
        raise BadGateway(
            f"Discodata circuit open for endpoint {endpoint_url}, "
            f"retry in {remaining:.1f}s"
        )

    remaining = _remaining(_query_open_until, _query_key(endpoint_url, sql_query))
    if remaining > 0:
        raise GatewayTimeout(
            f"Discodata circuit open for {endpoint_url} query, "
            f"retry in {remaining:.1f}s"
        )


def trip_endpoint(endpoint_url):
    """Open the breaker of the whole endpoint for one cooldown window."""
    _trip(_endpoint_open_until, endpoint_url, endpoint_url)


def trip_query(endpoint_url, sql_query):
    """Open the breaker of one connector definition for one cooldown window."""
    key = _query_key(endpoint_url, sql_query)
    _trip(_query_open_until, key, key)


def reset():
    """Clear all breaker state. Intended for tests."""
    _endpoint_open_until.clear()
    _query_open_until.clear()
