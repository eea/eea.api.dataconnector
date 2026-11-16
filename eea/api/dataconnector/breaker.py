"""Circuit breakers for the shared Discodata service.

All connectors post to the same Discodata host, so a single service-level
breaker would let one slow statement fail every other connector. Failures are
therefore tracked at two levels: per endpoint and per SQL query.
"""

import logging
import os
from hashlib import sha1
from time import monotonic

from eea.api.dataconnector.exceptions import BadGateway, GatewayTimeout
from eea.api.dataconnector.utils import parse_positive_float

logger = logging.getLogger(__name__)

DEFAULT_COOLDOWN = 15.0

_endpoint_circuits = {}
_query_circuits = {}


def _cooldown():
    """Return the configured cooldown in seconds."""
    return parse_positive_float(
        os.environ.get("DISCODATA_CIRCUIT_COOLDOWN"), DEFAULT_COOLDOWN
    )


def _query_key(endpoint_url, sql_query):
    """Return the query store key of one SQL statement.

    Virtual pages carry a per-entity id, so a context-based key would be
    recreated for every guessed entity.
    """
    digest = sha1((sql_query or "").encode("utf-8")).hexdigest()[:12]
    return f"{endpoint_url}|{digest}"


def _remaining(store, key):
    """Return the remaining seconds and error of an open circuit.

    Expired entries are pruned, so the stores cannot keep dead keys.
    """
    entry = store.get(key)
    if entry is None:
        return 0.0, None
    deadline, error = entry
    now = monotonic()
    if deadline > now:
        return deadline - now, error
    if store.get(key) == entry:
        store.pop(key, None)
    return 0.0, None


def _trip(store, key, label, error):
    """Open one circuit for a cooldown and log it once."""
    cooldown = _cooldown()
    now = monotonic()
    for expired in [k for k, entry in store.items() if entry[0] <= now]:
        store.pop(expired, None)
    store[key] = (now + cooldown, error)
    logger.error("Discodata circuit opened for %s for %.1fs", label, cooldown)


def check(endpoint_url, sql_query):
    """Raise while a circuit is open for this endpoint or this query."""
    remaining, error = _remaining(_endpoint_circuits, endpoint_url)
    if remaining:
        raise error(
            f"Discodata circuit open for {endpoint_url}, retry in {remaining:.1f}s"
        )
    remaining, error = _remaining(_query_circuits, _query_key(endpoint_url, sql_query))
    if remaining:
        raise error(
            f"Discodata circuit open for {endpoint_url} query, "
            f"retry in {remaining:.1f}s"
        )


def trip_endpoint(endpoint_url, error=BadGateway):
    """Open the circuit of one endpoint for a cooldown."""
    _trip(_endpoint_circuits, endpoint_url, endpoint_url, error)


def trip_query(endpoint_url, sql_query, error=GatewayTimeout):
    """Open the circuit of one SQL statement for a cooldown."""
    key = _query_key(endpoint_url, sql_query)
    _trip(_query_circuits, key, f"{endpoint_url} query", error)


def reset():
    """Clear both stores. Only for tests."""
    _endpoint_circuits.clear()
    _query_circuits.clear()
