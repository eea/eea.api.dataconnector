import re
from moz_sql_parser import format as sql_format
from moz_sql_parser import parse
from plone.registry.interfaces import IRegistry
from plone.restapi.deserializer import json_body
from collections import namedtuple
from zope.component import getUtility
from zope.dottedname.resolve import resolve

Row = namedtuple('Row', ['index', 'values', 'table', 'collate'])

def parseQuery(context, request):
    reg = getUtility(IRegistry)
    conditions = []
    form = request.form or {}
    body_form = json_body(request).get('form') or {}
    data_query = json_body(request).get('data_query') or []
    # Update form with body form
    form.update(body_form)
    # Compute data_query from form
    form_data_query = getDataQuery(form)
    # Merge queries
    _data_query = mergeLists(data_query, form_data_query)
    # Parse sql query
    db_version = form.get('db_version') or 'latest'
    sql_parsed = getParsedSQLQuery(context, db_version)
    # Get context properties
    parameters = context.parameters
    required_parameters = context.required_parameters
    namespace = context.namespace
    collate = context.collate
    # Get indexes
    __data_query = []
    __indexes = []

    for row in _data_query:
        _index = row.get('i')
        _namespace = row.get('ns')
        if not parameters:
            break
        if namespace and namespace is not _namespace:
            continue
        if _index not in parameters:
            continue
        __data_query.append(row)
        __indexes.append(_index)

    # Check if required parameters exists in data_query
    if not hasRequiredParameters(required_parameters, __indexes):
        return None

    for row in __data_query:
        operator = row.get('o', None)
        index = row.get('i', None)
        value = row.get('v', None)
        table = row.get('t', None)
        function_path = operator
        if 'eea.api.dataconnector.queryparser' not in operator:
            function_path = reg["%s.operation" % operator].replace('plone.app.querystring', 'eea.api.dataconnector')
        row = Row(index=index,
                values=value,
                table=table,
                collate=collate)
        parser = resolve(function_path)
        condition = parser(row)
        if type(condition) is list:
            condition = {'and': condition}
        conditions.append(condition)

    return {
        "query": sql_parsed,
        "conditions": conditions,
    }

# Helpers
def mergeLists(list_1, list_2):
    new_list = list_1
    for item in list_2:
        if item not in new_list:
            new_list.append(item)
    return new_list

def combine(str_1, str_2):
    if str_1 and str_2:
        return str_1 + '.' + str_2
    return str_2

def getParsedSQLQuery(context, db_version):
    return parse(
        re.sub(
            r"\/\*[\s\S]*?\*\/",
            "",
            context.sql_query.replace("DB_VERSION", db_version),
        )
    )

def hasRequiredParameters(required_parameters, parameters):
    if not required_parameters:
        return True
    for param in required_parameters:
        if param not in parameters:
            return False
    return True

def getValue(form, parameter, namespace):
    """Get value from request form"""
    value = None
    field = parameter.get('i')
    op = parameter.get('o')
    op = op if op else ''
    composedParameter = field + op
    if namespace:
        value = form.get("{}|{}".format(namespace, composedParameter))
    if not value:
        value = form.get(composedParameter)
    return value

def getDataQuery(form):
    data = []
    for expression in form:
        value = form.get(expression)
        op =  re.search(
            r"\b(gt|gte|lt|lte|eq|ne|in|nin|like|not_like)\b", expression
        )
        expression = re.sub(
            r"\[(gt|gte|lt|lte|eq|ne|in|nin|like|not_like)\]",
            "",
            expression,
        ).split("::")
        _expression = []
        namespace = None
        table = None

        if op:
            op = op.group()
        elif type(value) is list:
            op = 'contains'
        else:
            op = 'equal'

        if len(expression) == 1:
            index = expression[0]
        elif len(expression) == 2:
            _expression = expression[0].split('|')
            index = expression[1]

        if len(_expression) == 1:
            table = _expression[0]
        elif len(_expression) == 2:
            namespace = _expression[0]
            table = _expression[1]

        data.append({
            'i': index,
            'o': 'eea.api.dataconnector.queryparser._' + op,
            'v': value,
            'ns': namespace,
            't': table or ''
        })
    return data

# Query operators

def _default(row, op = 'eq'):
    collate = row.collate
    index = combine(row.table, row.index)
    if type(row.values) is not list:
        if type(row.values) is str:
            if collate:
                index = {'collate': {index, collate}}
            return {op: [ index, {'literal': row.values}]}
        return {op: [ index, row.values ]}
    if len(row.values) == 1:
        if type(row.values[0]) is str:
            if collate:
                index = {'collate': {index, collate}}
            return {op: [ index, {'literal': row.values[0]}]}
        return {op: [ index, row.values[0] ]}
    else:
        return list(
            map(
                lambda value: _default(
                    Row(
                        index=row.index,
                        values=value,
                        table=row.table,
                        collate=row.collate
                    ),
                    op
                ),
                row.values
            )
        )

# From query string

def _eq(row):
    return _default(row)

def _ne(row):
    return _default(row, 'ne')

def _like(row):
    return _default(row, 'like')

def _not_like(row):
    return _default(row, 'not_like')

def _in(row):
    return _contains(row)

def _nin(row):
    index = combine(row.table, row.index)
    return {'nin': [ index, row.values ]}

def _gt(row):
    return _default(row, 'gt')

def _gte(row):
    return _default(row, 'gte')

def _lt(row):
    return _default(row, 'lt')

def _lte(row):
    return _default(row, 'lte')

# From data query

def _equal(row):
    return _default(row)

def _contains(row):
    index = combine(row.table, row.index)
    return {'in': [ index, row.values ]}

def _all(row):
    return _default(row)

def _intEqual(row):
    return _default(row)

def _isTrue(row):
    index = combine(row.table, row.index)
    return {'eq': [ index, True ]}

def _isFalse(row):
    index = combine(row.table, row.index)
    return {'eq': [ index, False ]}

# def _between(row):
#     To be defined

def _largerThan(row):
    return _default(row, 'gt')


def _intLargerThan(row):
    return _default(row, 'gt')


def _lessThan(row):
    return _default(row, 'lt')


def _intLessThan(row):
    return _default(row, 'lt')


# def _currentUser(row):
#     To be defined


# def _showInactive(row):
#     To be defined


# def _lessThanRelativeDate(row):
#     To be defined


# def _moreThanRelativeDate(row):
#     To be defined


# def _betweenDates(row):
#     To be defined


# def _today(row):
#     To be defined


# def _afterToday(row):
#     To be defined


# def _beforeToday(row):
#     To be defined


# def _beforeRelativeDate(row):
#     To be defined


# def _afterRelativeDate(row):
#     To be defined

# def _pathByRoot(root, row):
#     To be defined


# def _absolutePath(row):
#     To be defined


# def _navigationPath(row):
#     To be defined

# def _relativePath(row):
#     To be defined


# def _referenceIs(row):
#     To be defined