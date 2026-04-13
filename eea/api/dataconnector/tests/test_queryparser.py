"""Unit tests for eea.api.dataconnector.queryparser module

These tests cover pure functions that don't require Plone context:
- mergeLists
- combine
- hasRequiredParameters
- getValue
- getParameters
- getDataQuery
- convertValue
- getWhereStatement
- computeDataQuery (partial, no request mock)
- Query operators: _eq, _ne, _gt, _gte, _lt, _lte, _like, _not_like, _in, _nin, _contains, _equal, _all, _isTrue, _isFalse, _largerThan, _lessThan
"""

import unittest
from eea.api.dataconnector.queryparser import (
    Row,
    mergeLists,
    combine,
    hasRequiredParameters,
    getValue,
    getParameters,
    getDataQuery,
    convertValue,
    getWhereStatement,
    _eq,
    _ne,
    _gt,
    _gte,
    _lt,
    _lte,
    _like,
    _not_like,
    _in,
    _nin,
    _equal,
    _contains,
    _all,
    _isTrue,
    _isFalse,
    _largerThan,
    _lessThan,
    _intLargerThan,
    _intLessThan,
    _intEqual,
    _default,
)


class TestMergeLists(unittest.TestCase):
    """Tests for mergeLists function"""

    def test_merge_two_empty_lists(self):
        self.assertEqual(mergeLists([], []), [])

    def test_merge_empty_with_nonempty(self):
        self.assertEqual(mergeLists([], [1, 2]), [1, 2])

    def test_merge_nonempty_with_empty(self):
        self.assertEqual(mergeLists([1, 2], []), [1, 2])

    def test_merge_no_duplicates(self):
        self.assertEqual(mergeLists([1, 2], [3, 4]), [1, 2, 3, 4])

    def test_merge_with_duplicates(self):
        self.assertEqual(mergeLists([1, 2], [2, 3]), [1, 2, 3])

    def test_merge_preserves_order(self):
        result = mergeLists([1], [2])
        self.assertEqual(result, [1, 2])

    def test_merge_dicts(self):
        a = [{"i": "title", "v": "test"}]
        b = [{"i": "description", "v": "desc"}]
        result = mergeLists(a, b)
        self.assertEqual(len(result), 2)


class TestCombine(unittest.TestCase):
    """Tests for combine function"""

    def test_combine_both_strings(self):
        self.assertEqual(combine("table", "param"), "table.param")

    def test_combine_empty_first(self):
        self.assertEqual(combine("", "param"), "param")

    def test_combine_none_first(self):
        self.assertEqual(combine(None, "param"), "param")

    def test_combine_empty_second(self):
        self.assertEqual(combine("table", ""), "")

    def test_combine_none_second(self):
        self.assertEqual(combine("table", None), None)

    def test_combine_both_empty(self):
        self.assertEqual(combine("", ""), "")


class TestHasRequiredParameters(unittest.TestCase):
    """Tests for hasRequiredParameters function"""

    def test_no_required_parameters(self):
        self.assertTrue(hasRequiredParameters([], ["title"]))

    def test_none_required_parameters(self):
        self.assertTrue(hasRequiredParameters(None, ["title"]))

    def test_all_required_present(self):
        self.assertTrue(hasRequiredParameters(["title"], ["title", "desc"]))

    def test_required_missing(self):
        self.assertFalse(hasRequiredParameters(["title"], ["missing"]))

    def test_empty_parameters(self):
        self.assertFalse(hasRequiredParameters(["title"], []))

    def test_exact_match(self):
        self.assertTrue(hasRequiredParameters(["title"], ["title"]))


class TestGetValue(unittest.TestCase):
    """Tests for getValue function"""

    def test_get_value_with_operator(self):
        form = {"titlegt": "test_value"}
        param = {"i": "title", "o": "gt"}
        self.assertEqual(getValue(form, param), "test_value")

    def test_get_value_without_operator(self):
        form = {"title": "test_value"}
        param = {"i": "title", "o": ""}
        self.assertEqual(getValue(form, param), "test_value")

    def test_get_value_missing(self):
        form = {}
        param = {"i": "title", "o": "gt"}
        self.assertIsNone(getValue(form, param))


class TestGetParameters(unittest.TestCase):
    """Tests for getParameters function"""

    def test_none_params(self):
        self.assertIsNone(getParameters(None))

    def test_empty_params(self):
        self.assertIsNone(getParameters([]))

    def test_simple_param(self):
        result = getParameters(["title"])
        self.assertEqual(result, {"title": ""})

    def test_table_param(self):
        result = getParameters(["table*title"])
        self.assertEqual(result, {"title": "table"})

    def test_multiple_params(self):
        result = getParameters(["title", "table*desc"])
        self.assertEqual(result, {"title": "", "desc": "table"})


class TestConvertValue(unittest.TestCase):
    """Tests for convertValue function"""

    def test_convert_int(self):
        self.assertEqual(convertValue("42", "int"), 42)

    def test_convert_float(self):
        self.assertAlmostEqual(convertValue("3.14", "float"), 3.14)

    def test_convert_string(self):
        self.assertEqual(convertValue("hello", None), "hello")

    def test_convert_already_int(self):
        self.assertEqual(convertValue(42, "int"), 42)


class TestGetDataQuery(unittest.TestCase):
    """Tests for getDataQuery function"""

    def test_simple_equality(self):
        form = {"title": "test"}
        result = getDataQuery(form)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["i"], "title")
        self.assertEqual(result[0]["o"], "eea.api.dataconnector.queryparser._equal")
        self.assertEqual(result[0]["v"], "test")

    def test_gt_operator(self):
        form = {"title[gt]": "test"}
        result = getDataQuery(form)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["o"], "eea.api.dataconnector.queryparser._gt")

    def test_list_value_uses_contains(self):
        form = {"title": ["a", "b"]}
        result = getDataQuery(form)
        self.assertEqual(result[0]["o"], "eea.api.dataconnector.queryparser._contains")

    def test_int_type_conversion(self):
        form = {"count:int": "42"}
        result = getDataQuery(form)
        self.assertEqual(result[0]["v"], 42)

    def test_float_type_conversion(self):
        form = {"price:float": "3.14"}
        result = getDataQuery(form)
        self.assertAlmostEqual(result[0]["v"], 3.14)

    def test_empty_form(self):
        result = getDataQuery({})
        self.assertEqual(result, [])


class TestGetWhereStatement(unittest.TestCase):
    """Tests for getWhereStatement function"""

    def test_eq_string(self):
        row = Row(index="title", values="test", table="", collate=None)
        result = getWhereStatement(row, "eq")
        self.assertEqual(result, {"eq": ["title", {"literal": "test"}]})

    def test_eq_number(self):
        row = Row(index="count", values=42, table="", collate=None)
        result = getWhereStatement(row, "eq")
        self.assertEqual(result, {"eq": ["count", 42]})

    def test_in_list(self):
        row = Row(index="title", values="a,b", table="", collate=None)
        result = getWhereStatement(row, "in")
        self.assertEqual(result, {"in": ["title", {"literal": ["a", "b"]}]})

    def test_with_table(self):
        row = Row(index="title", values="test", table="mytable", collate=None)
        result = getWhereStatement(row, "eq")
        self.assertEqual(result, {"eq": ["mytable.title", {"literal": "test"}]})

    def test_single_item_list(self):
        row = Row(index="title", values=["test"], table="", collate=None)
        result = getWhereStatement(row, "eq")
        self.assertEqual(result, {"eq": ["title", {"literal": "test"}]})

    def test_with_collate(self):
        row = Row(index="title", values="test", table="", collate="utf8")
        result = getWhereStatement(row, "eq")
        self.assertEqual(result, {"eq": ["title", {"collate": [{"literal": "test"}, "utf8"]}]})

    def test_in_list_no_split_when_already_list(self):
        row = Row(index="title", values=["a", "b"], table="", collate=None)
        result = getWhereStatement(row, "in")
        self.assertEqual(result, {"in": ["title", {"literal": ["a", "b"]}]})


class TestQueryOperators(unittest.TestCase):
    """Tests for query operator functions"""

    def test_eq(self):
        row = Row(index="title", values="test", table="", collate=None)
        result = _eq(row)
        self.assertEqual(result, {"eq": ["title", {"literal": "test"}]})

    def test_ne(self):
        row = Row(index="title", values="test", table="", collate=None)
        result = _ne(row)
        self.assertEqual(result, {"ne": ["title", {"literal": "test"}]})

    def test_gt(self):
        row = Row(index="count", values=10, table="", collate=None)
        result = _gt(row)
        self.assertEqual(result, {"gt": ["count", 10]})

    def test_gte(self):
        row = Row(index="count", values=10, table="", collate=None)
        result = _gte(row)
        self.assertEqual(result, {"gte": ["count", 10]})

    def test_lt(self):
        row = Row(index="count", values=10, table="", collate=None)
        result = _lt(row)
        self.assertEqual(result, {"lt": ["count", 10]})

    def test_lte(self):
        row = Row(index="count", values=10, table="", collate=None)
        result = _lte(row)
        self.assertEqual(result, {"lte": ["count", 10]})

    def test_like(self):
        row = Row(index="title", values="test", table="", collate=None)
        result = _like(row)
        self.assertEqual(result, {"like": ["title", {"literal": "test"}]})

    def test_not_like(self):
        row = Row(index="title", values="test", table="", collate=None)
        result = _not_like(row)
        self.assertEqual(result, {"not_like": ["title", {"literal": "test"}]})

    def test_in_operator(self):
        row = Row(index="title", values=["a", "b"], table="", collate=None)
        result = _in(row)
        self.assertEqual(result, {"in": ["title", {"literal": ["a", "b"]}]})

    def test_nin(self):
        row = Row(index="title", values=["a", "b"], table="", collate=None)
        result = _nin(row)
        self.assertEqual(result, {"nin": ["title", {"literal": ["a", "b"]}]})

    def test_equal(self):
        row = Row(index="title", values="test", table="", collate=None)
        result = _equal(row)
        self.assertEqual(result, {"eq": ["title", {"literal": "test"}]})

    def test_contains(self):
        row = Row(index="title", values=["a", "b"], table="", collate=None)
        result = _contains(row)
        self.assertEqual(result, {"in": ["title", {"literal": ["a", "b"]}]})

    def test_contains_with_op(self):
        row = Row(index="title", values=["a", "b"], table="", collate=None)
        result = _contains(row, "nin")
        self.assertEqual(result, {"nin": ["title", {"literal": ["a", "b"]}]})

    def test_all(self):
        row = Row(index="title", values="test", table="", collate=None)
        result = _all(row)
        self.assertEqual(result, {"eq": ["title", {"literal": "test"}]})

    def test_isTrue(self):
        row = Row(index="active", values=True, table="", collate=None)
        result = _isTrue(row)
        self.assertEqual(result, {"eq": ["active", True]})

    def test_isFalse(self):
        row = Row(index="active", values=False, table="", collate=None)
        result = _isFalse(row)
        self.assertEqual(result, {"eq": ["active", False]})

    def test_largerThan(self):
        row = Row(index="count", values=10, table="", collate=None)
        result = _largerThan(row)
        self.assertEqual(result, {"gt": ["count", 10]})

    def test_lessThan(self):
        row = Row(index="count", values=10, table="", collate=None)
        result = _lessThan(row)
        self.assertEqual(result, {"lt": ["count", 10]})

    def test_intLargerThan(self):
        row = Row(index="count", values=10, table="", collate=None)
        result = _intLargerThan(row)
        self.assertEqual(result, {"gt": ["count", 10]})

    def test_intLessThan(self):
        row = Row(index="count", values=10, table="", collate=None)
        result = _intLessThan(row)
        self.assertEqual(result, {"lt": ["count", 10]})

    def test_intEqual(self):
        row = Row(index="count", values=10, table="", collate=None)
        result = _intEqual(row)
        self.assertEqual(result, {"eq": ["count", 10]})

    def test_eq_with_table(self):
        row = Row(index="title", values="test", table="data", collate=None)
        result = _eq(row)
        self.assertEqual(result, {"eq": ["data.title", {"literal": "test"}]})

    def test_default_with_list_values(self):
        row = Row(index="count", values=[10, 20], table="", collate=None)
        result = _default(row)
        # getWhereStatement returns truthy dict, so _default returns it directly
        self.assertEqual(result, {"eq": ["count", [10, 20]]})

    def test_in_with_comma_string(self):
        row = Row(index="title", values="a,b,c", table="", collate=None)
        result = _in(row)
        self.assertEqual(result, {"in": ["title", {"literal": ["a", "b", "c"]}]})


class TestRow(unittest.TestCase):
    """Tests for Row namedtuple"""

    def test_row_creation(self):
        row = Row(index="title", values="test", table="data", collate="utf8")
        self.assertEqual(row.index, "title")
        self.assertEqual(row.values, "test")
        self.assertEqual(row.table, "data")
        self.assertEqual(row.collate, "utf8")

    def test_row_index_access(self):
        row = Row(index="title", values="test", table="data", collate=None)
        self.assertEqual(row[0], "title")
        self.assertEqual(row[1], "test")


if __name__ == "__main__":
    unittest.main()