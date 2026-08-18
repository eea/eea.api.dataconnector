# -*- coding: utf-8 -*-
"""dataconnector"""

import hashlib
import json
import logging
import os

import requests
from Acquisition import aq_base, aq_inner, aq_parent
from plone.memoize import ram
from plone.restapi.deserializer import json_body

# plone imports
from plone.restapi.interfaces import IExpandableElement
from plone.restapi.services import Service

# zope imports
from zope.component import adapter, getMultiAdapter, queryMultiAdapter
from zope.interface import Interface, implementer
from zope.interface.interfaces import ComponentLookupError
from zExceptions import NotFound

# eea imports
from eea.api.dataconnector.interfaces import (
    IConnectorDataProvider,
    IDataProvider,
    IElasticDataProvider,
    IFileDataProvider,
)
from eea.api.dataconnector.payload import canonical_form

# Set the default logging level to ERROR
log_level = os.environ.get("LOG_LEVEL", "ERROR")
numeric_log_level = getattr(logging, log_level, None)

if not isinstance(numeric_log_level, int):
    raise ValueError(f"Invalid log level: {log_level}")

# Create a logger and set its level
logger = logging.getLogger(__name__)
logger.setLevel(numeric_log_level)

# Create a console handler and set its level
handler = logging.StreamHandler()
handler.setLevel(numeric_log_level)

# Create a formatter and add it to the handler
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(handler)

_MISSING = object()


def _connector_data_cache_key(self, method, context_path, payload_hash):
    cache_key = (context_path, payload_hash)
    # cache_key = (context_path, payload_hash, _time() // 300)
    return cache_key


def _normalize_provider_data(data):
    """Return the public data shape expected by connector-data consumers."""
    if not isinstance(data, dict):
        return {"results": [], "metadata": {}}

    results = data.get("results")
    metadata = data.get("metadata")
    return {
        "results": results if isinstance(results, (dict, list)) and results else [],
        "metadata": metadata if isinstance(metadata, dict) else {},
    }


def _validate_virtual_connector_data(connector_data):
    """Validate the internal virtual-page preload envelope."""
    if not isinstance(connector_data, dict):
        raise ValueError("Virtual connector_data must be an object")

    if not isinstance(connector_data.get("@id"), str) or not connector_data["@id"]:
        raise ValueError("Virtual connector_data requires a non-empty @id")
    if not isinstance(connector_data.get("path"), str) or not connector_data["path"]:
        raise ValueError("Virtual connector_data requires a non-empty path")

    data = connector_data.get("data")
    if not isinstance(data, dict):
        raise ValueError("Virtual connector_data.data must be an object")
    if not isinstance(data.get("results"), (dict, list)):
        raise ValueError(
            "Virtual connector_data.data.results must be an object or array"
        )
    if not isinstance(data.get("metadata"), dict):
        raise ValueError("Virtual connector_data.data.metadata must be an object")

    payload = connector_data.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Virtual connector_data.payload must be an object")
    if not isinstance(payload.get("data_query"), list):
        raise ValueError("Virtual connector_data.payload.data_query must be an array")
    if not isinstance(payload.get("form"), dict):
        raise ValueError("Virtual connector_data.payload.form must be an object")

    return connector_data


def _get_virtual_connector_data(context):
    """Return an owned, validated preload only for a virtual context."""
    context = aq_base(context)
    if not bool(getattr(context, "is_virtual", False)):
        return None

    connector_data = getattr(context, "connector_data", _MISSING)
    if connector_data is _MISSING:
        return None
    return _validate_virtual_connector_data(connector_data)


def _provider_name(context):
    """Select the provider adapter without acquiring a parent file."""
    has_file = getattr(aq_base(context), "file", None) is not None
    is_file_provider = IFileDataProvider.providedBy(context)
    is_connector_provider = IConnectorDataProvider.providedBy(context)

    if is_file_provider and (has_file or not is_connector_provider):
        return "file"
    if is_connector_provider:
        return "connector"
    raise ComponentLookupError("No data provider found")


@implementer(IExpandableElement)
class ConnectorData:
    """connector data"""

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.body = None

    def _ensure_request_body(self):
        context_data_query = getattr(aq_base(self.context), "data_query", None)
        try:
            self.body = json_body(self.request)
        except Exception:
            self.body = {}
        if not self.body.get("data_query") and context_data_query is not None:
            self.body["data_query"] = context_data_query
        if not self.body.get("form"):
            self.body["form"] = {}
        self.request["BODY"] = json.dumps(self.body)

    def _payload(self):
        """Return the public request identity used for frontend preload reuse.

        Authentication belongs in headers or cookies and is intentionally not
        included in this response metadata.
        """
        return {
            "data_query": self.body.get("data_query", []),
            "form": canonical_form(
                self.request.form,
                self.body.get("form", {}),
            ),
        }

    def _payload_hash(self):
        return hashlib.md5(
            json.dumps(self._payload(), sort_keys=True).encode()
        ).hexdigest()

    @ram.cache(_connector_data_cache_key)
    def _expand_connector_data(self, context_path, payload_hash):
        name = _provider_name(self.context)
        connector = getMultiAdapter(
            (self.context, self.request), IDataProvider, name=name
        )
        return _normalize_provider_data(connector.provided_data)

    def __call__(self, expand=False):
        self._ensure_request_body()

        connector_data = _get_virtual_connector_data(self.context)
        if connector_data is not None:
            return {"connector-data": connector_data}

        is_virtual = bool(getattr(aq_base(self.context), "is_virtual", False))
        if is_virtual:
            path = aq_parent(aq_inner(self.context)).absolute_url()
        else:
            path = self.context.absolute_url()

        payload = self._payload()

        result = {
            "connector-data": {
                "@id": "{}/@connector-data".format(self.context.absolute_url()),
                "path": path,
                "data": {
                    "results": [],
                    "metadata": {},
                },
                "payload": payload,
            }
        }

        if not expand:
            return result

        context_path = "/".join(self.context.getPhysicalPath())
        payload_hash = self._payload_hash()
        result["connector-data"]["data"] = self._expand_connector_data(
            context_path, payload_hash
        )

        return result


@implementer(IExpandableElement)
@adapter(IElasticDataProvider, Interface)
class ElasticConnectorData:
    """Elastic connector data"""

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, expand=False):
        result = {
            "connector-data": {
                "@id": "{}/@connector-data".format(self.context.absolute_url())
            }
        }

        widget_data = getattr(self.context, "elastic_csv_widget", {})
        form_value = widget_data.get("formValue", {})
        req_config = widget_data.get("elasticQueryConfig", {})
        es_endpoint = req_config.get("es_endpoint")
        payload_config = req_config.get("payloadConfig")

        if not es_endpoint or not payload_config:
            return {"results": [], "metadata": {}}

        # Fetch data from Elasticsearch
        table_data = self._fetch_from_elasticsearch(
            es_endpoint, payload_config, form_value
        )

        result["connector-data"]["data"] = {
            "results": table_data,
            "metadata": {"readme": ""},
        }

        return result

    def _fetch_from_elasticsearch(self, url, payload, form_value):
        """
        Fetch data from Elasticsearch.

        Args:
        - url: The Elasticsearch endpoint URL.
        - payload: The payload to send with the request.
        - form_value: The form values.

        Returns:
        A dictionary containing the table data.
        """
        headers = {
            "Content-Type": "application/json",
        }
        response = {}

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()

            es_data = response.json()
            table_data = self._process_es_response(es_data, form_value)
            return table_data

        except requests.RequestException as e:
            logger.error("Error fetching data from Elasticsearch: %s", e)
            if response:
                logger.error("Response status code: %s", response.status_code)
                logger.error("Response content: %s", response.text)
            return {}

    def _process_es_response(self, es_data, form_value):
        """
        Process the Elasticsearch response.

        Args:
        - es_data: The data returned from Elasticsearch.
        - form_value: The form values.

        Returns:
        A dictionary containing the processed data.
        """
        use_aggs = form_value.get("use_aggs", False)
        agg_fields = form_value.get("agg_fields")
        fields = form_value.get("fields", [])

        table = {}
        if use_aggs:
            for agg_field in agg_fields:
                agg_data = (
                    es_data.get("aggregations", {})
                    .get(agg_field["field"], {})
                    .get("buckets", [])
                )
                if agg_data:
                    table.update(self._build_table_from_aggs(agg_data, agg_field))
        else:
            hits = es_data.get("hits", {}).get("hits", [])
            if hits and fields:
                table.update(self._build_table_from_fields(hits, fields))

        return table

    def _build_table_from_fields(self, items, fields):
        """
        Build a table from fields.

        Args:
        - items: The items to process.
        - fields: The fields to include in the table.

        Returns:
        A dictionary containing the table data.
        """
        table = {}
        for field_obj in fields:
            field_name = field_obj.get("field")
            table[field_name] = [
                item.get("_source", {}).get(field_name) for item in items
            ]
        return table

    def _build_table_from_aggs(self, data, field_obj):
        """
        Build a table from aggregations.

        Args:
        - data: The data to process.
        - field_obj: The field object containing field details.

        Returns:
            A dictionary containing the table data.
        """
        field_name = field_obj.get("field")
        field_label = field_obj.get("title", field_name) + " "

        values_column = "{}values".format(field_label)
        count_column = "{}total".format(field_label)

        table = {
            values_column: [],
            count_column: [],
        }

        for bucket in data:
            table[values_column].append(bucket.get("key"))
            table[count_column].append(bucket.get("doc_count"))

            # Handle second-level aggregation if specified
            second_level_agg = field_obj.get("secondLevelAgg")
            if second_level_agg:
                sub_buckets = bucket.get(second_level_agg, {}).get("buckets", [])
                for sub_bucket in sub_buckets:
                    sub_key = sub_bucket.get("key")

                    # If this subBucket's key hasn't been seen before
                    #  create a new column for it
                    if sub_key not in table:
                        table[sub_key] = [0] * (len(table[values_column]) - 1)

                    # Add the doc_count to the appropriate column
                    table[sub_key].append(sub_bucket.get("doc_count"))

                # Ensure all columns have the same length after each push to
                # the table
                # Filling in zeroes where necessary
                max_col_length = max(len(col) for col in table.values())
                for col_key, col in table.items():
                    if col_key in table and len(col) < max_col_length:
                        col.extend([0] * (max_col_length - len(col)))
        return table


def connector_data_response(context, request):
    """Return connector data or a 404 when the context has no data provider."""
    connector = queryMultiAdapter(
        (context, request),
        IExpandableElement,
        name="connector-data",
    )
    if connector is None:
        raise NotFound(context, "@connector-data", request)

    try:
        result = connector(expand=True)
    except ComponentLookupError as ex:
        raise NotFound(context, "@connector-data", request) from ex

    return result["connector-data"]


class ConnectorDataGet(Service):
    """connector data - get"""

    def reply(self):
        """reply"""
        return connector_data_response(self.context, self.request)


class ConnectorDataPost(Service):
    """connector data - post"""

    def reply(self):
        """reply"""
        return connector_data_response(self.context, self.request)
