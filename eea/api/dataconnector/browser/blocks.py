""" block-related utils """

import re
from urllib.parse import urlparse
from AccessControl import Unauthorized
from plone import api
from plone.restapi.behaviors import IBlocks
from plone.restapi.interfaces import ISerializeToJson
from plone.restapi.interfaces import IBlockFieldSerializationTransformer
from plone.restapi.interfaces import IBlockFieldDeserializationTransformer
from plone.restapi.deserializer.utils import path2uid
from plone.restapi.serializer.utils import RESOLVEUID_RE, uid_to_url
from zExceptions import Forbidden
from zope.component import adapter
from zope.component import queryMultiAdapter
from zope.interface import implementer
from zope.publisher.interfaces.browser import IBrowserRequest


def getLinkHTML(url, text=None):
    """
      Get link HTML
      """

    if not url:
        return url

    if not text:
        text = url

    return '<a href="' + url + '" target="_blank">' + text + '</a>'


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
        return getUid(context, path2uid(context=context, link=getLink(link)),
                      False)

    uid, _ = match.groups()
    return uid


def getUrlUid(self, value, field):
    """
    Get URL and UID based on the provided value and field.

    :param value: The input value.
    :param field: The field to extract the URL from in the value.

    :return: A tuple containing the URL and UID.
    """

    url = value.get(field)
    uid = getUid(self.context, url)
    url = uid_to_url(url)
    return url, uid


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
        "description": serializer.get("description"),
        "publisher": serializer.get("publisher"),
        "geo_coverage": serializer.get("geo_coverage"),
        "temporal_coverage": serializer.get("temporal_coverage"),
        "other_organisations": serializer.get("other_organisations"),
        "data_provenance": serializer.get("data_provenance"),
        "figure_note": serializer.get("figure_note")
    }


def getVisualizationLayout(chartData):
    """Get visualization layout with no data"""
    if not chartData or not chartData.get("data"):
        return {}

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

    visualization = serializer.get("visualization", None)

    if not visualization:
        return {}

    chartData = visualization.get("chartData", {})
    provider_url = visualization.get("provider_url", None)
    use_data_sources = visualization.get("use_data_sources", layout)
    filters = visualization.get("filters", None)
    variation = visualization.get("variation", None)

    if use_data_sources:
        chartData = getVisualizationLayout(chartData)

    response = {
        "chartData": {
            "data": chartData.get("data", []),
            "layout": chartData.get("layout", {}),
            "frames": chartData.get("frames", [])
        },
        "use_data_sources": use_data_sources,
        "filters": filters,
        "variation": variation
    }

    if use_data_sources and provider_url:
        response["provider_url"] = provider_url

    if use_data_sources and "data_source" in visualization:
        response["data_source"] = visualization.get("data_source")

    return response


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
        vis_url, uid = getUrlUid(self, value, 'vis_url')

        if 'visualization' in value:
            del value['visualization']

        if not uid:
            return value

        doc = None

        try:
            doc = api.content.get(UID=uid)
        except Unauthorized:
            return {
                **value, "vis_url": vis_url,
                "visualization": {
                    "error":
                    "Apologies, it seems this " +
                    getLinkHTML(vis_url, 'Chart (Interactive)') +
                    " has not been published yet."
                }
            }
        except Forbidden:
            return {
                **value, "vis_url": vis_url,
                "visualization": {
                    "error":
                    "Apologies, it seems you do not have " +
                    "permissions to see this " +
                    getLinkHTML(vis_url, 'Chart (Interactive)') + "."
                }
            }

        doc_serializer = self._get_doc_serializer(doc)
        if doc_serializer:
            use_data_sources = value.get('use_data_sources', True)

            return {
                **value, "vis_url": vis_url,
                "visualization": {
                    **getVisualization(serializer=doc_serializer,
                                       layout=use_data_sources),
                    **getMetadata(doc_serializer),
                }
            }
        return {**value, "vis_url": uid_to_url(value.get('vis_url'))}

    def _get_doc_serializer(self, doc):
        """
        Get a serializer for the given document.

        This method queries for a JSON serializer adapter for the provided
        document and request. If a serializer is found, it is instantiated
        with the version from the request and returned.

        :param doc: The document for which to get a serializer.
        :type doc: object

        :return: An instantiated JSON serializer if available, or None if
                 not found.
        :rtype: object or None
        """
        if doc:
            doc_serializer = queryMultiAdapter(
                (doc, self.request), ISerializeToJson)
            if doc_serializer:
                return doc_serializer(
                    version=self.request.get("version"))
        return None


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
        if 'visualization' in value:
            del value['visualization']
        if 'vis_url' in value:
            value['vis_url'] = path2uid(context=self.context,
                                        link=getLink(value['vis_url']))
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
        tableau_vis_url, uid = getUrlUid(self, value, 'tableau_vis_url')

        if 'tableau_visualization' in value:
            del value['tableau_visualization']

        if not uid:
            return value

        doc = None

        try:
            doc = api.content.get(UID=uid)
        except Unauthorized:
            return {
                **value, "tableau_vis_url": tableau_vis_url,
                "tableau_visualization": {
                    "error":
                    "Apologies, it seems this " +
                    getLinkHTML(tableau_vis_url, 'Dashboard') +
                    " has not been published yet."
                }
            }
        except Forbidden:
            return {
                **value, "tableau_vis_url": tableau_vis_url,
                "tableau_visualization": {
                    "error":
                    "Apologies, it seems you do not have " +
                    "permissions to see this " +
                    getLinkHTML(tableau_vis_url, 'Dashboard') + "."
                }
            }

        doc_serializer = self._get_doc_serializer(doc)
        if doc_serializer:
            return {
                **value, "tableau_vis_url": tableau_vis_url,
                "tableau_visualization": {
                    **doc_serializer.get('tableau_visualization', {}),
                    **getMetadata(doc_serializer),
                }
            }
        return {
            **value,
            "tableau_vis_url": tableau_vis_url,
        }

    def _get_doc_serializer(self, doc):
        """
        Get a serializer for the given document.

        This method queries for a JSON serializer adapter for the provided
        document and request. If a serializer is found, it is instantiated
        with the version from the request and returned.

        :param doc: The document for which to get a serializer.
        :type doc: object

        :return: An instantiated JSON serializer if available, or None if
                 not found.
        :rtype: object or None
        """
        if doc:
            doc_serializer = queryMultiAdapter(
                (doc, self.request), ISerializeToJson)
            if doc_serializer:
                return doc_serializer(
                    version=self.request.get("version"))
        return None


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
        if 'tableau_visualization' in value:
            del value['tableau_visualization']
        if 'tableau_vis_url' in value:
            value['tableau_vis_url'] = path2uid(context=self.context,
                                                link=value['tableau_vis_url'])
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
        vis_url, uid = getUrlUid(self, value, 'vis_url')

        if 'map_visualization_data' in value:
            del value['map_visualization_data']

        if not uid:
            return value

        doc = None

        try:
            doc = api.content.get(UID=uid)
        except Unauthorized:
            return {
                **value, "tableau_vis_url": vis_url,
                "map_visualization_data": {
                    "error":
                    "Apologies, it seems this " +
                    getLinkHTML(vis_url, 'Map (Simple)') +
                    " has not been published yet."
                }
            }
        except Forbidden:
            return {
                **value, "tableau_vis_url": vis_url,
                "map_visualization_data": {
                    "error":
                    "Apologies, it seems you do not have " +
                    "permissions to see this " +
                    getLinkHTML(vis_url, 'Map (Simple)') + "."
                }
            }

        doc_serializer = self._get_doc_serializer(doc)
        if doc_serializer:
            return {
                **value, "vis_url": vis_url,
                "map_visualization_data": {
                    **doc_serializer.get('map_visualization_data', {}),
                    **getMetadata(doc_serializer),
                }
            }
        return {
            **value,
            "vis_url": vis_url,
        }

    def _get_doc_serializer(self, doc):
        """
        Get a serializer for the given document.

        This method queries for a JSON serializer adapter for the provided
        document and request. If a serializer is found, it is instantiated
        with the version from the request and returned.

        :param doc: The document for which to get a serializer.
        :type doc: object

        :return: An instantiated JSON serializer if available, or None if
                 not found.
        :rtype: object or None
        """
        if doc:
            doc_serializer = queryMultiAdapter(
                (doc, self.request), ISerializeToJson)
            if doc_serializer:
                return doc_serializer(
                    version=self.request.get("version"))
        return None


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
        if 'map_visualization_data' in value:
            del value['map_visualization_data']
        if 'vis_url' in value:
            value['vis_url'] = path2uid(context=self.context,
                                        link=value['vis_url'])
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
        url, uid = getUrlUid(self, value, 'url')

        if 'maps' in value:
            del value['maps']

        if not uid:
            return value

        try:
            doc = api.content.get(UID=uid)
        except Unauthorized:
            return {
                **value, "maps": {
                    "error":
                    "Apologies, it seems this " +
                    getLinkHTML(url, 'Map (Interactive)') +
                    " has not been published yet."
                }
            }
        except Forbidden:
            return {
                **value, "maps": {
                    "error":
                    "Apologies, it seems you do not have " +
                    "permissions to see this " +
                    getLinkHTML(url, 'Map (Interactive)') + "."
                }
            }

        doc_serializer = self._get_doc_serializer(doc)
        if doc_serializer:
            return {
                **value, "maps": {
                    **doc_serializer.get('maps', {}),
                    **getMetadata(doc_serializer),
                }
            }
        return value

    def _get_doc_serializer(self, doc):
        """
        Get a serializer for the given document.

        This method queries for a JSON serializer adapter for the provided
        document and request. If a serializer is found, it is instantiated
        with the version from the request and returned.

        :param doc: The document for which to get a serializer.
        :type doc: object

        :return: An instantiated JSON serializer if available, or None if
                 not found.
        :rtype: object or None
        """
        if doc:
            doc_serializer = queryMultiAdapter(
                (doc, self.request), ISerializeToJson)
            if doc_serializer:
                return doc_serializer(
                    version=self.request.get("version"))
        return None


@implementer(IBlockFieldDeserializationTransformer)
@adapter(IBlocks, IBrowserRequest)
class EmbedMapsDeserializationTransformer:
    """Embed maps deserialization"""

    order = 9999
    block_type = "embed_maps"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        if 'maps' in value:
            del value['maps']
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
        if value.get("use_data_sources", True):
            newData = (value.get("visualization",
                                 {}).get("chartData", {}).get("data", None))
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
                        "target"] = []
            value["visualization"]["chartData"]["data"] = newData

        return value
