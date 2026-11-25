"""Tests for map_interactive preview rendering."""

import unittest
from unittest import mock

from plone.namedfile.file import NamedBlobImage
from plone.namedfile.interfaces import IStorage
from plone.namedfile.storages import BytesStorable
from zope.component import provideUtility
from zope.lifecycleevent import Attributes, ObjectModifiedEvent

from eea.api.dataconnector import map_preview
from eea.api.dataconnector.interfaces import IMaps
from eea.api.dataconnector.map_preview import GENERATED_FILENAME

PORTAL = "https://portal.discomap.eea.europa.eu/arcgis"
REST = PORTAL + "/sharing/rest/content/items"
APP_ID = "4866816a1ae14283a754a3c6cb369aae"
WEBMAP_ID = "72b12bf1d5dd41a28a41f8173632e2e9"
APP_URL = f"{PORTAL}/apps/experiencebuilder/experience/?id={APP_ID}"
PRINT_HOST = "https://water.discomap.eea.europa.eu"
PNG = map_preview.PNG_SIGNATURE + b"image"
VIEW = {"xmin": 1, "ymin": 2, "xmax": 3, "ymax": 4, "spatialReference": {"wkid": 3857}}


class Response:
    """Minimal requests.Response stand-in"""

    def __init__(self, url, data=None, content=b""):
        self.url = url
        self.data = data
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


ARCGIS = {
    f"{REST}/{APP_ID}": {"type": "Web Experience"},
    f"{REST}/{APP_ID}/data": {
        "dataSources": {"ds": {"type": "WEB_MAP", "itemId": WEBMAP_ID}}
    },
    f"{REST}/{WEBMAP_ID}": {"type": "Web Map", "extent": [[0, 0], [1, 1]]},
    f"{REST}/{WEBMAP_ID}/data": {
        "initialState": {"viewpoint": {"targetGeometry": VIEW}},
        "baseMap": {"baseMapLayers": [{"id": "base"}]},
        "operationalLayers": [{"id": "data"}],
    },
}


def fake_get(url, **kwargs):
    if url.endswith(".png"):
        return Response(url, content=PNG)
    return Response(url, ARCGIS[url])


def fake_post(url, data=None, **kwargs):
    fake_post.calls.append(data)
    out = {"results": [{"value": {"url": PRINT_HOST + "/out/_ags_1.png"}}]}
    return Response(url, out)


class Item:
    """A map_interactive stand-in"""

    def __init__(self, url=APP_URL, preview_image=None):
        self.maps = {"url": url}
        self.preview_image = preview_image

    def absolute_url(self):
        return "http://nohost/plone/map"


def register_storage():
    """NamedBlobImage needs plone.namedfile's storage for bytes"""
    provideUtility(BytesStorable(), IStorage, name="builtins.bytes")


def image(filename):
    register_storage()
    return NamedBlobImage(data=PNG, filename=filename, contentType="image/png")


@mock.patch.object(map_preview.requests, "post", side_effect=fake_post)
@mock.patch.object(map_preview.requests, "get", side_effect=fake_get)
class TestRenderPreview(unittest.TestCase):
    """Rendering an app URL through the print service"""

    def setUp(self):
        fake_post.calls = []

    def test_renders_app_web_map_at_its_saved_view(self, get, post):
        self.assertEqual(map_preview.render_preview(APP_URL), PNG)
        sent = map_preview.json.loads(fake_post.calls[0]["Web_Map_as_JSON"])
        self.assertEqual(sent["mapOptions"]["extent"], VIEW)
        self.assertEqual(
            [layer["id"] for layer in sent["operationalLayers"]], ["base", "data"]
        )
        self.assertEqual(fake_post.calls[0]["Layout_Template"], "MAP_ONLY")

    def test_ignores_non_portal_and_unlisted_hosts(self, get, post):
        for url in (
            "https://adventure.discomap.eea.europa.eu/experience/13",
            f"https://evil.example/arcgis/apps/dashboards/{APP_ID}",
            f"http://portal.discomap.eea.europa.eu/arcgis/apps/dashboards/{APP_ID}",
            "",
            None,
        ):
            self.assertIsNone(map_preview.render_preview(url), url)
        get.assert_not_called()

    def test_rejects_output_from_another_host(self, get, post):
        post.side_effect = lambda url, **kw: Response(
            url, {"results": [{"value": {"url": "https://other.host/x.png"}}]}
        )
        with self.assertRaises(ValueError):
            map_preview.render_preview(APP_URL)

    def test_disabled_by_empty_print_url(self, get, post):
        with mock.patch.dict("os.environ", {"EEA_MAP_PREVIEW_PRINT_URL": ""}):
            self.assertIsNone(map_preview.render_preview(APP_URL))
        get.assert_not_called()


class TestFindWebmap(unittest.TestCase):
    """Locating the web map in each ArcGIS app type"""

    def test_app_types(self):
        cases = {
            "experience builder": {
                "dataSources": {"a": {"type": "WEB_MAP", "itemId": "wm"}}
            },
            "instant app": {"values": {"webmap": "wm"}},
            "web appbuilder": {"map": {"itemId": "wm"}},
            "dashboard": {
                "desktopView": {"widgets": [{"type": "mapWidget", "itemId": "wm"}]}
            },
        }
        for name, data in cases.items():
            self.assertEqual(map_preview.find_webmap(data), "wm", name)
        self.assertIsNone(map_preview.find_webmap({"widgets": []}))

    def test_falls_back_to_item_extent(self):
        extent = map_preview.web_map_as_json({}, [[0, 0], [10, 10]])["mapOptions"][
            "extent"
        ]
        self.assertAlmostEqual(extent["xmin"], 0)
        self.assertAlmostEqual(extent["xmax"], 1113194.9, places=0)


@mock.patch.object(map_preview, "render_preview", return_value=PNG)
class TestUpdatePreview(unittest.TestCase):
    """Which stored images get replaced"""

    def setUp(self):
        register_storage()

    def test_sets_generated_image_when_missing(self, render):
        item = Item()
        self.assertTrue(map_preview.update_preview(item))
        self.assertEqual(item.preview_image.filename, GENERATED_FILENAME)
        self.assertEqual(item.preview_image.data, PNG)

    def test_replaces_previously_generated_image(self, render):
        item = Item(preview_image=image(GENERATED_FILENAME))
        self.assertTrue(map_preview.update_preview(item))

    def test_never_replaces_uploaded_image(self, render):
        uploaded = image("my-screenshot.png")
        item = Item(preview_image=uploaded)
        self.assertFalse(map_preview.update_preview(item))
        self.assertIs(item.preview_image, uploaded)
        render.assert_not_called()

    def test_failure_keeps_current_image(self, render):
        render.side_effect = OSError("print service down")
        old = image(GENERATED_FILENAME)
        item = Item(preview_image=old)
        self.assertFalse(map_preview.update_preview(item))
        self.assertIs(item.preview_image, old)


@mock.patch.object(map_preview, "update_preview")
class TestSubscribers(unittest.TestCase):
    """When saving triggers a render"""

    def test_modified_maps_triggers(self, update):
        item = Item()
        map_preview.on_modified(
            item, ObjectModifiedEvent(item, Attributes(IMaps, "IMaps.maps"))
        )
        update.assert_called_once_with(item)

    def test_other_changes_do_not_trigger(self, update):
        item = Item()
        map_preview.on_modified(item, ObjectModifiedEvent(item))
        map_preview.on_modified(
            item, ObjectModifiedEvent(item, Attributes(IMaps, "IMaps.other"))
        )
        update.assert_not_called()

    def test_added_only_without_preview(self, update):
        map_preview.on_added(Item(preview_image=image("x.png")), None)
        update.assert_not_called()
        item = Item()
        map_preview.on_added(item, None)
        update.assert_called_once_with(item)
