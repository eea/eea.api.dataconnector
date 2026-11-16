"""Tests for connector and file provider responses."""

import copy
import os
import unittest
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

import requests
from plone.memoize import ram
from plone.registry.interfaces import IRegistry
from zope.component import provideAdapter, provideUtility
from zope.component.testing import setUp as componentSetUp
from zope.component.testing import tearDown as componentTearDown
from zope.interface import Interface, alsoProvides
from ZPublisher.HTTPResponse import HTTPResponse

from eea.api.dataconnector.adapter import (
    DataProviderForConnectors,
    _get_discodata_timeouts,
)
from eea.api.dataconnector.api.dataconnector import ConnectorData
from eea.api.dataconnector.behavior import DataProviderForFiles
from eea.api.dataconnector.exceptions import BadGateway, GatewayTimeout
from eea.api.dataconnector.interfaces import IConnectorDataProvider, IDataProvider

MODULE = "eea.api.dataconnector.adapter"
ENDPOINT = "https://discodata.eea.europa.eu/sql"
README = "Connector documentation"
SQL = {
    "conditions": [],
    "data_query": [],
    "form": {},
    "query": {"select": "*", "from": "t"},
}


def _discodata_env(overrides):
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("DISCODATA_")
    }
    env.update(overrides)
    return env


class RegistryStub(dict):
    """Minimal registry utility for query filter lookups."""


class FakeResponse:
    """Minimal stand-in for a requests response."""

    def __init__(self, status_code=200, payload=None, text="", json_error=None):
        self.status_code = status_code
        self.payload = payload
        self.text = text
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


OUTCOMES = [
    (
        "valid rows",
        FakeResponse(payload={"results": [{"a": 1}, {"a": 2}]}),
        None,
        {"a": [1, 2]},
        200,
        None,
        None,
    ),
    ("empty results", FakeResponse(payload={"results": []}), None, {}, 200, None, None),
    (
        "null results",
        FakeResponse(payload={"results": None}),
        None,
        {},
        200,
        None,
        None,
    ),
    (
        "sql errors",
        FakeResponse(payload={"errors": "bad sql"}),
        None,
        {},
        200,
        "WARNING",
        "bad sql",
    ),
    (
        "http 400",
        FakeResponse(status_code=400, text="bad request"),
        BadGateway,
        None,
        502,
        "ERROR",
        "HTTP 400",
    ),
    (
        "http 500",
        FakeResponse(status_code=500, text="server error"),
        BadGateway,
        None,
        502,
        "ERROR",
        "HTTP 500",
    ),
    (
        "malformed json",
        FakeResponse(json_error=ValueError("no json"), text="<html>"),
        BadGateway,
        None,
        502,
        "ERROR",
        "invalid JSON",
    ),
    (
        "non dict payload",
        FakeResponse(payload=["x"]),
        BadGateway,
        None,
        502,
        "ERROR",
        "payload",
    ),
    (
        "non list results",
        FakeResponse(payload={"results": "nope"}),
        BadGateway,
        None,
        502,
        "ERROR",
        "unusable results",
    ),
    (
        "non dict rows",
        FakeResponse(payload={"results": [1, 2]}),
        BadGateway,
        None,
        502,
        "ERROR",
        "unusable results",
    ),
    (
        "timeout",
        requests.Timeout("slow"),
        GatewayTimeout,
        None,
        504,
        "ERROR",
        "timeout",
    ),
    (
        "connect timeout",
        requests.ConnectTimeout("connect"),
        GatewayTimeout,
        None,
        504,
        "ERROR",
        "timeout",
    ),
    (
        "connection error",
        requests.ConnectionError("down"),
        BadGateway,
        None,
        502,
        "ERROR",
        "request failed",
    ),
]


TIMEOUT_CONFIG = [
    ("unset", {}, (5.0, 30.0)),
    ("empty values", {"DISCODATA_TIMEOUT": ""}, (5.0, 30.0)),
    ("shared fallback", {"DISCODATA_TIMEOUT": "20"}, (20.0, 20.0)),
    (
        "explicit overrides",
        {
            "DISCODATA_TIMEOUT": "20",
            "DISCODATA_CONNECT_TIMEOUT": "1.5",
            "DISCODATA_READ_TIMEOUT": "60",
        },
        (1.5, 60.0),
    ),
    (
        "invalid override keeps shared fallback",
        {"DISCODATA_TIMEOUT": "20", "DISCODATA_READ_TIMEOUT": "abc"},
        (20.0, 20.0),
    ),
    ("invalid shared fallback", {"DISCODATA_TIMEOUT": "abc"}, (5.0, 30.0)),
] + [
    (
        f"invalid {value}",
        {"DISCODATA_CONNECT_TIMEOUT": value, "DISCODATA_READ_TIMEOUT": value},
        (5.0, 30.0),
    )
    for value in ("abc", "0", "-5", "nan", "inf")
]


class ProviderOutcomeTest(unittest.TestCase):
    """Verify the Discodata provider outcome contract."""

    def setUp(self):
        componentSetUp()
        provideUtility(RegistryStub(), IRegistry)
        self.addCleanup(componentTearDown)
        env = patch.dict(os.environ, _discodata_env({}), clear=True)
        env.start()
        self.addCleanup(env.stop)
        parser = patch(f"{MODULE}.parseQuery", return_value=copy.deepcopy(SQL))
        parser.start()
        self.addCleanup(parser.stop)

    def _provider(self):
        context = SimpleNamespace(
            sql_query="SELECT * FROM t",
            endpoint_url=ENDPOINT,
            readme=README,
        )
        return DataProviderForConnectors(context, object())

    def _fetch(self, exception):
        provider = self._provider()
        if exception is None:
            return provider.provided_data, None
        with self.assertRaises(exception) as caught:
            _ = provider.provided_data
        return None, caught.exception

    def test_provider_outcomes(self):
        for name, outcome, exception, results, status, level, message in OUTCOMES:
            with self.subTest(name):
                with patch(f"{MODULE}.requests.post") as post:
                    if isinstance(outcome, Exception):
                        post.side_effect = outcome
                    else:
                        post.return_value = outcome
                    if level:
                        with self.assertLogs(MODULE, level=level) as logs:
                            data, caught = self._fetch(exception)
                        self.assertIn(message, "\n".join(logs.output))
                    else:
                        data, caught = self._fetch(exception)
                    self.assertEqual(post.call_args.args[0], ENDPOINT)
                    self.assertEqual(post.call_args.kwargs["timeout"], (5.0, 30.0))

                if caught is None:
                    self.assertEqual(data["results"], results)
                    self.assertEqual(data["metadata"], {"readme": README})
                else:
                    response = HTTPResponse()
                    response.setStatus(type(caught))
                    self.assertEqual(response.status, status)


class TimeoutConfigTest(unittest.TestCase):
    """Verify the Discodata timeout configuration."""

    def test_timeouts_from_environment(self):
        for name, env, expected in TIMEOUT_CONFIG:
            environ = patch.dict(os.environ, _discodata_env(env), clear=True)
            with self.subTest(name), environ:
                self.assertEqual(_get_discodata_timeouts(), expected)


class StubDataProvider:
    """Provider adapter returning queued outcomes and counting calls."""

    outcomes: ClassVar[list] = []
    calls: ClassVar[int] = 0

    def __init__(self, context, request):
        self.context = context
        self.request = request

    @property
    def provided_data(self):
        StubDataProvider.calls += 1
        outcome = StubDataProvider.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class ConnectorRequest(dict):
    """Minimal request double with a form mapping."""

    form: ClassVar[dict] = {}


class CacheImmunityTest(unittest.TestCase):
    """Verify provider failures never populate the connector data cache."""

    def setUp(self):
        componentSetUp()
        provideAdapter(
            StubDataProvider,
            (IConnectorDataProvider, Interface),
            IDataProvider,
            name="connector",
        )
        StubDataProvider.outcomes = []
        StubDataProvider.calls = 0
        ram.global_cache.invalidateAll()

    def tearDown(self):
        ram.global_cache.invalidateAll()
        componentTearDown()

    def _connector(self):
        context = SimpleNamespace(
            absolute_url=lambda: "http://example.com/provider",
            getPhysicalPath=lambda: ("", "site", "provider"),
        )
        alsoProvides(context, IConnectorDataProvider)
        return ConnectorData(context, ConnectorRequest())

    def test_failure_is_not_cached(self):
        StubDataProvider.outcomes = [
            BadGateway("Discodata failed"),
            {"results": {}, "metadata": {}},
        ]
        connector = self._connector()

        with self.assertRaises(BadGateway):
            connector(expand=True)

        self.assertEqual(StubDataProvider.calls, 1)
        self.assertEqual(
            connector(expand=True)["connector-data"]["data"],
            {"results": {}, "metadata": {}},
        )
        self.assertEqual(StubDataProvider.calls, 2)

    def test_successful_results_are_cached(self):
        payloads = [
            {"results": {}, "metadata": {}},
            {"results": {"a": [1]}, "metadata": {"readme": README}},
        ]
        for payload in payloads:
            with self.subTest(results=payload["results"]):
                StubDataProvider.outcomes = [payload]
                StubDataProvider.calls = 0
                ram.global_cache.invalidateAll()
                connector = self._connector()

                first = connector(expand=True)["connector-data"]["data"]
                second = connector(expand=True)["connector-data"]["data"]

                self.assertEqual(first, payload)
                self.assertEqual(second, payload)
                self.assertEqual(StubDataProvider.calls, 1)


class EmptyProviderDataTest(unittest.TestCase):
    """Verify empty providers preserve the public connector-data shape."""

    def test_connector_without_sql_query(self):
        context = SimpleNamespace(
            sql_query="",
            endpoint_url=ENDPOINT,
            readme=README,
        )

        data = DataProviderForConnectors(context, object()).provided_data

        self.assertEqual(
            data,
            {
                "results": {},
                "metadata": {"readme": README},
            },
        )

    @patch("eea.api.dataconnector.behavior.json_body", return_value={"form": {}})
    def test_file_provider_without_file(self, json_body):
        context = SimpleNamespace(file=None)

        data = DataProviderForFiles(context, object()).provided_data

        self.assertEqual(data, {"results": {}, "metadata": {}})
        json_body.assert_called()

    @patch("eea.api.dataconnector.behavior.json_body", return_value={"form": {}})
    def test_file_provider_without_rows(self, json_body):
        context = SimpleNamespace(file=SimpleNamespace(data=b""))

        data = DataProviderForFiles(context, object()).provided_data

        self.assertEqual(data, {"results": {}, "metadata": {}})
        json_body.assert_called()


def test_suite():
    """Test suite."""
    return unittest.defaultTestLoader.loadTestsFromName(__name__)
