from plone.registry.interfaces import IRegistry
from collections import namedtuple
from zope.component import getUtility
from zope.dottedname.resolve import resolve

Filter = namedtuple("Filter", ["index", "values"])


def allow(filters, row, keys):
    """allow filter"""
    reg = getUtility(IRegistry)
    for filter in filters:
        operator = filter.get("o", None)
        index = filter.get("i", None)
        value = filter.get("v", None)
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
        filter = Filter(index=index, values=value)
        filterFunc = resolve(function_path)
        if not filterFunc(filter, row):
            return False
    return True


def filteredData(data, filters):
    """filter data based on form filters"""
    if not len(data):
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


def _eq(filter, row):
    """equal filter"""
    # return _default(row)
    return True


def _ne(filter, row):
    """not equal filter"""
    # return _default(row, 'ne')
    return True


def _like(filter, row):
    """like filter"""
    # return _default(row, 'like')
    return True


def _not_like(filter, row):
    """not like filter"""
    # return _default(row, 'not_like')
    return True


def _in(filter, row):
    """in filter"""
    # return _contains(filter, row)
    return True


def _nin(filter, row):
    """not in filter"""
    return True


def _gt(filter, row):
    """greater than filter"""
    # return _default(row, 'gt')
    return True


def _gte(filter, row):
    """greater than equal filter"""
    # return _default(row, 'gte')
    return True


def _lt(filter, row):
    """lower than filter"""
    # return _default(row, 'lt')
    return True


def _lte(filter, row):
    """lower than equal filter"""
    # return _default(row, 'lte')
    return True


# From data query


def _equal(filter, row):
    """equal filter"""
    # return _default(filter, row)
    return True


def _contains(filter, row):
    """contains filter"""
    if not filter.values or len(filter.values) == 0:
        return True
    if type(filter.values) is not list:
        return row[filter.index] == filter.values
    return row[filter.index] in filter.values


def _all(filter, row):
    """all filter"""
    # return _default(filter, row)
    return True


def _intEqual(filter, row):
    """int equal filter"""
    # return _default(filter, row)
    return True


def _isTrue(filter, row):
    """boolean true filter"""
    # index = combine(row.table, row.index)
    return True


def _isFalse(filter, row):
    """boolean false filter"""
    # index = combine(row.table, row.index)
    return True


# def _between(filter, row):
#     To be defined


def _largerThan(filter, row):
    """larger than filter"""
    # return _default(row, 'gt')
    return True


def _intLargerThan(filter, row):
    """int larger than filter"""
    # return _default(row, 'gt')
    return True


def _lessThan(filter, row):
    """less than filter"""
    # return _default(row, 'lt')
    return True


def _intLessThan(filter, row):
    """int less than filter"""
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
