"""Tests for the @connector-data service response helper."""

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from Acquisition import Implicit
from plone.restapi.interfaces import IExpandableElement
from zope.component import provideAdapter
from zope.component.testing import setUp as componentSetUp
from zope.component.testing import tearDown as componentTearDown
from zope.interface import alsoProvides
from zope.interface import implementer
from zope.interface import Interface
from zope.interface.interfaces import ComponentLookupError
from zExceptions import NotFound

from eea.api.dataconnector.api.dataconnector import (
    _connector_data_cache_key,
    _context_cache_revision,
    _get_virtual_connector_data,
    _normalize_provider_data,
    _provider_name,
    connector_data_response,
    ConnectorData,
)
from eea.api.dataconnector.interfaces import (
    IConnectorDataProvider,
    IFileDataProvider,
)

MODULE = "eea.api.dataconnector.api.dataconnector"


@implementer(IConnectorDataProvider)
class ConnectorContext:
    """Context providing the interface used by the real ZCML registration."""


@implementer(IExpandableElement)
class RegisteredConnectorData:
    """Named multi-adapter matching the production registration."""

    calls = []

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, expand=False):
        self.calls.append(expand)
        return {"connector-data": {"data": {"results": []}}}


class AcquisitionNode(Implicit):
    """Minimal acquisition-aware context for preload lookup tests."""


class ConnectorRequest(dict):
    """Minimal mapping request with a form attribute."""

    form = {}


class ConnectorDataContractTest(unittest.TestCase):
    """Verify provider-data normalization and virtual preload validation."""

    def _valid_connector_data(self):
        return {
            "@id": "http://example.com/facility/5000671/@connector-data",
            "path": "http://example.com/facility",
            "data": {"results": [], "metadata": {}},
            "payload": {"data_query": [], "form": {"db_version": "latest"}},
        }

    def test_normalizes_empty_provider_data(self):
        empty = {"results": [], "metadata": {}}

        self.assertEqual(_normalize_provider_data(None), empty)
        self.assertEqual(_normalize_provider_data([]), empty)
        self.assertEqual(
            _normalize_provider_data({"results": {}, "metadata": None}),
            empty,
        )

    def test_preserves_non_empty_provider_data(self):
        data = {
            "results": {"facilityLocalId": ["5000671"]},
            "metadata": {"readme": "Facility data"},
        }

        self.assertEqual(_normalize_provider_data(data), data)

    def test_accepts_owned_virtual_connector_data(self):
        connector_data = self._valid_connector_data()
        context = AcquisitionNode()
        context.is_virtual = True
        context.connector_data = connector_data

        self.assertIs(_get_virtual_connector_data(context), connector_data)

    def test_ignores_connector_data_on_non_virtual_context(self):
        context = AcquisitionNode()
        context.connector_data = self._valid_connector_data()

        self.assertIsNone(_get_virtual_connector_data(context))

    def test_does_not_acquire_virtual_connector_data(self):
        parent = AcquisitionNode()
        parent.connector_data = self._valid_connector_data()
        context = AcquisitionNode()
        context.is_virtual = True

        self.assertIsNone(_get_virtual_connector_data(context.__of__(parent)))

    def test_rejects_malformed_virtual_connector_data(self):
        malformed_values = [
            None,
            {},
            {
                "@id": "http://example.com/@connector-data",
                "path": "http://example.com",
                "data": {"results": [], "metadata": {}},
                "payload": {"data_query": [], "form": []},
            },
            {
                "@id": "http://example.com/@connector-data",
                "path": "http://example.com",
                "data": {"results": None, "metadata": {}},
                "payload": {"data_query": [], "form": {}},
            },
        ]

        for connector_data in malformed_values:
            with self.subTest(connector_data=connector_data):
                context = AcquisitionNode()
                context.is_virtual = True
                context.connector_data = connector_data

                with self.assertRaises(ValueError):
                    _get_virtual_connector_data(context)

    def test_real_connector_returns_virtual_preload_unchanged(self):
        connector_data = self._valid_connector_data()
        context = AcquisitionNode()
        context.is_virtual = True
        context.connector_data = connector_data

        result = ConnectorData(context, {})(expand=True)

        self.assertIs(result["connector-data"], connector_data)

    def test_provider_selection_does_not_acquire_parent_file(self):
        parent = AcquisitionNode()
        parent.file = object()
        context = AcquisitionNode()
        alsoProvides(context, IFileDataProvider, IConnectorDataProvider)

        self.assertEqual(_provider_name(context.__of__(parent)), "connector")

    def test_file_only_provider_without_file_uses_file_adapter(self):
        context = AcquisitionNode()
        alsoProvides(context, IFileDataProvider)

        self.assertEqual(_provider_name(context), "file")

    def test_context_revision_includes_serial_and_modified(self):
        context = AcquisitionNode()
        context._p_serial = b"\x01" * 8
        context.modified = lambda: "2026-08-18T10:00:00Z"

        self.assertEqual(
            _context_cache_revision(context),
            "0101010101010101:2026-08-18T10:00:00Z",
        )

    def test_context_revision_ignores_uncommitted_zodb_serial(self):
        context = AcquisitionNode()
        context._p_serial = b"\x00" * 8
        context.modified = lambda: "2026-08-18T10:00:00Z"

        self.assertEqual(
            _context_cache_revision(context),
            "2026-08-18T10:00:00Z",
        )

    def test_context_revision_uses_modified_fallback(self):
        context = AcquisitionNode()
        context.modified = lambda: "2026-08-18T10:00:00Z"

        self.assertEqual(
            _context_cache_revision(context),
            "2026-08-18T10:00:00Z",
        )

    def test_modified_date_changes_revision_before_serial_changes(self):
        context = AcquisitionNode()
        context._p_serial = b"\x01" * 8
        context.modified = lambda: "2026-08-18T10:00:00Z"
        first = _context_cache_revision(context)
        context.modified = lambda: "2026-08-18T10:01:00Z"

        self.assertNotEqual(first, _context_cache_revision(context))

    def test_content_revision_changes_cache_identity(self):
        first = _connector_data_cache_key(
            None,
            None,
            "/site/provider",
            "payload-hash",
            "revision-1",
        )
        second = _connector_data_cache_key(
            None,
            None,
            "/site/provider",
            "payload-hash",
            "revision-2",
        )

        self.assertNotEqual(first, second)

    def test_expansion_uses_content_revision(self):
        context = AcquisitionNode()
        context.absolute_url = lambda: "http://example.com/provider"
        context.getPhysicalPath = lambda: ("", "site", "provider")
        context.modified = lambda: "2026-08-18T10:00:00Z"
        connector = ConnectorData(context, ConnectorRequest())
        data = {"results": [], "metadata": {}}

        with patch.object(
            connector,
            "_expand_connector_data",
            return_value=data,
        ) as expand:
            result = connector(expand=True)

        self.assertEqual(result["connector-data"]["data"], data)
        self.assertEqual(
            expand.call_args.args[2],
            "2026-08-18T10:00:00Z",
        )


class ConnectorDataResponseTest(unittest.TestCase):
    """Verify connector lookup and error behavior."""

    def setUp(self):
        componentSetUp()
        RegisteredConnectorData.calls = []
        provideAdapter(
            RegisteredConnectorData,
            adapts=(IConnectorDataProvider, Interface),
            provides=IExpandableElement,
            name="connector-data",
        )

    def tearDown(self):
        componentTearDown()

    def test_finds_registered_adapter(self):
        result = connector_data_response(ConnectorContext(), object())

        self.assertEqual(result, {"data": {"results": []}})
        self.assertEqual(RegisteredConnectorData.calls, [True])

    def test_returns_not_found_without_connector_adapter(self):
        with self.assertRaises(NotFound):
            connector_data_response(object(), object())

    @patch(f"{MODULE}.queryMultiAdapter")
    def test_translates_provider_lookup_failure_to_not_found(
        self,
        query_multi_adapter,
    ):
        query_multi_adapter.return_value = Mock(
            side_effect=ComponentLookupError("No data provider found")
        )

        with self.assertRaises(NotFound):
            connector_data_response(ConnectorContext(), object())


def test_suite():
    """Test suite."""
    return unittest.defaultTestLoader.loadTestsFromName(__name__)
