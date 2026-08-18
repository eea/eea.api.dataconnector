"""Tests for the @connector-data service response helper."""

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from plone.restapi.interfaces import IExpandableElement
from zope.component import provideAdapter
from zope.component.testing import setUp as componentSetUp
from zope.component.testing import tearDown as componentTearDown
from zope.interface import implementer
from zope.interface import Interface
from zope.interface.interfaces import ComponentLookupError
from zExceptions import NotFound

from eea.api.dataconnector.api.dataconnector import connector_data_response
from eea.api.dataconnector.interfaces import IConnectorDataProvider

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


class ConnectorDataResponseTest(unittest.TestCase):
    """Verify the merged response timing and error behavior."""

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

    @patch(f"{MODULE}.sleep")
    @patch(f"{MODULE}._time", side_effect=[10.0, 10.2])
    def test_finds_registered_adapter_and_delays_success(self, _time, sleep):
        result = connector_data_response(ConnectorContext(), object())

        self.assertEqual(result, {"data": {"results": []}})
        self.assertEqual(RegisteredConnectorData.calls, [True])
        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args.args[0], 0.3)

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
