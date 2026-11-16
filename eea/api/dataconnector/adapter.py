"""behavior module"""

import logging
import os
import time

import requests
from mo_sql_parsing import format as sql_format
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface
from zope.schema.interfaces import IField
from zope.publisher.interfaces.browser import IBrowserRequest
from plone.restapi.types.interfaces import IJsonSchemaProvider
from plone.restapi.types.adapters import DefaultJsonSchemaProvider
from eea.api.dataconnector.interfaces import (
    IConnectorDataProvider,
    IDataProvider,
)
from eea.api.dataconnector.utils import parse_positive_float, timing
from eea.api.dataconnector.queryparser import parseQuery
from eea.api.dataconnector.queryfilter import filteredData
from eea.api.dataconnector import breaker
from eea.api.dataconnector.exceptions import BadGateway, GatewayTimeout

logger = logging.getLogger(__name__)

DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_READ_TIMEOUT = 30.0


def _log_transport_failure(reason, started, endpoint, err):
    """Log one transport failure with the time it took."""
    logger.error(
        "%s after %.3fs on %s: %s", reason, time.monotonic() - started, endpoint, err
    )


def _get_discodata_timeouts():
    """Return the effective connect and read timeouts for Discodata."""
    shared = os.environ.get("DISCODATA_TIMEOUT")
    connect = parse_positive_float(
        os.environ.get("DISCODATA_CONNECT_TIMEOUT"),
        parse_positive_float(shared, DEFAULT_CONNECT_TIMEOUT),
    )
    read_timeout = parse_positive_float(
        os.environ.get("DISCODATA_READ_TIMEOUT"),
        parse_positive_float(shared, DEFAULT_READ_TIMEOUT),
    )
    return connect, read_timeout


@adapter(IConnectorDataProvider, IBrowserRequest)
@implementer(IDataProvider)
class DataProviderForConnectors:
    """data provider for connectors"""

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def _get_metadata(self):
        """_get_metadata."""
        return {"readme": self.context.readme}

    @timing
    def _get_data(self):
        """_get_data."""
        data = {}
        metadata = self._get_metadata()
        sql = parseQuery(self.context, self.request)

        if not sql:
            return {"results": {}, "metadata": metadata}

        conditions = sql.get("conditions")
        data_query = sql.get("data_query")
        form = sql.get("form")
        query = sql.get("query")

        if "where" in query and conditions:
            query["where"] = {"and": conditions + [query["where"]]}
        elif "where" not in query and len(conditions) > 1:
            query["where"] = {"and": conditions}
        elif len(conditions) == 1:
            query["where"] = conditions[0]

        formatted_query = sql_format(query)
        if " <> " in formatted_query:
            formatted_query = formatted_query.replace(" <> ", " != ")

        data["query"] = formatted_query

        if form.get("p"):
            data["p"] = form.get("p")

        if form.get("nrOfHits"):
            data["nrOfHits"] = form.get("nrOfHits")

        endpoint = self.context.endpoint_url
        breaker.check(endpoint, self.context.sql_query)
        connect_timeout, read_timeout = _get_discodata_timeouts()
        started = time.monotonic()
        try:
            req = requests.post(
                endpoint,
                data,
                timeout=(connect_timeout, read_timeout),
            )
        except requests.ConnectTimeout as err:
            _log_transport_failure("Discodata timeout", started, endpoint, err)
            breaker.trip_endpoint(endpoint, GatewayTimeout)
            raise GatewayTimeout(f"Discodata did not answer on {endpoint}") from err
        except requests.Timeout as err:
            _log_transport_failure("Discodata timeout", started, endpoint, err)
            breaker.trip_query(endpoint, self.context.sql_query)
            raise GatewayTimeout(f"Discodata did not answer on {endpoint}") from err
        except requests.RequestException as err:
            _log_transport_failure("Discodata request failed", started, endpoint, err)
            breaker.trip_endpoint(endpoint)
            raise BadGateway(f"Discodata request failed on {endpoint}") from err

        elapsed = time.monotonic() - started
        if not 200 <= req.status_code < 300:
            logger.error(
                "Discodata answered HTTP %s after %.3fs on %s: %s",
                req.status_code,
                elapsed,
                endpoint,
                (req.text or "")[:300],
            )
            if req.status_code >= 500:
                breaker.trip_query(endpoint, self.context.sql_query, BadGateway)
            raise BadGateway(f"Discodata answered HTTP {req.status_code} on {endpoint}")

        try:
            payload = req.json()
        except ValueError as err:
            logger.error(
                "Discodata returned invalid JSON after %.3fs on %s: %s",
                elapsed,
                endpoint,
                (req.text or "")[:300],
            )
            raise BadGateway(f"Discodata returned invalid JSON on {endpoint}") from err

        if not isinstance(payload, dict):
            logger.error(
                "Discodata returned a payload of type %s after %.3fs on %s",
                type(payload).__name__,
                elapsed,
                endpoint,
            )
            raise BadGateway(f"Discodata returned an unusable payload on {endpoint}")

        sql_errors = payload.get("errors")
        if sql_errors:
            logger.warning(
                "Discodata reported errors after %.3fs on %s: %s",
                elapsed,
                endpoint,
                sql_errors,
            )
            return {"results": {}, "metadata": metadata}

        raw_rows = payload.get("results")
        if raw_rows is None:
            raw_rows = []

        if not isinstance(raw_rows, list) or not all(
            isinstance(row, dict) for row in raw_rows
        ):
            logger.error(
                "Discodata returned unusable results after %.3fs on %s: %s",
                elapsed,
                endpoint,
                type(raw_rows).__name__,
            )
            raise BadGateway(f"Discodata returned unusable results on {endpoint}")

        return {
            "results": filteredData(raw_rows, data_query),
            "metadata": metadata,
        }

    # TO DO: persistent caching, periodical refresh, etc
    def _provided_data(self):
        """provided data"""
        if not self.context.sql_query:
            return {"results": {}, "metadata": self._get_metadata()}
        return self._get_data()

    @property
    def provided_data(self):
        """provided data"""
        return self._provided_data()


@adapter(IField, Interface, Interface)
@implementer(IJsonSchemaProvider)
class DataQueryJsonSchemaProvider(DefaultJsonSchemaProvider):
    """Schema provider for DataQuery"""

    def get_type(self):
        """return type of object"""
        return "array"
