""" block-related utils """

import re
from urllib.parse import urlparse
from plone import api
from plone.restapi.behaviors import IBlocks
from plone.restapi.interfaces import ISerializeToJson
from plone.restapi.interfaces import IBlockFieldSerializationTransformer
from plone.restapi.interfaces import IBlockFieldDeserializationTransformer
from plone.restapi.deserializer.utils import path2uid
from plone.restapi.serializer.utils import RESOLVEUID_RE, uid_to_url
from zope.component import adapter
from zope.component import queryMultiAdapter
from zope.interface import implementer
from zope.publisher.interfaces.browser import IBrowserRequest


def getLink(path):
    """
    Get link
    """

    URL = urlparse(path)

    if URL.netloc.startswith('localhost') and URL.scheme:
        return path.replace(URL.scheme + "://" + URL.netloc, "")
    return path


def getUid(context, link, retry=True):
    """
    Get the UID corresponding to a given link.

    Parameters:
    - context: The context or object providing the link.
    - link (str): The link for which to retrieve the UID.
    - retry (bool, optional): If True, attempt to resolve the UID
      even if the initial attempt fails. Defaults to True.

    Returns:
    - str or None: The UID corresponding to the provided link,
      or None if the link is empty or cannot be resolved.

    If the link is empty, the function returns the link itself.
    If the link cannot be resolved in the initial attempt and retry
    is True, the function retries resolving the link by calling itself
    with retry set to False.

    The function uses the RESOLVEUID_RE regular expression to match
    and extract the UID from the link.
    """

    if not link:
        return link
    match = RESOLVEUID_RE.match(link)
    if match is None:
        if not retry:
            return link
        # Alin Voinea a zis sa las asa
        return getUid(
            context,
            path2uid(
                context=context, link=getLink(link)),
            False)

    uid, _ = match.groups()
    return uid


def getMetadata(serializer):
    """
    Extract metadata information from a serializer.

    Parameters:
    - serializer: The serializer providing metadata information.

    Returns:
    - dict: A dictionary containing metadata information with
    the following keys:
      - "@id": The identifier.
      - "title": The title.
      - "publisher": The publisher.
      - "geo_coverage": The geographic coverage.
      - "temporal_coverage": The temporal coverage.
      - "other_organisations": Other organizations involved.
      - "data_provenance": Data provenance information.
      - "figure_note": Additional notes related to the figure.

    The function retrieves metadata information from the provided
    serializer and returns it as a dictionary. If a specific metadata
    field is not present in the serializer, the corresponding key in
    the dictionary will have a value of None.
    """

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
    """
    Extract visualization information from a serializer.

    Parameters:
    - serializer: The serializer providing visualization information.
    - layout (bool, optional): If True, apply layout adjustments to the
      visualization data. Defaults to True.

    Returns:
    - dict or None: A dictionary containing visualization information
    with the following keys:
      - "chartData": The chart data.
      - "provider_url": The provider URL.
      Returns None if the visualization information is not present.

    The function retrieves visualization information from the provided
    serializer, including chart data and provider URL. If layout is set
    to True (default), it applies layout adjustments to the chart data using
    the getVisualizationLayout function.
    If visualization information is not present, the function returns None.
    """

    visualization = serializer.get("visualization", {})
    chartData = visualization.get("chartData", {})
    provider_url = chartData.get("provider_url")

    if layout:
        chartData = getVisualizationLayout(chartData)

    if chartData and "provider_url" in chartData:
        del chartData["provider_url"]

    if not visualization:
        return None

    return {
        "chartData": chartData,
        "provider_url": provider_url
    }


@implementer(IBlockFieldSerializationTransformer)
@adapter(IBlocks, IBrowserRequest)
class EmbedVisualizationSerializationTransformer:
    """Embed visualization serialization"""

    order = 9999
    block_type = "embed_visualization"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        uid = getUid(self.context, value.get('vis_url'))

        if 'visualization' in value:
            del value['visualization']

        if not uid:
            return value
        doc = api.content.get(UID=uid)
        doc_serializer = queryMultiAdapter(
            (doc, self.request),
            ISerializeToJson
        ) if doc else None
        if doc_serializer:
            doc_serializer = doc_serializer(
                version=self.request.get("version"))
            use_live_data = value.get('use_live_data', True)

            return {
                **value,
                "vis_url":  uid_to_url(value.get('vis_url')),
                "visualization": {
                    **getMetadata(doc_serializer),
                    **doc_serializer.get('visualization'),
                    **getVisualization(
                        serializer=doc_serializer,
                        layout=use_live_data
                    ),
                }
            }
        return {
            **value,
            "vis_url":  uid_to_url(value.get('vis_url'))
        }


@implementer(IBlockFieldDeserializationTransformer)
@adapter(IBlocks, IBrowserRequest)
class EmbedVisualizationDeserializationTransformer:
    """Embed visualization deserialization"""

    order = 9999
    block_type = "embed_visualization"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        if 'vis_url' in value:
            value['vis_url'] = path2uid(
                context=self.context, link=getLink(value['vis_url']))
        return value


@implementer(IBlockFieldSerializationTransformer)
@adapter(IBlocks, IBrowserRequest)
class EmbedTableauVisualizationSerializationTransformer:
    """Embed tableau visualization serialization"""

    order = 9999
    block_type = "embed_tableau_visualization"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        tableau_vis_url = value.get('tableau_vis_url')
        uid = getUid(self.context, tableau_vis_url)

        if 'tableau_visualization' in value:
            del value['tableau_visualization']

        if not uid:
            return value

        doc = api.content.get(UID=uid)
        doc_serializer = queryMultiAdapter(
            (doc, self.request),
            ISerializeToJson
        ) if doc else None
        if doc_serializer:
            doc_serializer = doc_serializer(
                version=self.request.get("version"))
            return {
                **value,
                "tableau_vis_url":  uid_to_url(tableau_vis_url),
                "tableau_visualization": {
                    **getMetadata(doc_serializer),
                    **doc_serializer.get('tableau_visualization'),
                }
            }
        return {
            **value,
            "tableau_vis_url":  uid_to_url(tableau_vis_url),
        }


@implementer(IBlockFieldDeserializationTransformer)
@adapter(IBlocks, IBrowserRequest)
class EmbedTableauVisualizationDeserializationTransformer:
    """Embed Tableau visualization deserialization"""

    order = 9999
    block_type = "embed_tableau_visualization"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        if 'tableau_vis_url' in value:
            value['tableau_vis_url'] = path2uid(
                context=self.context, link=value['tableau_vis_url'])
        return value


@implementer(IBlockFieldSerializationTransformer)
@adapter(IBlocks, IBrowserRequest)
class EmbedEEAMapBlockSerializationTransformer:
    """Embed eea map block serializer"""

    order = 9999
    block_type = "embed_eea_map_block"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        vis_url = value.get('vis_url')
        uid = getUid(self.context, vis_url)

        if 'map_visualization_data' in value:
            del value['map_visualization_data']

        if not uid:
            return value

        doc = api.content.get(UID=uid)
        doc_serializer = queryMultiAdapter(
            (doc, self.request),
            ISerializeToJson
        ) if doc else None
        if doc_serializer:
            doc_serializer = doc_serializer(
                version=self.request.get("version"))
            return {
                **value,
                "vis_url":  uid_to_url(vis_url),
                "map_visualization_data": {
                    **getMetadata(doc_serializer),
                    **doc_serializer.get('map_visualization_data'),
                }
            }
        return {
            **value,
            "vis_url":  uid_to_url(vis_url),
        }


@implementer(IBlockFieldDeserializationTransformer)
@adapter(IBlocks, IBrowserRequest)
class EmbedEEAMapBlockDeserializationTransformer:
    """Embed eea map block deserialization"""

    order = 9999
    block_type = "embed_eea_map_block"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        if 'vis_url' in value:
            value['vis_url'] = path2uid(
                context=self.context, link=value['vis_url'])
        return value


@implementer(IBlockFieldSerializationTransformer)
@adapter(IBlocks, IBrowserRequest)
class EmbedMapsSerializationTransformer:
    """Embed maps serializer"""

    order = 9999
    block_type = "embed_maps"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        uid = getUid(self.context, value.get('url'))

        if 'maps' in value:
            del value['maps']

        if not uid:
            return value

        doc = api.content.get(UID=uid)
        doc_serializer = queryMultiAdapter(
            (doc, self.request),
            ISerializeToJson
        ) if doc else None
        if doc_serializer:
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
class PlotlyChartSerializationTransformer:
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
