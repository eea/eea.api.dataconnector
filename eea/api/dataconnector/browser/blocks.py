""" block-related utils """

from urllib.parse import urlparse
from AccessControl import Unauthorized
from plone import api
from plone.restapi.blocks import iter_block_transform_handlers
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


def getMetadata(doc_json):
    """
      Extract metadata information from a doc_json.

      Parameters:
      - doc_json: The doc_json providing metadata information.

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
      doc_json and returns it as a dictionary. If a specific metadata
      field is not present in the doc_json, the corresponding key in
      the dictionary will have a value of None.
      """

    return {
        "@id": doc_json.get("@id"),
        "title": doc_json.get("title"),
        "description": doc_json.get("description"),
        "publisher": doc_json.get("publisher"),
        "geo_coverage": doc_json.get("geo_coverage"),
        "temporal_coverage": doc_json.get("temporal_coverage"),
        "other_organisations": doc_json.get("other_organisations"),
        "data_provenance": doc_json.get("data_provenance"),
        "figure_note": doc_json.get("figure_note")
    }


@implementer(IBlockFieldSerializationTransformer)
@adapter(IBlocks, IBrowserRequest)
class EmbedingBlockSerializationTransformer:
    """Embeding block serialization"""

    order = 9999
    block_type = "unknown"
    title = 'content'
    state = {}
    error = None
    initialized = False

    def __call__(self, value):
        return value

    def init(self, value):
        """Init"""
        self.state = {}
        self.initialized = True
        url = self.get_url(value)

        if not url:
            return

        self.state["url"] = url
        self.state["uid"] = getUid(self.context, self.state["url"])
        self.state["doc"] = self.get_doc()
        self.state["doc_json"] = self.get_doc_json()

        if not self.state["doc_json"]:
            return

        self.state["properties"] = {
            **getMetadata(self.state["doc_json"]),
            "@type": self.state["doc_json"].get("@type"),
            "UID": self.state["doc_json"].get("UID")
        }

    def get_url(self, value):
        """Get url"""
        if not value:
            return None
        return (
            value.get("url") or
            value.get("vis_url") or
            value.get("tableau_vis_url")
        )

    def get_doc(self):
        """Get doc"""
        url = self.state["url"]
        uid = self.state["uid"]
        try:
            return api.content.get(UID=uid)
        except Unauthorized:
            self.error = "Apologies, it seems this " + getLinkHTML(
                url, self.title) + " has not been published yet."
            return None

        except Forbidden:
            self.error = "Apologies, it seems you do not have " + \
                "permissions to see this " + getLinkHTML(url, self.title) + \
                "."
            return None

    def get_doc_json(self):
        """Get document json"""
        doc = self.state["doc"]
        if not doc:
            return None
        serializer = queryMultiAdapter(
            (doc, self.request), ISerializeToJson)
        if not serializer:
            return None
        return serializer(
            version=self.request.get("version"))

    def get_error(self):
        """Get error"""


class EmbedContentSerializationTransformer(
        EmbedingBlockSerializationTransformer):
    """Embed content serialization"""

    block_type = "embed_content"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        if not self.initialized:
            self.init(value)

        url = self.state.get("url")
        doc_json = self.state.get("doc_json")

        if not url:
            return value

        if self.error:
            return {
                **value,
                "error": self.error
            }

        if not doc_json:
            return {
                **value,
                "error": "Apologies, it seems this " + getLinkHTML(
                    url, self.title) + " does not exist."
            }

        value["properties"] = self.state["properties"]

        content_type = value["properties"].get('@type', None)
        block_type = 'none'

        if content_type == 'visualization':
            block_type = 'embed_visualization'
        if content_type == 'tableau_visualization':
            block_type = 'embed_tableau_visualization'
        if content_type == 'map_visualization':
            block_type = 'embed_eea_map_block'
        if content_type == 'map_interactive':
            block_type = 'embed_maps'

        new_value = value.copy()
        for handler in iter_block_transform_handlers(
                self.context, {**value, "@type": block_type},
                IBlockFieldSerializationTransformer):
            new_value = handler(new_value)

        return new_value


@implementer(IBlockFieldDeserializationTransformer)
@adapter(IBlocks, IBrowserRequest)
class EmbedContentDeserializationTransformer:
    """Embed content deserialization"""

    order = 9999
    block_type = "embed_content"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        for attr in [
            'properties', 'visualization', 'tableau_visualization',
            'map_visualization_data', 'maps', 'image_scales', 'vis_url',
                'tableau_vis_url']:
            if attr in value:
                del value[attr]

        return value


class EmbedTableauVisualizationSerializationTransformer((
        EmbedingBlockSerializationTransformer)):
    """Embed tableau visualization serialization"""

    order = 9999
    block_type = "embed_tableau_visualization"
    title = "Dashboard"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        if not self.initialized:
            self.init(value)

        url = uid_to_url(self.state.get("url"))
        doc_json = self.state.get("doc_json")

        value["tableau_vis_url"] = url

        if self.error:
            return {
                **value,
                "visualization": {
                    "error": self.error
                }
            }

        if 'tableau_visualization' in value:
            del value['tableau_visualization']

        if not doc_json:
            return value

        return {
            **value,
            "tableau_visualization": {
                **doc_json.get('tableau_visualization', {}),
                **getMetadata(doc_json),
            }
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
        if 'tableau_visualization' in value:
            del value['tableau_visualization']
        if 'tableau_vis_url' in value:
            value['tableau_vis_url'] = path2uid(context=self.context,
                                                link=value['tableau_vis_url'])
        return value


class EmbedEEAMapBlockSerializationTransformer(
        EmbedingBlockSerializationTransformer):
    """Embed eea map block serializer"""

    order = 9999
    block_type = "embed_eea_map_block"
    title = "Map (Simple)"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        if not self.initialized:
            self.init(value)

        url = uid_to_url(self.state.get("url"))
        doc_json = self.state.get("doc_json")

        value["vis_url"] = url

        if self.error:
            return {
                **value,
                "visualization": {
                    "error": self.error
                }
            }

        if 'map_visualization_data' in value:
            del value['map_visualization_data']

        if not doc_json:
            return value

        return {
            **value,
            "map_visualization_data": {
                **doc_json.get('map_visualization_data', {}),
                **getMetadata(doc_json),
            }
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
        if 'map_visualization_data' in value:
            del value['map_visualization_data']
        if 'vis_url' in value:
            value['vis_url'] = path2uid(context=self.context,
                                        link=value['vis_url'])
        return value


class EmbedMapsSerializationTransformer(
        EmbedingBlockSerializationTransformer):
    """Embed maps serializer"""

    order = 9999
    block_type = "embed_maps"
    title = "Map (Interactive)"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, value):
        if not self.initialized:
            self.init(value)

        url = uid_to_url(self.state.get("url"))
        doc_json = self.state.get("doc_json")

        value["url"] = url

        if self.error:
            return {
                **value,
                "visualization": {
                    "error": self.error
                }
            }

        if 'maps' in value:
            del value['maps']

        if not doc_json:
            return value

        return {
            **value, "maps": {
                **doc_json.get('maps', {}),
                **getMetadata(doc_json),
            }
        }


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
