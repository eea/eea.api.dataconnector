"""behavior module"""

import logging
import math
import os
import time

import requests
from mo_sql_parsing import format as sql_format
from plone.restapi.types.adapters import DefaultJsonSchemaProvider
from plone.restapi.types.interfaces import IJsonSchemaProvider
from zope.component import adapter
from zope.interface import Interface, implementer
from zope.publisher.interfaces.browser import IBrowserRequest
from zope.schema.interfaces import IField

from eea.api.dataconnector.exceptions import BadGateway, GatewayTimeout
from eea.api.dataconnector.interfaces import (
    IConnectorDataProvider,
    IDataProvider,
)
from eea.api.dataconnector.queryfilter import filteredData
from eea.api.dataconnector.queryparser import parseQuery
from eea.api.dataconnector.utils import timing

logger = logging.getLogger(__name__)

DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_READ_TIMEOUT = 15.0


def _parse_timeout(value, default):
    if value is None:
        return default
    try:
        parsed = float(value)
        if math.isfinite(parsed) and parsed > 0:
            return parsed
    except (ValueError, TypeError):
        pass
    return default


def _get_discodata_timeouts():
    fallback = _parse_timeout(os.environ.get("DISCODATA_TIMEOUT"), None)
    connect_default = fallback if fallback is not None else DEFAULT_CONNECT_TIMEOUT
    read_default = fallback if fallback is not None else DEFAULT_READ_TIMEOUT
    connect_timeout = _parse_timeout(
        os.environ.get("DISCODATA_CONNECT_TIMEOUT"), connect_default
    )
    read_timeout = _parse_timeout(
        os.environ.get("DISCODATA_READ_TIMEOUT"), read_default
    )
    return (connect_timeout, read_timeout)


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
            return {"results": [], "metadata": metadata}

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

        start_time = time.monotonic()
        timeouts = _get_discodata_timeouts()

        try:
            req = requests.post(self.context.endpoint_url, data, timeout=timeouts)
        except requests.Timeout as err:
            elapsed = time.monotonic() - start_time
            logger.error(
                "Discodata request timed out after %.2fs for endpoint %s: %s",
                elapsed,
                self.context.endpoint_url,
                err,
            )
            raise GatewayTimeout(
                f"Discodata request timed out after {elapsed:.2f}s: {self.context.endpoint_url}"
            ) from err
        except requests.RequestException as err:
            elapsed = time.monotonic() - start_time
            logger.error(
                "Discodata connection failure after %.2fs for endpoint %s: %s",
                elapsed,
                self.context.endpoint_url,
                err,
            )
            raise BadGateway(f"Discodata connection failure: {err}") from err

        elapsed = time.monotonic() - start_time
        if not (200 <= req.status_code < 300):
            body_snippet = (req.text or "")[:300]
            logger.error(
                "Discodata returned HTTP %s after %.2fs for endpoint %s: %s",
                req.status_code,
                elapsed,
                self.context.endpoint_url,
                body_snippet,
            )
            raise BadGateway(
                f"Discodata returned HTTP {req.status_code}: {body_snippet}"
            )

        try:
            payload = req.json()
        except Exception as err:
            body_snippet = (req.text or "")[:300]
            logger.error(
                "Discodata returned malformed JSON after %.2fs for endpoint %s: %s",
                elapsed,
                self.context.endpoint_url,
                body_snippet,
            )
            raise BadGateway(
                f"Discodata returned malformed JSON: {body_snippet}"
            ) from err

        if not isinstance(payload, dict):
            logger.error(
                "Discodata returned non-dict payload after %.2fs for endpoint %s: %r",
                elapsed,
                self.context.endpoint_url,
                type(payload),
            )
            raise BadGateway(
                "Discodata returned invalid payload shape (expected object)"
            )

        errors = payload.get("errors")
        if errors:
            logger.error(
                "Discodata returned error payload after %.2fs for endpoint %s: %s",
                elapsed,
                self.context.endpoint_url,
                errors,
            )
            raise BadGateway(f"Discodata provider error: {errors}")

        raw_rows = payload.get("results")
        if raw_rows is None:
            raw_rows = []
        if not isinstance(raw_rows, list):
            logger.error(
                "Discodata returned invalid results field after %.2fs for endpoint %s: %r",
                elapsed,
                self.context.endpoint_url,
                type(raw_rows),
            )
            raise BadGateway("Discodata results field is missing or not a list")

        return {
            "results": filteredData(raw_rows, data_query) or {},
            "metadata": metadata,
        }

    # TO DO: persistent caching, periodical refresh, etc
    def _provided_data(self):
        """provided data"""
        if not self.context.sql_query:
            return {"results": [], "metadata": self._get_metadata()}
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
