# -*- coding: utf-8 -*-
""" dataconnector """
# eea imports
import logging
import requests
from eea.api.dataconnector.interfaces import IBasicDataProvider
from eea.api.dataconnector.interfaces import IDataProvider
from eea.api.dataconnector.interfaces import IElasticDataProvider

# plone imports
from plone.restapi.interfaces import IExpandableElement
from plone.restapi.interfaces import ISerializeToJson
from plone.restapi.services import Service

# zope imports
from zope.component import adapter
from zope.component import getMultiAdapter
from zope.component import queryMultiAdapter
from zope.component.interfaces import ComponentLookupError
from zope.interface import implementer
from zope.interface import Interface


logging.basicConfig(level=logging.ERROR)  # This will log only errors and above
logger = logging.getLogger(__name__)


@implementer(IExpandableElement)
@adapter(IBasicDataProvider, Interface)
class ConnectorData(object):
    """connector data"""

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, expand=False):
        result = {
            "connector-data": {
                "@id": "{}/@connector-data".format(
                    self.context.absolute_url()
                )
            }
        }

        if not expand:
            return result

        connector = getMultiAdapter(
            (self.context, self.request), IDataProvider
        )
        result["connector-data"]["data"] = connector.provided_data

        return result


@implementer(IExpandableElement)
@adapter(IElasticDataProvider, Interface)
class ElasticConnectorData(object):
    """ Elastic connector data """

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, expand=False):
        result = {
            "connector-data": {
                "@id": "{}/@connector-data".format(
                    self.context.absolute_url()
                )
            }
        }

        widgetData = getattr(self.context, 'elastic_csv_widget', {})
        formValue = widgetData.get('formValue', {})
        reqConfig = widgetData.get('elasticQueryConfig', {})
        es_endpoint = reqConfig.get('es_endpoint')
        payloadConfig = reqConfig.get('payloadConfig')

        if not es_endpoint or not payloadConfig:
            return {"results": [], "metadata": {}}

        # Fetch data from Elasticsearch
        table_data = self._fetch_from_elasticsearch(
            es_endpoint, payloadConfig, formValue)

        result["connector-data"]["data"] = {"results": table_data,
                                            "metadata": {"readme": ""}}

        return result

    def _fetch_from_elasticsearch(self, url, payload, formValue):
        """
        Fetch data from Elasticsearch.

        Args:
        - url: The Elasticsearch endpoint URL.
        - payload: The payload to send with the request.
        - formValue: The form values.

        Returns:
        A dictionary containing the table data.
        """
        headers = {
            'Content-Type': 'application/json',
        }
        try:
            response = requests.post(
                url, json=payload, headers=headers)
            response.raise_for_status()

            es_data = response.json()
            table_data = self._process_es_response(es_data, formValue)
            return table_data

        except requests.RequestException as e:
            logger.error("Error fetching data from Elasticsearch: %s", e)
            if response:
                logger.error("Response status code: %s", response.status_code)
                logger.error("Response content: %s", response.text)
            return {}

    def _process_es_response(self, es_data, formValue):
        """
        Process the Elasticsearch response.

        Args:
        - es_data: The data returned from Elasticsearch.
        - formValue: The form values.

        Returns:
        A dictionary containing the processed data.
        """
        use_aggs = formValue.get('use_aggs', False)
        agg_field = formValue.get('agg_field')
        fields = formValue.get('fields', [])

        if use_aggs and agg_field:
            aggBuckets = es_data.get('aggregations', {}).get(
                agg_field, {}).get('buckets', [])
            if aggBuckets:
                return self._build_table_from_aggs(aggBuckets, agg_field)
        else:
            hits = es_data.get('hits', {}).get('hits', [])
            if hits and fields:
                return self._build_table_from_fields(hits, fields)

        return {}

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
        for fieldObj in fields:
            fieldName = fieldObj.get('field')
            table[fieldName] = [item.get('_source', {}).get(fieldName)
                                for item in items]
        return table

    def _build_table_from_aggs(self, data, fieldName):
        """
        Build a table from aggregations.

        Args:
        - data: The data to process.
        - fieldName: The field name to use for aggregations.

        Returns:
        A dictionary containing the table data.
        """
        valuesColumn = f"{fieldName}_values"
        countColumn = f"{fieldName}_count"

        table = {
            valuesColumn: [],
            countColumn: [],
        }

        for bucket in data:
            table[valuesColumn].append(bucket.get('key'))
            table[countColumn].append(bucket.get('doc_count'))

        return table


class ConnectorDataGet(Service):
    """connector data - get"""

    def reply(self):
        """reply"""
        try:
            # using the getMultiAdapter to switch
            # between the 2 IExpandableElements
            connector = getMultiAdapter(
                (self.context, self.request), IExpandableElement
            )
            result = connector(expand=True)

            return result["connector-data"]
        except ComponentLookupError:
            raise ValueError("No suitable connector found for the context.")


class ConnectorDataPost(Service):
    """connector data - post"""

    def reply(self):
        """reply"""
        # using the getMultiAdapter to switch between
        # the 2 IExpandableElements
        result = getMultiAdapter(
            (self.context, self.request), IExpandableElement
        )(expand=True)

        return result["connector-data"]


class MapVisualizationGet(Service):
    """Get map visualization data"""

    def reply(self):
        """reply"""

        res = {
            "@id": self.context.absolute_url(),
            "map_visualization": {},
        }

        serializer = queryMultiAdapter(
            (self.context, self.request), ISerializeToJson
        )

        if serializer is None:
            self.request.response.setStatus(501)

            return dict(error=dict(message="No serializer available."))

        ser = serializer(version=self.request.get("version"))
        res["map_visualization"] = {
            "data": ser["map_visualization_data"],
            "data_provenance": ser["data_provenance"],
        }

        return res


class TableauVisualizationGet(Service):
    """Get tableau visualization data"""

    def reply(self):
        """reply"""

        res = {
            "@id": self.context.absolute_url(),
            "tableau_visualization": {},
        }

        serializer = queryMultiAdapter(
            (self.context, self.request), ISerializeToJson
        )

        if serializer is None:
            self.request.response.setStatus(501)

            return dict(error=dict(message="No serializer available."))

        ser = serializer(version=self.request.get("version"))
        res["tableau_visualization"] = {
            "data": ser["tableau_visualization"],
            "data_provenance": ser["data_provenance"],
        }

        return res
