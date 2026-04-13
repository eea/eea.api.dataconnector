"""Unit tests for eea.api.dataconnector.queryfilter module

These tests cover pure filter functions that don't require Plone context:
- _equal
- _contains
- _gte
- _all
- filteredData
"""

import unittest
from eea.api.dataconnector.queryfilter import Filter, _equal, _contains, _gte, _all, filteredData


class TestEqual(unittest.TestCase):
    """Tests for _equal filter function"""

    def test_equal_string(self):
        f = Filter(index="title", values="test")
        self.assertTrue(_equal(f, {"title": "test"}))

    def test_not_equal_string(self):
        f = Filter(index="title", values="test")
        self.assertFalse(_equal(f, {"title": "other"}))

    def test_equal_with_list_values(self):
        f = Filter(index="title", values=["test1", "test2"])
        self.assertTrue(_equal(f, {"title": "test1"}))

    def test_not_in_list_values(self):
        f = Filter(index="title", values=["test1", "test2"])
        self.assertFalse(_equal(f, {"title": "test3"}))

    def test_none_values_always_true(self):
        f = Filter(index="title", values=None)
        self.assertTrue(_equal(f, {"title": "anything"}))


class TestContains(unittest.TestCase):
    """Tests for _contains filter function"""

    def test_contains_string(self):
        f = Filter(index="title", values="test")
        self.assertTrue(_contains(f, {"title": "test"}))

    def test_contains_list(self):
        f = Filter(index="title", values=["test1", "test2"])
        self.assertTrue(_contains(f, {"title": "test1"}))

    def test_not_contains(self):
        f = Filter(index="title", values=["test1"])
        self.assertFalse(_contains(f, {"title": "test3"}))

    def test_none_values_always_true(self):
        f = Filter(index="title", values=None)
        self.assertTrue(_contains(f, {"title": "anything"}))


class TestGte(unittest.TestCase):
    """Tests for _gte filter function"""

    def test_gte_true(self):
        f = Filter(index="count", values=5)
        self.assertTrue(_gte(f, {"count": 5}))

    def test_gte_greater(self):
        f = Filter(index="count", values=5)
        self.assertTrue(_gte(f, {"count": 10}))

    def test_gte_false(self):
        f = Filter(index="count", values=5)
        self.assertFalse(_gte(f, {"count": 3}))

    def test_gte_none_values(self):
        f = Filter(index="count", values=None)
        self.assertTrue(_gte(f, {"count": 3}))


class TestAll(unittest.TestCase):
    """Tests for _all filter function"""

    def test_all_single_value(self):
        f = Filter(index="title", values="test")
        self.assertTrue(_all(f, {"title": "test"}))

    def test_all_single_value_not_match(self):
        f = Filter(index="title", values="test")
        self.assertFalse(_all(f, {"title": "other"}))

    def test_all_list_all_match(self):
        f = Filter(index="title", values=["test"])
        self.assertTrue(_all(f, {"title": "test"}))

    def test_all_list_not_all_match(self):
        f = Filter(index="title", values=["test1", "test2"])
        self.assertFalse(_all(f, {"title": "test1"}))

    def test_all_none_values(self):
        f = Filter(index="title", values=None)
        self.assertTrue(_all(f, {"title": "anything"}))


class TestFilteredData(unittest.TestCase):
    """Tests for filteredData function"""

    def test_empty_data(self):
        result = filteredData([], [])
        self.assertEqual(result, {})

    def test_none_data(self):
        result = filteredData(None, [])
        self.assertEqual(result, {})

    # Note: filteredData with actual data calls allow() which needs
    # IRegistry from Plone, so those tests need integration testing


class TestFilter(unittest.TestCase):
    """Tests for Filter namedtuple"""

    def test_filter_creation(self):
        f = Filter(index="title", values="test")
        self.assertEqual(f.index, "title")
        self.assertEqual(f.values, "test")

    def test_filter_index_access(self):
        f = Filter(index="title", values="test")
        self.assertEqual(f[0], "title")
        self.assertEqual(f[1], "test")


if __name__ == "__main__":
    unittest.main()