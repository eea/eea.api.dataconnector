""" visualization module """
import re
from plone.restapi.interfaces import ISerializeToJson
from plone.restapi.services import Service
from zope.component import queryMultiAdapter


def getVisualizationLayout(chartData):
    """Get visualization layout with no data"""
    if not chartData or not chartData.get("data"):
        return None

    newData = chartData.get("data")

    for traceIndex, trace in enumerate(newData):
        for tk in trace:
            originalColumn = re.sub("src$", "", tk)
            if tk.endswith("src") and originalColumn in trace:
                newData[traceIndex][originalColumn] = []
        if not trace.get("transforms"):
            continue
        for transformIndex, _ in enumerate(trace.get("transforms")):
            newData[traceIndex]["transforms"][transformIndex]["target"] = []

    chartData["data"] = newData

    return chartData


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

        ser = serializer(version=self.request.get("version"))

        visualization = ser.get("visualization", {})
        figure_note = ser.get("figure_note", {})
        chartData = visualization.get("chartData", {})
        provider_url = chartData.get("provider_url")

        del chartData["provider_url"]

        res = {
            "@id": self.context.absolute_url() + "/@visualization",
            "visualization": {
                "chartData": chartData,
                "provider_url": provider_url,
                "publisher": ser.get("publisher"),
                "geo_coverage": ser.get("geo_coverage"),
                "temporal_coverage": ser.get("temporal_coverage"),
                "other_organisations": ser.get("other_organisations"),
                "data_provenance": ser.get("data_provenance"),
                "figure_note": figure_note
            }
            if visualization
            else None,
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

        ser = serializer(version=self.request.get("version"))

        visualization = ser.get("visualization", {})
        figure_note = ser.get("figure_note", {})
        chartData = getVisualizationLayout(visualization.get("chartData", {}))
        provider_url = chartData.get("provider_url")

        del chartData["provider_url"]

        res = {
            "@id": self.context.absolute_url() + "/@visualization-layout",
            "visualization": {
                "chartData": chartData,
                "provider_url": provider_url,
                "publisher": ser.get("publisher"),
                "geo_coverage": ser.get("geo_coverage"),
                "temporal_coverage": ser.get("temporal_coverage"),
                "other_organisations": ser.get("other_organisations"),
                "data_provenance": ser.get("data_provenance"),
                "figure_note": figure_note

            }
            if visualization
            else None,
        }

        return res
