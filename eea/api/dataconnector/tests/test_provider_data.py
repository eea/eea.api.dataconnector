"""Tests for connector and file provider responses."""

import os
import unittest
from time import monotonic
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests
from plone.memoize.ram import global_cache
from zope.component import provideAdapter
from zope.component.testing import setUp as componentSetUp
from zope.component.testing import tearDown as componentTearDown
from zope.interface import Interface, implementer
from ZPublisher.HTTPResponse import HTTPResponse

from eea.api.dataconnector import breaker
from eea.api.dataconnector.adapter import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_READ_TIMEOUT,
    DataProviderForConnectors,
    _get_discodata_timeouts,
)
from eea.api.dataconnector.api.dataconnector import ConnectorData
from eea.api.dataconnector.behavior import DataProviderForFiles
from eea.api.dataconnector.exceptions import BadGateway, GatewayTimeout
from eea.api.dataconnector.interfaces import (
    IConnectorDataProvider,
    IDataProvider,
)
from eea.api.dataconnector.utils import parse_positive_float


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
        self.assertEqual(parse_positive_float(None, 5.0), 5.0)

    def test_parses_valid_float_and_int(self):
        self.assertEqual(parse_positive_float("10", 5.0), 10.0)
        self.assertEqual(parse_positive_float("2.5", 5.0), 2.5)
        self.assertEqual(parse_positive_float(3, 5.0), 3.0)
        self.assertEqual(parse_positive_float(4.5, 5.0), 4.5)

    def test_default_on_invalid_or_non_positive(self):
        self.assertEqual(parse_positive_float("abc", 5.0), 5.0)
        self.assertEqual(parse_positive_float("-1", 5.0), 5.0)
        self.assertEqual(parse_positive_float("0", 5.0), 5.0)
        self.assertEqual(parse_positive_float("inf", 5.0), 5.0)
        self.assertEqual(parse_positive_float("nan", 5.0), 5.0)
        self.assertEqual(parse_positive_float([], 5.0), 5.0)


class GetDiscodataTimeoutsTest(unittest.TestCase):
    """Verify timeout resolution from environment variables."""

    def test_defaults_when_env_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                _get_discodata_timeouts(),
                (DEFAULT_CONNECT_TIMEOUT, 60.0),
            )
            self.assertEqual(DEFAULT_READ_TIMEOUT, 60.0)

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
        breaker.reset()
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

    def tearDown(self):
        breaker.reset()

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
    def test_empty_filtered_results_returned_as_empty_dict(
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
                "results": {},
                "metadata": {"readme": "Connector docs"},
            },
        )

    @patch("eea.api.dataconnector.adapter.filteredData", return_value={})
    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_null_results_treated_as_empty(
        self, mock_post, mock_parse, mock_filtered_data
    ):
        mock_parse.return_value = self.fake_sql
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"results": None}
        mock_post.return_value = response

        provider = DataProviderForConnectors(self.context, self.request)
        data = provider._get_data()
        self.assertEqual(
            data,
            {
                "results": {},
                "metadata": {"readme": "Connector docs"},
            },
        )
        mock_filtered_data.assert_called_once_with([], [])


class CircuitBreakerTest(unittest.TestCase):
    """Verify Discodata transport failures fail fast for the cooldown window."""

    def setUp(self):
        breaker.reset()
        patcher = patch.dict(os.environ, {}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
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

    def tearDown(self):
        breaker.reset()

    def _ok_response(self):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"results": []}
        return response

    def _other_context(self):
        return SimpleNamespace(
            endpoint_url="https://discodata.eea.europa.eu/sql",
            sql_query="SELECT * FROM other_tbl",
            readme="Connector docs",
        )

    def _fetch(self, context):
        return DataProviderForConnectors(context, self.request)._get_data()

    @patch("eea.api.dataconnector.adapter.filteredData", return_value={})
    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_connect_timeout_trips_endpoint_breaker(
        self, mock_post, mock_parse, mock_filtered_data
    ):
        mock_parse.return_value = self.fake_sql
        mock_post.side_effect = requests.ConnectTimeout("Connect timed out")

        with self.assertRaises(GatewayTimeout) as ctx:
            self._fetch(self.context)
        self.assertIn("Discodata request timed out", str(ctx.exception))
        with self.assertRaises(BadGateway) as ctx:
            self._fetch(self._other_context())
        self.assertIn("circuit open", str(ctx.exception))
        self.assertEqual(mock_post.call_count, 1)

    @patch("eea.api.dataconnector.adapter.filteredData", return_value={})
    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_connection_error_trips_endpoint_breaker(
        self, mock_post, mock_parse, mock_filtered_data
    ):
        mock_parse.return_value = self.fake_sql
        mock_post.side_effect = requests.ConnectionError("Connection refused")

        with self.assertRaises(BadGateway):
            self._fetch(self.context)
        with self.assertRaises(BadGateway) as ctx:
            self._fetch(self._other_context())
        self.assertIn("circuit open", str(ctx.exception))
        self.assertEqual(mock_post.call_count, 1)

    @patch("eea.api.dataconnector.adapter.filteredData", return_value={})
    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_http_5xx_trips_endpoint_breaker(
        self, mock_post, mock_parse, mock_filtered_data
    ):
        mock_parse.return_value = self.fake_sql
        response = MagicMock()
        response.status_code = 503
        response.text = "Service Unavailable"
        mock_post.return_value = response

        with self.assertRaises(BadGateway) as ctx:
            self._fetch(self.context)
        self.assertIn("Discodata returned HTTP 503", str(ctx.exception))
        with self.assertRaises(BadGateway) as ctx:
            self._fetch(self._other_context())
        self.assertIn("circuit open", str(ctx.exception))
        self.assertEqual(mock_post.call_count, 1)

    @patch("eea.api.dataconnector.adapter.filteredData", return_value={})
    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_read_timeout_trips_query_breaker_only(
        self, mock_post, mock_parse, mock_filtered_data
    ):
        mock_parse.return_value = self.fake_sql
        mock_post.side_effect = requests.ReadTimeout("Read timed out")

        with self.assertRaises(GatewayTimeout):
            self._fetch(self.context)
        with self.assertRaises(GatewayTimeout) as ctx:
            self._fetch(self.context)
        self.assertIn("circuit open", str(ctx.exception))
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(breaker._endpoint_open_until, {})

        mock_post.side_effect = None
        mock_post.return_value = self._ok_response()

        self._fetch(self._other_context())

        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(
            mock_post.call_args[0][0], "https://discodata.eea.europa.eu/sql"
        )

    @patch("eea.api.dataconnector.adapter.filteredData", return_value={})
    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_http_4xx_does_not_trip_breaker(
        self, mock_post, mock_parse, mock_filtered_data
    ):
        mock_parse.return_value = self.fake_sql
        response = MagicMock()
        response.status_code = 400
        response.text = "Bad Request"
        mock_post.return_value = response

        provider = DataProviderForConnectors(self.context, self.request)
        with self.assertRaises(BadGateway) as ctx:
            provider._get_data()
        self.assertIn("Discodata returned HTTP 400", str(ctx.exception))
        with self.assertRaises(BadGateway) as ctx:
            provider._get_data()
        self.assertNotIn("circuit open", str(ctx.exception))
        self.assertEqual(mock_post.call_count, 2)

    @patch("eea.api.dataconnector.adapter.filteredData", return_value={})
    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_sql_errors_payload_does_not_trip_breaker(
        self, mock_post, mock_parse, mock_filtered_data
    ):
        mock_parse.return_value = self.fake_sql
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"errors": "bad sql"}
        mock_post.return_value = response

        provider = DataProviderForConnectors(self.context, self.request)
        with self.assertRaises(BadGateway) as ctx:
            provider._get_data()
        self.assertIn("Discodata provider error: bad sql", str(ctx.exception))
        with self.assertRaises(BadGateway) as ctx:
            provider._get_data()
        self.assertNotIn("circuit open", str(ctx.exception))
        self.assertEqual(mock_post.call_count, 2)

    @patch("eea.api.dataconnector.adapter.filteredData", return_value={})
    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_malformed_json_does_not_trip_breaker(
        self, mock_post, mock_parse, mock_filtered_data
    ):
        mock_parse.return_value = self.fake_sql
        response = MagicMock()
        response.status_code = 200
        response.text = "<html>oops</html>"
        response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = response

        provider = DataProviderForConnectors(self.context, self.request)
        with self.assertRaises(BadGateway):
            provider._get_data()
        with self.assertRaises(BadGateway) as ctx:
            provider._get_data()
        self.assertNotIn("circuit open", str(ctx.exception))
        self.assertEqual(mock_post.call_count, 2)

    @patch("eea.api.dataconnector.adapter.filteredData", return_value={})
    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_non_dict_payload_does_not_trip_breaker(
        self, mock_post, mock_parse, mock_filtered_data
    ):
        mock_parse.return_value = self.fake_sql
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = ["not", "a", "dict"]
        mock_post.return_value = response

        provider = DataProviderForConnectors(self.context, self.request)
        with self.assertRaises(BadGateway):
            provider._get_data()
        with self.assertRaises(BadGateway) as ctx:
            provider._get_data()
        self.assertNotIn("circuit open", str(ctx.exception))
        self.assertEqual(mock_post.call_count, 2)

    @patch("eea.api.dataconnector.adapter.filteredData", return_value={})
    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_invalid_results_field_does_not_trip_breaker(
        self, mock_post, mock_parse, mock_filtered_data
    ):
        mock_parse.return_value = self.fake_sql
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"results": "not a list"}
        mock_post.return_value = response

        provider = DataProviderForConnectors(self.context, self.request)
        with self.assertRaises(BadGateway):
            provider._get_data()
        with self.assertRaises(BadGateway) as ctx:
            provider._get_data()
        self.assertNotIn("circuit open", str(ctx.exception))
        self.assertEqual(mock_post.call_count, 2)

    @patch("eea.api.dataconnector.adapter.filteredData", return_value={})
    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_breaker_is_scoped_per_endpoint(
        self, mock_post, mock_parse, mock_filtered_data
    ):
        mock_parse.return_value = self.fake_sql
        mock_post.side_effect = requests.ConnectionError("Connection refused")

        failing = SimpleNamespace(
            endpoint_url="https://discodata.eea.europa.eu/sql",
            sql_query="SELECT * FROM tbl",
            readme="Connector docs",
        )
        with self.assertRaises(BadGateway):
            self._fetch(failing)

        mock_post.side_effect = None
        mock_post.return_value = self._ok_response()
        healthy = SimpleNamespace(
            endpoint_url="https://discodata.example.org/sql",
            sql_query="SELECT * FROM tbl",
            readme="Connector docs",
        )

        self._fetch(healthy)

        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(mock_post.call_args[0][0], "https://discodata.example.org/sql")

    @patch("eea.api.dataconnector.adapter.filteredData", return_value={})
    @patch("eea.api.dataconnector.adapter.parseQuery")
    @patch("eea.api.dataconnector.adapter.requests.post")
    def test_breaker_recovers_after_cooldown(
        self, mock_post, mock_parse, mock_filtered_data
    ):
        mock_parse.return_value = self.fake_sql
        mock_post.side_effect = requests.Timeout("Read timed out")
        with self.assertRaises(GatewayTimeout):
            self._fetch(self.context)

        mock_post.side_effect = requests.ConnectionError("Connection refused")
        with self.assertRaises(BadGateway):
            self._fetch(self._other_context())

        mock_post.reset_mock()
        mock_post.side_effect = None
        mock_post.return_value = self._ok_response()
        later = monotonic() + breaker.DEFAULT_COOLDOWN + 1.0

        with patch("eea.api.dataconnector.breaker.monotonic", return_value=later):
            self._fetch(self.context)

        self.assertEqual(mock_post.call_count, 1)
        self.assertNotIn(self.context.endpoint_url, breaker._endpoint_open_until)
        self.assertEqual(breaker._query_open_until, {})

    def test_cooldown_from_environment(self):
        with patch.dict(os.environ, {"DISCODATA_CIRCUIT_COOLDOWN": "30"}, clear=True):
            self.assertEqual(breaker._cooldown(), 30.0)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(breaker._cooldown(), breaker.DEFAULT_COOLDOWN)
            self.assertEqual(breaker.DEFAULT_COOLDOWN, 15.0)
        for invalid in ("abc", "0", "-5", "nan"):
            with patch.dict(
                os.environ,
                {"DISCODATA_CIRCUIT_COOLDOWN": invalid},
                clear=True,
            ):
                self.assertEqual(breaker._cooldown(), breaker.DEFAULT_COOLDOWN)


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

    def test_gateway_timeout_does_not_populate_cache_and_subsequent_request_retries(
        self,
    ):
        self.mock_provider.side_effect = GatewayTimeout("Discodata timeout")

        with self.assertRaises(GatewayTimeout) as ctx:
            self.connector._expand_connector_data(
                self.context_path, self.payload_hash, self.context_revision
            )
        self.assertIn("Discodata timeout", str(ctx.exception))
        self.assertEqual(self.mock_provider.call_count, 1)
        self.assertEqual(global_cache.getStatistics(), ())

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

    def test_bad_gateway_does_not_populate_cache_and_subsequent_request_retries(
        self,
    ):
        self.mock_provider.side_effect = BadGateway("Discodata error")

        with self.assertRaises(BadGateway) as ctx:
            self.connector._expand_connector_data(
                self.context_path, self.payload_hash, self.context_revision
            )
        self.assertIn("Discodata error", str(ctx.exception))
        self.assertEqual(self.mock_provider.call_count, 1)
        self.assertEqual(global_cache.getStatistics(), ())

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

    def test_valid_empty_results_populated_and_served_from_cache(self):
        self.mock_provider.return_value = {
            "results": [],
            "metadata": {"readme": "docs"},
        }

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

    def test_valid_non_empty_results_populated_and_served_from_cache(self):
        self.mock_provider.return_value = {
            "results": [{"col1": "a", "col2": "b"}],
            "metadata": {"readme": "docs"},
        }

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


def test_suite():
    """Test suite."""
    return unittest.defaultTestLoader.loadTestsFromName(__name__)
