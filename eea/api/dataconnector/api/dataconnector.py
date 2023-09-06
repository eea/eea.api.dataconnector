# -*- coding: utf-8 -*-
""" dataconnector """
from eea.api.dataconnector.interfaces import IBasicDataProvider
from eea.api.dataconnector.interfaces import IDataProvider
from eea.api.dataconnector.interfaces import IElasticDataProvider
from plone.restapi.interfaces import IExpandableElement
from plone.restapi.interfaces import ISerializeToJson
from plone.restapi.services import Service
from zope.component import adapter
from zope.component import getMultiAdapter
from zope.interface import implementer
from zope.interface import Interface
from zope.component import queryMultiAdapter


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


class ConnectorDataGet(Service):
    """connector data - get"""

    def reply(self):
        """reply"""
        result = ConnectorData(self.context, self.request)(expand=True)

        return result["connector-data"]


class ConnectorDataPost(Service):
    """connector data - post"""

    def reply(self):
        """reply"""
        result = ConnectorData(self.context, self.request)(expand=True)

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
