# -*- coding: utf-8 -*-
""" dataconnector """
import logging
import os
import requests
# eea imports
from eea.api.dataconnector.interfaces import IBasicDataProvider
from eea.api.dataconnector.interfaces import IDataProvider
from eea.api.dataconnector.interfaces import IElasticDataProvider

# plone imports
from plone.restapi.interfaces import IExpandableElement
from plone.restapi.services import Service

# zope imports
from zope.component import adapter
from zope.component import getMultiAdapter
from zope.interface.interfaces import ComponentLookupError
from zope.interface import implementer
from zope.interface import Interface

# Set the default logging level to ERROR
log_level = os.environ.get('LOG_LEVEL', 'ERROR')
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
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(handler)


@implementer(IExpandableElement)
@adapter(IBasicDataProvider, Interface)
class ConnectorData:
    """connector data"""

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, expand=False):
        result = {
            "connector-data": {
                "@id": "{}/@connector-data".format(self.context.absolute_url())
            }
        }

        if not expand:
            return result

        connector = getMultiAdapter(
            (self.context, self.request), IDataProvider)
        result["connector-data"]["data"] = connector.provided_data

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
                    table.update(self._build_table_from_aggs(
                        agg_data, agg_field))
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
                sub_buckets = bucket.get(
                    second_level_agg, {}).get("buckets", [])
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
                        col.extend([0] * (
                            max_col_length - len(col)))
        return table


class ConnectorDataGet(Service):
    """connector data - get"""

    def reply(self):
        """reply"""
        try:
            connector = getMultiAdapter(
                (self.context, self.request), name="connector-data"
            )
            result = connector(expand=True)

            return result["connector-data"]
        except ComponentLookupError as ex:
            raise ValueError(
                "No suitable connector found for the context.") from ex


class ConnectorDataPost(Service):
    """connector data - post"""

    def reply(self):
        """reply"""
        connector = getMultiAdapter(
            (self.context, self.request), name="connector-data")
        result = connector(expand=True)

        return result["connector-data"]
