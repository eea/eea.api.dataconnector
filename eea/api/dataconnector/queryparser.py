""" queryparser module """
import re
from collections import namedtuple
from mo_sql_parsing import parse_sqlserver as parse
from plone.registry.interfaces import IRegistry
from plone.restapi.deserializer import json_body
from zope.component import getUtility
from zope.dottedname.resolve import resolve

Row = namedtuple("Row", ["index", "values", "table", "collate"])


def parseQuery(context, request):
    """parse query"""
    reg = getUtility(IRegistry)
    conditions = []
    form = request.form or {}
    body_form = json_body(request).get("form", {})
    data_query = json_body(request).get("data_query", [])
    # Update form with body form
    form.update(body_form)
    # Compute data_query from form
    form_data_query = getDataQuery(form)
    # Merge queries
    _data_query = mergeLists(data_query, form_data_query)
    # Parse sql query
    db_version = form.get("db_version") or "latest"
    sql_parsed = getParsedSQLQuery(context, db_version)
    # Get extra conditions
    extra_conditions = form.get("extra_conditions", [])
    # Get context properties
    parameters = getParameters(context.parameters)
    required_parameters = context.required_parameters
    collate = context.collate
    # Get indexes
    __data_query = []
    __indexes = []

    for row in _data_query:
        _index = row.get("i")
        if not parameters:
            break
        if _index not in parameters:
            continue
        __data_query.append(row)
        __indexes.append(_index)

    # Check if required parameters exists in data_query
    if not hasRequiredParameters(required_parameters, __indexes):
        return None

    for row in __data_query:
        operator = row.get("o", None)
        index = row.get("i", None)
        value = row.get("v", None)
        table = parameters.get(index) if parameters else None
        function_path = operator
        if "eea.api.dataconnector.queryparser" not in operator:
            function_path = reg["%s.operation" % operator].replace(
                "plone.app.querystring", "eea.api.dataconnector"
            )
        row = Row(index=index, values=value, table=table, collate=collate)
        parser = resolve(function_path)
        condition = parser(row)
        if condition:
            if isinstance(condition, list):
                condition = {"and": condition}
            conditions.append(condition)
    conditions += extra_conditions

    return {
        "query": sql_parsed,
        "conditions": conditions,
        "form": form,
        "data_query": _data_query,
    }


# Helpers
def mergeLists(list_1, list_2):
    """merge lists"""
    new_list = list_1
    for item in list_2:
        if item not in new_list:
            new_list.append(item)
    return new_list


def combine(str_1, str_2):
    """combine two strings as table.param"""
    if str_1 and str_2:
        return "{}.{}".format(str_1, str_2)
    return str_2


def getParsedSQLQuery(context, db_version):
    """get parsed sql query"""
    return parse(
        re.sub(
            r"\/\*[\s\S]*?\*\/",
            "",
            context.sql_query.replace("DB_VERSION", db_version),
        )
    )


def hasRequiredParameters(required_parameters, parameters):
    """check if required_parameters are satisfied"""
    if not required_parameters:
        return True
    for param in required_parameters:
        if param not in parameters:
            return False
    return True


def getValue(form, parameter):
    """get value from request form"""
    value = None
    field = parameter.get("i")
    op = parameter.get("o")
    op = op if op else ""
    composedParameter = field + op
    value = form.get(composedParameter)
    return value


def getParameters(params_expression):
    """get parameters"""
    parameters = {}
    table = None
    param = None
    if not params_expression:
        return None
    for row in params_expression:
        expression = row.split("*")
        if len(expression) == 1:
            table = ""
            param = row
        elif len(expression) == 2:
            table = expression[0]
            param = expression[1]
        if param:
            parameters[param] = table
    return parameters


def getDataQuery(form):
    """get data query"""
    data = []
    for expression in form:
        value = form.get(expression)
        op = re.search(
            r"\b(gt|gte|lt|lte|eq|ne|in|nin|like|not_like)\b", expression
        )
        index = re.sub(
            r"\[(gt|gte|lt|lte|eq|ne|in|nin|like|not_like)\]",
            "",
            expression,
        )
        if op:
            op = op.group()
        elif isinstance(value, list):
            op = "contains"
        else:
            op = "equal"

        data.append(
            {
                "i": index,
                "o": "eea.api.dataconnector.queryparser._" + op,
                "v": value,
            }
        )
    return data


def computeDataQuery(request):
    """compute data_query"""
    form = request.form or {}
    body_form = json_body(request).get("form") or {}
    data_query = json_body(request).get("data_query") or []
    # Update form with body form
    form.update(body_form)
    # Compute data_query from form
    form_data_query = getDataQuery(form)
    # Merge queries
    _data_query = mergeLists(data_query, form_data_query)
    return _data_query


def getWhereStatement(row, op="eq"):
    """get where statement"""
    collate = row.collate
    index = combine(row.table, row.index)
    values = row.values
    if op in ["in", "nin"] and isinstance(row.values, str):
        values = row.values.split(",")
    isList = isinstance(values, list)
    isString = False
    value = None
    if op in ["in", "nin"] and isList:
        value = values
        if isinstance(values[0], str):
            isString = True
    elif isList and len(values) == 1:
        value = values[0]
        if isinstance(values[0], str):
            isString = True
    elif isinstance(values, str):
        value = values
        isString = True
    else:
        value = values
    if isString:
        if collate and op not in ["in", "nin"]:
            return {op: [index, {"collate": [{"literal": value}, collate]}]}
        return {op: [index, {"literal": value}]}
    return {op: [index, value]}


# Query operators


def _default(row, op="eq"):
    """defaupt where statement generator"""
    where_statement = getWhereStatement(row, op)
    if where_statement:
        return where_statement
    if isinstance(row.values, list):
        return [
            _default(
                Row(
                    index=row.index,
                    values=value,
                    table=row.table,
                    collate=row.collate,
                ),
                op,
            )
            for value in row.values
        ]
    return where_statement


# From query string


def _eq(row):
    """equal"""
    return _default(row)


def _ne(row):
    """not equal"""
    return _default(row, "ne")


def _like(row):
    """like"""
    return _default(row, "like")


def _not_like(row):
    """not like"""
    return _default(row, "not_like")


def _in(row):
    """in or contains"""
    return _contains(row)


def _nin(row):
    """not in"""
    return _contains(row, "nin")


def _gt(row):
    """greater than"""
    return _default(row, "gt")


def _gte(row):
    """greater than equal"""
    return _default(row, "gte")


def _lt(row):
    """lower than"""
    return _default(row, "lt")


def _lte(row):
    """lower than equal"""
    return _default(row, "lte")


# From data query


def _equal(row):
    """equal"""
    return _default(row)


def _contains(row, op="in"):
    """in or contains"""
    return getWhereStatement(row, op)


def _all(row):
    """all"""
    return _default(row)


def _intEqual(row):
    """int equal"""
    return _default(row)


def _isTrue(row):
    """boolean true"""
    index = combine(row.table, row.index)
    return {"eq": [index, True]}


def _isFalse(row):
    """boolean false"""
    index = combine(row.table, row.index)
    return {"eq": [index, False]}


# def _between(row):
#     To be defined


def _largerThan(row):
    """larger than"""
    return _default(row, "gt")


def _intLargerThan(row):
    """int larger than"""
    return _default(row, "gt")


def _lessThan(row):
    """less than"""
    return _default(row, "lt")


def _intLessThan(row):
    """int less than"""
    return _default(row, "lt")


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
