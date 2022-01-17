import re
from moz_sql_parser import format as sql_format
from moz_sql_parser import parse
from plone.registry.interfaces import IRegistry
from plone.restapi.deserializer import json_body
from collections import namedtuple
from zope.component import getUtility
from zope.dottedname.resolve import resolve

Filter = namedtuple('Filter', ['index', 'values'])

def allow(filters, row, keys):
    reg = getUtility(IRegistry)
    for filter in filters:
        operator = filter.get('o', None)
        index = filter.get('i', None)
        value = filter.get('v', None)
        function_path = operator
        if index not in keys:
            continue
        if 'eea.api.dataconnector.queryparser' not in operator:
            function_path = reg["%s.operation" % operator].replace('plone.app.querystring.queryparser', 'eea.api.dataconnector.queryfilter')
        else:
            function_path = operator.replace('eea.api.dataconnector.queryparser', 'eea.api.dataconnector.queryfilter')
        filter = Filter(index=index,
                values=value)
        filterFunc = resolve(function_path)
        if not filterFunc(filter, row):
            return False
    return True


def filteredData(data, filters):
    if not len(data): return {}
    results = {}
    keys = data[0].keys()
    for row in data:
        if allow(filters, row, keys):
            # Change orientation
            # TO DO: in-memory built, should optimize
            for key in keys:
                if key not in results:
                    results[key] = []
                results[key].append(row[key])

    return results

# Filter operations

def _eq(filter, row):
    # return _default(row)
    return True

def _ne(filter, row):
    # return _default(row, 'ne')
    return True

def _like(filter, row):
    # return _default(row, 'like')
    return True

def _not_like(filter, row):
    # return _default(row, 'not_like')
    return True

def _in(filter, row):
    # return _contains(filter, row)
    return True

def _nin(filter, row):
    return True

def _gt(filter, row):
    # return _default(row, 'gt')
    return True

def _gte(filter, row):
    # return _default(row, 'gte')
    return True

def _lt(filter, row):
    # return _default(row, 'lt')
    return True

def _lte(filter, row):
    # return _default(row, 'lte')
    return True

# From data query

def _equal(filter, row):
    # return _default(filter, row)
    return True

def _contains(filter, row):
    if not filter.values or len(filter.values) == 0:
        return True
    if type(filter.values) is not list:
        return row[filter.index] == filter.values
    return row[filter.index] in filter.values

def _all(filter, row):
    # return _default(filter, row)
    return True

def _intEqual(filter, row):
    # return _default(filter, row)
    return True

def _isTrue(filter, row):
    # index = combine(row.table, row.index)
    return True

def _isFalse(filter, row):
    # index = combine(row.table, row.index)
    return True

# def _between(filter, row):
#     To be defined

def _largerThan(filter, row):
    # return _default(row, 'gt')
    return True


def _intLargerThan(filter, row):
    # return _default(row, 'gt')
    return True


def _lessThan(filter, row):
    # return _default(row, 'lt')
    return True


def _intLessThan(filter, row):
    # return _default(row, 'lt')
    return True


# def _currentUser(filter, row):
#     To be defined


# def _showInactive(filter, row):
#     To be defined


# def _lessThanRelativeDate(filter, row):
#     To be defined


# def _moreThanRelativeDate(filter, row):
#     To be defined


# def _betweenDates(filter, row):
#     To be defined


# def _today(filter, row):
#     To be defined


# def _afterToday(filter, row):
#     To be defined


# def _beforeToday(filter, row):
#     To be defined


# def _beforeRelativeDate(filter, row):
#     To be defined


# def _afterRelativeDate(filter, row):
#     To be defined

# def _pathByRoot(root, row):
#     To be defined


# def _absolutePath(filter, row):
#     To be defined


# def _navigationPath(filter, row):
#     To be defined

# def _relativePath(filter, row):
#     To be defined


# def _referenceIs(filter, row):
#     To be defined