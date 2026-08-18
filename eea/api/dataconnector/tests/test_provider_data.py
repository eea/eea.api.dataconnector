"""Tests for empty connector and file provider responses."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from eea.api.dataconnector.adapter import DataProviderForConnectors
from eea.api.dataconnector.behavior import DataProviderForFiles


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


def test_suite():
    """Test suite."""
    return unittest.defaultTestLoader.loadTestsFromName(__name__)
