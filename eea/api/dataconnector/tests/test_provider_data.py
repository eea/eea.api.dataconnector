"""Tests for connector and file provider responses."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests
from plone.memoize.ram import global_cache
from zope.component import provideAdapter
from zope.component.testing import setUp as componentSetUp
from zope.component.testing import tearDown as componentTearDown
from zope.interface import Interface, implementer
from ZPublisher.HTTPResponse import HTTPResponse

from eea.api.dataconnector.adapter import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_READ_TIMEOUT,
    DataProviderForConnectors,
    _get_discodata_timeouts,
    _parse_timeout,
)
from eea.api.dataconnector.api.dataconnector import ConnectorData
from eea.api.dataconnector.behavior import DataProviderForFiles
from eea.api.dataconnector.exceptions import BadGateway, GatewayTimeout
from eea.api.dataconnector.interfaces import (
    IConnectorDataProvider,
    IDataProvider,
)


class EmptyProviderDataTest(unittest.TestCase):
    """Verify empty providers preserve the public connector-data shape."""

    def test_connector_without_sql_query(self):
        context = SimpleNamespace(sql_query="", readme="Connector documentation")

        data = DataProviderForConnectors(context, object()).provided_data

        self.assertEqual(
            data,
            {
                "results": [],
                "metadata": {"readme": "Connector documentation"},
            },
        )

    @patch("eea.api.dataconnector.behavior.json_body", return_value={"form": {}})
    def test_file_provider_without_file(self, json_body):
        context = SimpleNamespace(file=None)

        data = DataProviderForFiles(context, object()).provided_data

        self.assertEqual(data, {"results": [], "metadata": {}})
        json_body.assert_called()


class ParseTimeoutTest(unittest.TestCase):
    """Verify timeout parsing helper."""

    def test_default_on_none(self):
        self.assertEqual(_parse_timeout(None, 5.0), 5.0)

    def test_parses_valid_float_and_int(self):
        self.assertEqual(_parse_timeout("10", 5.0), 10.0)
        self.assertEqual(_parse_timeout("2.5", 5.0), 2.5)
        self.assertEqual(_parse_timeout(3, 5.0), 3.0)
        self.assertEqual(_parse_timeout(4.5, 5.0), 4.5)

    def test_default_on_invalid_or_non_positive(self):
        self.assertEqual(_parse_timeout("abc", 5.0), 5.0)
        self.assertEqual(_parse_timeout("-1", 5.0), 5.0)
        self.assertEqual(_parse_timeout("0", 5.0), 5.0)
        self.assertEqual(_parse_timeout("inf", 5.0), 5.0)
        self.assertEqual(_parse_timeout("nan", 5.0), 5.0)
        self.assertEqual(_parse_timeout([], 5.0), 5.0)


class GetDiscodataTimeoutsTest(unittest.TestCase):
    """Verify timeout resolution from environment variables."""

    def test_defaults_when_env_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                _get_discodata_timeouts(),
                (DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT),
            )

    def test_fallback_discodata_timeout(self):
        with patch.dict(os.environ, {"DISCODATA_TIMEOUT": "20"}, clear=True):
            self.assertEqual(_get_discodata_timeouts(), (20.0, 20.0))

    def test_specific_timeouts_override_fallback(self):
        with patch.dict(
            os.environ,
            {
                "DISCODATA_TIMEOUT": "20",
                "DISCODATA_CONNECT_TIMEOUT": "3",
                "DISCODATA_READ_TIMEOUT": "30",
            },
            clear=True,
        ):
            self.assertEqual(_get_discodata_timeouts(), (3.0, 30.0))


class ConnectorDataProviderTest(unittest.TestCase):
    """Verify DataProviderForConnectors error handling and response processing."""

    def setUp(self):
        self.context = SimpleNamespace(
            endpoint_url="https://discodata.eea.europa.eu/sql",
            sql_query="SELECT * FROM tbl",
            readme="Connector docs",
        )
        self.request = object()
        self.fake_sql = {
            "conditions": [],
            "data_query": [],
            "form": {},
            "query": {"select": "*", "from": "tbl"},
        }

    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_timeout_raises_gateway_timeout(self, mock_post, mock_parse):
        mock_parse.return_value = self.fake_sql
        mock_post.side_effect = requests.Timeout("Connection timed out")

        provider = DataProviderForConnectors(self.context, self.request)
        with self.assertRaises(GatewayTimeout) as ctx:
            provider._get_data()
        self.assertIn("Discodata request timed out", str(ctx.exception))

    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_connect_timeout_raises_gateway_timeout(self, mock_post, mock_parse):
        mock_parse.return_value = self.fake_sql
        mock_post.side_effect = requests.ConnectTimeout("Connect timed out")

        provider = DataProviderForConnectors(self.context, self.request)
        with self.assertRaises(GatewayTimeout):
            provider._get_data()

    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_connection_error_raises_bad_gateway(self, mock_post, mock_parse):
        mock_parse.return_value = self.fake_sql
        mock_post.side_effect = requests.ConnectionError("Connection refused")

        provider = DataProviderForConnectors(self.context, self.request)
        with self.assertRaises(BadGateway) as ctx:
            provider._get_data()
        self.assertIn("Discodata connection failure", str(ctx.exception))

    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_http_error_status_raises_bad_gateway(self, mock_post, mock_parse):
        mock_parse.return_value = self.fake_sql
        response = MagicMock()
        response.status_code = 500
        response.text = "Internal Server Error"
        mock_post.return_value = response

        provider = DataProviderForConnectors(self.context, self.request)
        with self.assertRaises(BadGateway) as ctx:
            provider._get_data()
        self.assertIn("Discodata returned HTTP 500", str(ctx.exception))

    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_malformed_json_raises_bad_gateway(self, mock_post, mock_parse):
        mock_parse.return_value = self.fake_sql
        response = MagicMock()
        response.status_code = 200
        response.text = "<html>502 Bad Gateway</html>"
        response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = response

        provider = DataProviderForConnectors(self.context, self.request)
        with self.assertRaises(BadGateway) as ctx:
            provider._get_data()
        self.assertIn("Discodata returned malformed JSON", str(ctx.exception))

    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_non_dict_payload_raises_bad_gateway(self, mock_post, mock_parse):
        mock_parse.return_value = self.fake_sql
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = ["not", "a", "dict"]
        mock_post.return_value = response

        provider = DataProviderForConnectors(self.context, self.request)
        with self.assertRaises(BadGateway) as ctx:
            provider._get_data()
        self.assertIn("invalid payload shape", str(ctx.exception))

    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_payload_with_errors_raises_bad_gateway(self, mock_post, mock_parse):
        mock_parse.return_value = self.fake_sql
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"errors": "SQL syntax error"}
        mock_post.return_value = response

        provider = DataProviderForConnectors(self.context, self.request)
        with self.assertRaises(BadGateway) as ctx:
            provider._get_data()
        self.assertIn("Discodata provider error: SQL syntax error", str(ctx.exception))

    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_non_list_results_raises_bad_gateway(self, mock_post, mock_parse):
        mock_parse.return_value = self.fake_sql
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"results": "not a list"}
        mock_post.return_value = response

        provider = DataProviderForConnectors(self.context, self.request)
        with self.assertRaises(BadGateway) as ctx:
            provider._get_data()
        self.assertIn(
            "Discodata results field is missing or not a list",
            str(ctx.exception),
        )

    @patch("eea.api.dataconnector.adapter.filteredData")
    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_valid_results_returned(self, mock_post, mock_parse, mock_filtered_data):
        mock_parse.return_value = self.fake_sql
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"results": [{"col1": "val1", "col2": "val2"}]}
        mock_post.return_value = response
        mock_filtered_data.return_value = {"col1": ["val1"], "col2": ["val2"]}

        provider = DataProviderForConnectors(self.context, self.request)
        data = provider._get_data()
        self.assertEqual(
            data,
            {
                "results": {"col1": ["val1"], "col2": ["val2"]},
                "metadata": {"readme": "Connector docs"},
            },
        )
        mock_post.assert_called_once_with(
            self.context.endpoint_url,
            {"query": "SELECT * FROM tbl"},
            timeout=(DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT),
        )
        mock_filtered_data.assert_called_once_with(
            [{"col1": "val1", "col2": "val2"}], []
        )

    @patch("eea.api.dataconnector.adapter.filteredData", return_value={})
    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_empty_filtered_results_returned_as_empty_list(
        self, mock_post, mock_parse, mock_filtered_data
    ):
        mock_parse.return_value = self.fake_sql
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"results": []}
        mock_post.return_value = response

        provider = DataProviderForConnectors(self.context, self.request)
        data = provider._get_data()
        self.assertEqual(
            data,
            {
                "results": [],
                "metadata": {"readme": "Connector docs"},
            },
        )


class HttpResponseStatusTest(unittest.TestCase):
    """Verify HTTPResponse status mapping for custom gateway exceptions."""

    def test_http_response_status_mapping(self):
        response_bad_gateway = HTTPResponse()
        response_bad_gateway.setStatus(BadGateway)
        self.assertEqual(response_bad_gateway.status, 502)

        response_timeout = HTTPResponse()
        response_timeout.setStatus(GatewayTimeout)
        self.assertEqual(response_timeout.status, 504)


@implementer(IConnectorDataProvider)
class CacheImmunityConnectorContext:
    """Context providing IConnectorDataProvider for cache immunity tests."""


class MockProviderForCacheImmunity:
    """Mock provider with call counting and controllable outcomes."""

    def __init__(self):
        self.call_count = 0
        self.side_effect = None
        self.return_value = None

    @property
    def provided_data(self):
        self.call_count += 1
        if self.side_effect:
            raise self.side_effect
        return self.return_value


class ConnectorDataCacheImmunityTest(unittest.TestCase):
    """Verify that ConnectorData._expand_connector_data handles caching properly.

    Provider errors must not poison @ram.cache, while valid empty and non-empty
    results must be cached normally.
    """

    def setUp(self):
        componentSetUp()
        global_cache.invalidateAll()
        self.mock_provider = MockProviderForCacheImmunity()
        provideAdapter(
            lambda context, request: self.mock_provider,
            adapts=(IConnectorDataProvider, Interface),
            provides=IDataProvider,
            name="connector",
        )
        self.context = CacheImmunityConnectorContext()
        self.request = object()
        self.connector = ConnectorData(self.context, self.request)
        self.context_path = "/site/data-connector"
        self.payload_hash = "test-payload-hash-1"
        self.context_revision = "revision-1"

    def tearDown(self):
        componentTearDown()
        global_cache.invalidateAll()

    def test_gateway_timeout_not_cached(self):
        self.mock_provider.side_effect = GatewayTimeout("Discodata timeout")

        with self.assertRaises(GatewayTimeout) as ctx:
            self.connector._expand_connector_data(
                self.context_path, self.payload_hash, self.context_revision
            )
        self.assertIn("Discodata timeout", str(ctx.exception))
        self.assertEqual(self.mock_provider.call_count, 1)

        # Cache must not be populated
        self.assertEqual(global_cache.getStatistics(), ())

        # Subsequent call invokes provider again (not serving cached error)
        self.mock_provider.side_effect = None
        self.mock_provider.return_value = {
            "results": [{"col": "val"}],
            "metadata": {"readme": "docs"},
        }
        result = self.connector._expand_connector_data(
            self.context_path, self.payload_hash, self.context_revision
        )
        self.assertEqual(self.mock_provider.call_count, 2)
        self.assertEqual(
            result,
            {"results": [{"col": "val"}], "metadata": {"readme": "docs"}},
        )

    def test_bad_gateway_not_cached(self):
        self.mock_provider.side_effect = BadGateway("Discodata error")

        with self.assertRaises(BadGateway) as ctx:
            self.connector._expand_connector_data(
                self.context_path, self.payload_hash, self.context_revision
            )
        self.assertIn("Discodata error", str(ctx.exception))
        self.assertEqual(self.mock_provider.call_count, 1)

        # Cache must not be populated
        self.assertEqual(global_cache.getStatistics(), ())

        # Subsequent call invokes provider again
        self.mock_provider.side_effect = None
        self.mock_provider.return_value = {
            "results": [{"col": "val"}],
            "metadata": {"readme": "docs"},
        }
        result = self.connector._expand_connector_data(
            self.context_path, self.payload_hash, self.context_revision
        )
        self.assertEqual(self.mock_provider.call_count, 2)
        self.assertEqual(
            result,
            {"results": [{"col": "val"}], "metadata": {"readme": "docs"}},
        )

    def test_valid_empty_results_cached(self):
        self.mock_provider.return_value = {
            "results": [],
            "metadata": {"readme": "docs"},
        }

        # First call: invokes provider and populates cache
        result1 = self.connector._expand_connector_data(
            self.context_path, self.payload_hash, self.context_revision
        )
        self.assertEqual(
            result1,
            {"results": [], "metadata": {"readme": "docs"}},
        )
        self.assertEqual(self.mock_provider.call_count, 1)

        stats = global_cache.getStatistics()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["entries"], 1)
        self.assertEqual(stats[0]["hits"], 0)

        # Second call with same cache key: served from cache without calling provider
        result2 = self.connector._expand_connector_data(
            self.context_path, self.payload_hash, self.context_revision
        )
        self.assertEqual(
            result2,
            {"results": [], "metadata": {"readme": "docs"}},
        )
        self.assertEqual(self.mock_provider.call_count, 1)

        stats = global_cache.getStatistics()
        self.assertEqual(stats[0]["hits"], 1)

    def test_valid_non_empty_results_cached(self):
        self.mock_provider.return_value = {
            "results": [{"col1": "a", "col2": "b"}],
            "metadata": {"readme": "docs"},
        }

        # First call: invokes provider and populates cache
        result1 = self.connector._expand_connector_data(
            self.context_path, self.payload_hash, self.context_revision
        )
        self.assertEqual(
            result1,
            {
                "results": [{"col1": "a", "col2": "b"}],
                "metadata": {"readme": "docs"},
            },
        )
        self.assertEqual(self.mock_provider.call_count, 1)

        stats = global_cache.getStatistics()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["entries"], 1)
        self.assertEqual(stats[0]["hits"], 0)

        # Second call with same cache key: served from cache without calling provider
        result2 = self.connector._expand_connector_data(
            self.context_path, self.payload_hash, self.context_revision
        )
        self.assertEqual(
            result2,
            {
                "results": [{"col1": "a", "col2": "b"}],
                "metadata": {"readme": "docs"},
            },
        )
        self.assertEqual(self.mock_provider.call_count, 1)

        stats = global_cache.getStatistics()
        self.assertEqual(stats[0]["hits"], 1)


class InterfacesWildcardImportTest(unittest.TestCase):
    """Verify interfaces module exposes expected symbols and no restrictive __all__."""

    def test_interfaces_module_exports(self):
        import eea.api.dataconnector.interfaces as ifaces

        self.assertFalse(hasattr(ifaces, "__all__"))
        self.assertTrue(hasattr(ifaces, "IDataConnector"))
        self.assertTrue(hasattr(ifaces, "IDataProvider"))
        self.assertTrue(hasattr(ifaces, "BadGateway"))
        self.assertTrue(hasattr(ifaces, "GatewayTimeout"))
        self.assertTrue(hasattr(ifaces, "DiscodataProviderError"))


def test_suite():
    """Test suite."""
    return unittest.defaultTestLoader.loadTestsFromName(__name__)
