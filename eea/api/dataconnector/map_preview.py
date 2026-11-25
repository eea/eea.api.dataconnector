"""Preview images for map_interactive items, rendered by ArcGIS.

A map_interactive item embeds an external ArcGIS app (Experience Builder,
Dashboards, Web AppBuilder) in a cross-origin iframe, so the browser cannot
capture it. Every such app is backed by a web map: a JSON spec of basemap and
layers that the ArcGIS "Export Web Map" print task renders server-side.
"""

import json
import logging
import math
import os
import re
from urllib.parse import urlparse

import requests
from plone.namedfile.file import NamedBlobImage

from eea.api.dataconnector.interfaces import IMaps

logger = logging.getLogger("eea.api.dataconnector.map_preview")

# Same marker as the @eeacms/volto-embed preview_image middleware: an image
# with this filename was generated and may be replaced, any other was uploaded.
GENERATED_FILENAME = "preview_image_generated_map_interactive.png"

DEFAULT_PORTALS = "portal.discomap.eea.europa.eu"
DEFAULT_PRINT_URL = (
    "https://water.discomap.eea.europa.eu/arcgis/rest/services/Utilities/"
    "PrintingTools/GPServer/Export%20Web%20Map%20Task/execute"
)
TIMEOUT = 30
OUTPUT_SIZE = [1200, 800]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ITEM_ID = re.compile(r"(?:[?&](?:id|appid|webmap)=|/dashboards/)([0-9a-f]{32})")


def print_url():
    """Export Web Map execute URL. An empty value disables previews."""
    return os.environ.get("EEA_MAP_PREVIEW_PRINT_URL", DEFAULT_PRINT_URL)


def allowed_portals():
    """ArcGIS portal hosts we may query, so editors can't point us anywhere."""
    hosts = os.environ.get("EEA_MAP_PREVIEW_PORTALS", DEFAULT_PORTALS)
    return {host.strip() for host in hosts.split(",") if host.strip()}


def _get(url, **kwargs):
    response = requests.get(url, timeout=TIMEOUT, **kwargs)
    response.raise_for_status()
    return response


def _json(response):
    data = response.json()
    if isinstance(data, dict) and "error" in data:
        raise ValueError(f"ArcGIS error from {response.url}: {data['error']}")
    return data


def portal_item(app_url):
    """Return (sharing REST base URL, item id) for an allowed portal app."""
    parsed = urlparse(app_url or "")
    match = ITEM_ID.search(app_url or "")
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed_portals()
        or not parsed.path.startswith("/arcgis/")
        or not match
    ):
        return None
    return f"https://{parsed.netloc}/arcgis/sharing/rest", match.group(1)


def _find_dashboard_map(data):
    """First mapWidget item id anywhere in a Dashboards config."""
    if isinstance(data, dict):
        if data.get("type") == "mapWidget" and data.get("itemId"):
            return data["itemId"]
        data = list(data.values())
    if isinstance(data, list):
        for value in data:
            found = _find_dashboard_map(value)
            if found:
                return found
    return None


def find_webmap(app_data):
    """Web map item id referenced by an ArcGIS app config, or None."""
    for source in (app_data.get("dataSources") or {}).values():  # Exp. Builder
        if source.get("type") == "WEB_MAP" and source.get("itemId"):
            return source["itemId"]
    values = app_data.get("values") or {}  # instant apps
    if values.get("webmap"):
        return values["webmap"]
    app_map = app_data.get("map") or {}  # Web AppBuilder
    if isinstance(app_map, dict) and app_map.get("itemId"):
        return app_map["itemId"]
    return _find_dashboard_map(app_data)  # Dashboards


def _mercator(lon, lat):
    lat = max(min(lat, 85.0), -85.0)
    x = lon * 20037508.34 / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) * 20037508.34 / math.pi
    return x, y


def web_map_as_json(webmap, item_extent=None):
    """Export Web Map task input: the web map at its saved initial view."""
    extent = ((webmap.get("initialState") or {}).get("viewpoint") or {}).get(
        "targetGeometry"
    )
    if not extent and item_extent:
        (xmin, ymin), (xmax, ymax) = (_mercator(*point) for point in item_extent)
        extent = {
            "xmin": xmin,
            "ymin": ymin,
            "xmax": xmax,
            "ymax": ymax,
            "spatialReference": {"wkid": 3857},
        }
    basemap = (webmap.get("baseMap") or {}).get("baseMapLayers") or []
    return {
        "mapOptions": {"extent": extent},
        "operationalLayers": basemap + (webmap.get("operationalLayers") or []),
        "exportOptions": {"outputSize": OUTPUT_SIZE, "dpi": 96},
    }


def render_preview(app_url):
    """PNG bytes of the app's web map, or None if it is not a known app.

    Raises on network, ArcGIS or print errors.
    """
    endpoint = print_url()
    located = portal_item(app_url)
    if not endpoint or not located:
        return None
    rest, item_id = located

    item = _json(_get(f"{rest}/content/items/{item_id}", params={"f": "json"}))
    if item.get("type") == "Web Map":
        webmap_id = item_id
    else:
        app_data = _get(f"{rest}/content/items/{item_id}/data", params={"f": "json"})
        webmap_id = find_webmap(_json(app_data))
        if not webmap_id:
            return None
        item = _json(_get(f"{rest}/content/items/{webmap_id}", params={"f": "json"}))
    webmap = _json(_get(f"{rest}/content/items/{webmap_id}/data", params={"f": "json"}))

    response = requests.post(
        endpoint,
        data={
            "Web_Map_as_JSON": json.dumps(web_map_as_json(webmap, item.get("extent"))),
            "Format": "PNG32",
            "Layout_Template": "MAP_ONLY",
            "f": "json",
        },
        timeout=TIMEOUT * 2,
    )
    response.raise_for_status()
    image_url = _json(response)["results"][0]["value"]["url"]
    if urlparse(image_url).hostname != urlparse(endpoint).hostname:
        raise ValueError(f"Unexpected print output URL: {image_url}")

    image = _get(image_url).content
    if not image.startswith(PNG_SIGNATURE):
        raise ValueError(f"Print output is not a PNG: {image_url}")
    return image


def has_uploaded_preview(context):
    """True if an editor set preview_image by hand; we never replace those."""
    image = getattr(context, "preview_image", None)
    return bool(image) and image.filename != GENERATED_FILENAME


def update_preview(context):
    """Render and store the preview image. Returns True if it was replaced.

    Never raises: a failed render keeps the current image so saving works.
    """
    if has_uploaded_preview(context):
        return False
    app_url = (getattr(context, "maps", None) or {}).get("url")
    try:
        image = render_preview(app_url)
    except Exception:  # network, ArcGIS or print failures must not block saves
        logger.warning(
            "Could not render map preview for %s from %s",
            context.absolute_url(),
            app_url,
            exc_info=True,
        )
        return False
    if not image:
        return False
    context.preview_image = NamedBlobImage(
        data=image, filename=GENERATED_FILENAME, contentType="image/png"
    )
    return True


def on_added(context, event):
    """New item: generate a preview unless one was already provided."""
    if not getattr(context, "preview_image", None):
        update_preview(context)


def on_modified(context, event):
    """Regenerate the preview when the embedded map changes."""
    for description in getattr(event, "descriptions", ()):
        if getattr(description, "interface", None) is IMaps and any(
            name.split(".")[-1] == "maps" for name in description.attributes
        ):
            update_preview(context)
            return
