"""Tests for canonical connector request payloads."""

import unittest

from eea.api.dataconnector.payload import canonical_form


class TestCanonicalForm(unittest.TestCase):
    """Tests for canonical_form."""

    def test_excludes_only_rest_expansion_parameters(self):
        self.assertEqual(
            canonical_form(
                {
                    "expand": "",
                    "expand.navigation.depth": "3",
                    "facilityLocalId": "5000671",
                    "expander": "preserved",
                }
            ),
            {
                "facilityLocalId": "5000671",
                "expander": "preserved",
                "db_version": "latest",
            },
        )

    def test_body_values_override_url_values(self):
        self.assertEqual(
            canonical_form(
                {"facilityLocalId": "old", "db_version": "v1"},
                {
                    "facilityLocalId": "new",
                    "db_version": "v2",
                    "expand": "navigation",
                },
            ),
            {"facilityLocalId": "new", "db_version": "v2"},
        )

    def test_omitted_and_empty_db_version_mean_latest(self):
        self.assertEqual(canonical_form({}), {"db_version": "latest"})
        self.assertEqual(
            canonical_form({"db_version": ""}),
            {"db_version": "latest"},
        )
