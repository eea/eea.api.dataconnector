""" visualization module """
from plone.restapi.interfaces import ISerializeToJson
from plone.restapi.services import Service
from zope.component import queryMultiAdapter
from eea.api.dataconnector.browser.blocks import getMetadata, getVisualization


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

        return {
            "visualization": {
                **getMetadata(serializer=serializer),
                **getVisualization(
                    serializer=serializer,
                    layout=False
                )
            }
        }


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

        return {
            "visualization": {
                **getMetadata(serializer=serializer),
                **getVisualization(
                    serializer=serializer
                )
            }
        }
