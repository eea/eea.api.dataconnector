""" visualization module """
import re
from plone.restapi.interfaces import ISerializeToJson
from plone.restapi.services import Service
from zope.component import queryMultiAdapter
from eea.api.dataconnector.browser.blocks import getVisualization


class VisualizationGet(Service):
    """Get visualization data + layout"""

    def reply(self):
        """reply"""
        serializer = queryMultiAdapter(
            (self.context, self.request), ISerializeToJson
        )

        if serializer is None:
            self.request.response.setStatus(501)

            return dict(error=dict(message="No serializer available."))

        serializer = serializer(version=self.request.get("version"))

        res = {
            "@id": self.context.absolute_url() + "/@visualization",
            "visualization": getVisualization(
                serializer=serializer,
                layout=False
            )
        }

        return res


class VisualizationLayoutGet(Service):
    """Get visualization layout"""

    def reply(self):
        """reply"""
        serializer = queryMultiAdapter(
            (self.context, self.request), ISerializeToJson
        )

        if serializer is None:
            self.request.response.setStatus(501)

            return dict(error=dict(message="No serializer available."))

        serializer = serializer(version=self.request.get("version"))

        res = {
            "@id": self.context.absolute_url() + "/@visualization",
            "visualization": getVisualization(
                serializer=serializer
            )
        }

        return res
