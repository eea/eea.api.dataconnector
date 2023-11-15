""" block-related utils """

import re
from plone import api
from plone.app.uuid.utils import uuidToCatalogBrain
from plone.restapi.behaviors import IBlocks
from plone.restapi.interfaces import ISerializeToJson
from plone.restapi.interfaces import IBlockFieldSerializationTransformer
from plone.restapi.interfaces import IBlockFieldDeserializationTransformer
from plone.restapi.deserializer.utils import path2uid
from plone.restapi.serializer.utils import uid_to_url, RESOLVEUID_RE
from zope.component import adapter
from zope.component import queryMultiAdapter
from zope.interface import implementer
from zope.publisher.interfaces.browser import IBrowserRequest


def getUid(context, link, retry=True):
    if not link:
        return link
    match = RESOLVEUID_RE.match(link)
    if match is None:
        if not retry:
            return link
        return getUid(context, path2uid(context=context, link=link), False)
    else:
        uid, suffix = match.groups()
        return uid


def getMetadata(serializer):
    return {
        "@id": serializer.get("@id"),
        "title": serializer.get("title"),
        "publisher": serializer.get("publisher"),
        "geo_coverage": serializer.get("geo_coverage"),
        "temporal_coverage": serializer.get("temporal_coverage"),
        "other_organisations": serializer.get("other_organisations"),
        "data_provenance": serializer.get("data_provenance"),
        "figure_note": serializer.get("figure_note"),
    }


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


def getVisualization(serializer, layout=True):
    visualization = serializer.get("visualization", {})
    chartData = visualization.get("chartData", {})
    provider_url = chartData.get("provider_url")

    if layout:
        chartData = getVisualizationLayout(chartData)

    if (chartData):
        del chartData["provider_url"]

    if not (visualization):
        return None

    return {
        "chartData": chartData,
        "provider_url": provider_url
    }


@implementer(IBlockFieldSerializationTransformer)
@adapter(IBlocks, IBrowserRequest)
class EmbedVisualizationSerializationTransformer(object):
    """Embed visualization serialization"""

    order = 9999
    block_type = "embed_visualization"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        uid = getUid(self.context, value.get('vis_url'))
        if not uid:
            return value
        doc = api.content.get(UID=uid)
        doc_serializer = queryMultiAdapter(
            (doc, self.request),
            ISerializeToJson
        ) if doc else None
        if (doc_serializer):
            doc_serializer = doc_serializer(
                version=self.request.get("version"))
            use_live_data = value.get('use_live_data', True)
            return {
                **value,  # this is a spread operator - for js devs
                "visualization": {
                    **getMetadata(doc_serializer),
                    **doc_serializer.get('visualization'),
                    **getVisualization(
                        serializer=doc_serializer,
                        layout=(False if not (use_live_data) else True)
                    ),
                }
            }
        return value


@implementer(IBlockFieldDeserializationTransformer)
@adapter(IBlocks, IBrowserRequest)
class EmbedVisualizationDeserializationTransformer(object):
    """Embed visualization deserialization"""

    order = 9999
    block_type = "embed_visualization"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        if value.get('vis_url'):
            value['vis_url'] = path2uid(
                context=self.context, link=value['vis_url'])
        return value


@implementer(IBlockFieldSerializationTransformer)
@adapter(IBlocks, IBrowserRequest)
class EmbedMapsSerializationTransformer(object):
    """Embed maps serializer"""

    order = 9999
    block_type = "embed_maps"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        uid = getUid(self.context, value.get('url'))
        if not uid:
            return value
        doc = api.content.get(UID=uid)
        doc_serializer = queryMultiAdapter(
            (doc, self.request),
            ISerializeToJson
        ) if doc else None
        if (doc_serializer):
            doc_serializer = doc_serializer(
                version=self.request.get("version"))
            return {
                **value,
                "maps": {
                    **getMetadata(doc_serializer),
                    **doc_serializer.get('maps'),
                }
            }
        return value


@implementer(IBlockFieldSerializationTransformer)
@adapter(IBlocks, IBrowserRequest)
class PlotlyChartSerializationTransformer(object):
    """Plotly chart serializer"""

    order = 100
    block_type = "plotly_chart"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    # def transform(self, value):
    #     # if value.get("visualization", {}).get("provider_url"):
    #     #     value["visualization"]["provider_url"] = self.url_to_path(
    #     #         value["visualization"]["provider_url"]
    #     #     )
    #     return value

    def __call__(self, value):
        if value.get("use_live_data", True):
            newData = (
                value.get("visualization", {})
                .get("chartData", {})
                .get("data", None)
            )
            if not newData:
                return value
            for traceIndex, trace in enumerate(newData):
                for tk in trace:
                    originalColumn = re.sub("src$", "", tk)
                    if tk.endswith("src") and originalColumn in trace:
                        newData[traceIndex][originalColumn] = []
                if not trace.get("transforms"):
                    continue
                for transformIndex, _ in enumerate(trace.get("transforms")):
                    newData[traceIndex]["transforms"][transformIndex][
                        "target"
                    ] = []
            value["visualization"]["chartData"]["data"] = newData

        return value
