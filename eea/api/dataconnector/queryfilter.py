""" queryfilter module """
from collections import namedtuple
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from zope.dottedname.resolve import resolve

Filter = namedtuple("Filter", ["index", "values"])


def allow(filters, row, keys):
    """allow filter"""
    reg = getUtility(IRegistry)
    for _filter in filters:
        operator = _filter.get("o", None)
        index = _filter.get("i", None)
        value = _filter.get("v", None)
        function_path = operator
        if index not in keys:
            continue
        if "eea.api.dataconnector.queryparser" not in operator:
            function_path = reg["%s.operation" % operator].replace(
                "plone.app.querystring.queryparser",
                "eea.api.dataconnector.queryfilter",
            )
        else:
            function_path = operator.replace(
                "eea.api.dataconnector.queryparser",
                "eea.api.dataconnector.queryfilter",
            )
        _filter = Filter(index=index, values=value)
        filterFunc = resolve(function_path)
        if not filterFunc(_filter, row):
            return False
    return True


def filteredData(data, filters):
    """filter data based on form filters"""

    if not data:
        return {}
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


def _eq(_filter, row):
    """equal"""
    # return _default(row)
    return True


def _ne(_filter, row):
    """not equal"""
    # return _default(row, 'ne')
    return True


def _like(_filter, row):
    """like"""
    # return _default(row, 'like')
    return True


def _not_like(_filter, row):
    """not like"""
    # return _default(row, 'not_like')
    return True


def _in(_filter, row):
    """in"""
    # return _contains(filter, row)
    return True


def _nin(_filter, row):
    """not in"""
    return True


def _gt(_filter, row):
    """greater than"""
    # return _default(row, 'gt')
    return True


def _gte(_filter, row):
    """greater than equal"""
    # return _default(row, 'gte')
    return True


def _lt(_filter, row):
    """lower than"""
    # return _default(row, 'lt')
    return True


def _lte(_filter, row):
    """lower than equal"""
    # return _default(row, 'lte')
    return True


# From data query


def _equal(_filter, row):
    """equal"""
    if not _filter.values:
        return True
    if not isinstance(_filter.values, list):
        return row[_filter.index] == _filter.values
    return row[_filter.index] in _filter.values


def _contains(_filter, row):
    """contains"""
    if not _filter.values:
        return True
    if not isinstance(_filter.values, list):
        return row[_filter.index] == _filter.values
    return row[_filter.index] in _filter.values


def _all(_filter, row):
    """all TO DO"""
    if not _filter.values:
        return True
    if not isinstance(_filter.values, list):
        return row[_filter.index] == _filter.values
    ok = True
    for value in _filter.values:
        if row[_filter.index] != value:
            ok = False
            break
    return ok


def _intEqual(_filter, row):
    """int equal"""
    # return _default(_filter, row)
    return True


def _isTrue(_filter, row):
    """boolean true"""
    # index = combine(row.table, row.index)
    return True


def _isFalse(_filter, row):
    """boolean false"""
    # index = combine(row.table, row.index)
    return True


# def _between(_filter, row):
#     To be defined


def _largerThan(_filter, row):
    """larger than"""
    # return _default(row, 'gt')
    return True


def _intLargerThan(_filter, row):
    """int larger than"""
    # return _default(row, 'gt')
    return True


def _lessThan(_filter, row):
    """less than"""
    # return _default(row, 'lt')
    return True


def _intLessThan(_filter, row):
    """int less than"""
    # return _default(row, 'lt')
    return True


# def _currentUser(_filter, row):
#     To be defined


# def _showInactive(_filter, row):
#     To be defined


# def _lessThanRelativeDate(_filter, row):
#     To be defined


# def _moreThanRelativeDate(_filter, row):
#     To be defined


# def _betweenDates(_filter, row):
#     To be defined


# def _today(_filter, row):
#     To be defined


# def _afterToday(_filter, row):
#     To be defined


# def _beforeToday(_filter, row):
#     To be defined


# def _beforeRelativeDate(_filter, row):
#     To be defined


# def _afterRelativeDate(_filter, row):
#     To be defined

# def _pathByRoot(root, row):
#     To be defined


# def _absolutePath(_filter, row):
#     To be defined


# def _navigationPath(_filter, row):
#     To be defined

# def _relativePath(_filter, row):
#     To be defined


# def _referenceIs(_filter, row):
#     To be defined
