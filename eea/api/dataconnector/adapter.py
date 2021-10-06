""" behavior module """

import logging

import re
import requests
from moz_sql_parser import format as sql_format
from moz_sql_parser import parse
from plone.memoize import ram
from zope.component import adapter
from zope.interface import implementer
from zope.publisher.interfaces.browser import IBrowserRequest

from eea.restapi.interfaces import IConnectorDataProvider, IDataProvider
from eea.restapi.utils import timing

logger = logging.getLogger(__name__)


def build_where_statement(wheres, operator="and"):
    """make where statement for moz_sql_parser"""
    if wheres:
        if len(wheres) == 1:
            return wheres[0]
        return {operator: wheres}
    return False


def has_required_parameters(request, context):
    """Check if required_parameters exists in form"""

    if not context.required_parameters:
        return True

    for param in context.required_parameters:
        value = None
        if context.namespace:
            value = request.form.get("{}.{}".format(context.namespace, param))
        if not value:
            value = request.form.get(param)
        if not value:
            return False
    return True


def get_param(param, value, collate):
    """Get param with corresponding table and collate"""
    if collate and isinstance(value, str):
        return {"collate": [param, collate]}
    return param


def get_value(form, namespace, field):
    """Get value from request form"""
    value = None
    if namespace:
        value = form.get("{}*{}".format(namespace, field))
    if not value:
        value = form.get(field)
    return value


@adapter(IConnectorDataProvider, IBrowserRequest)
@implementer(IDataProvider)
class DataProviderForConnectors(object):
    """ data provider for connectors """

    def __init__(self, context, request):
        self.context = context
        self.request = request

    @timing
    def _get_data(self):
        """_get_data."""
        # query = urllib.parse.quote_plus(self.query)

        form = self.request.form
        db_version = (
            get_value(form, self.context.namespace, "db_version") or "latest"
        )
        query = parse(
            re.sub(
                r"\/\*[\s\S]*?\*\/",
                "",
                self.context.sql_query.replace("DB_VERSION", db_version),
            )
        )
        collate = self.context.collate
        wheres_list = []
        data = {}

        if self.context.parameters:
            for param_expression in self.context.parameters:
                # A param can have this structure table*field[op]
                # so we need to separate the table and operation from field[op]
                param = re.sub(
                    r"\[(gt|gte|lt|lte|eq|ne|in|nin|like)\]",
                    "",
                    param_expression,
                )
                op = re.search(
                    r"\b(gt|gte|lt|lte|eq|ne|in|nin|like)\b", param_expression
                )
                op = op.group() if op else "eq"
                field = param_expression.split("*")

                if len(field) > 1:
                    field = ".".join(field[1:])
                elif len(field) == 1:
                    field = field[0]

                param = param.replace("*", ".")            
                value = get_value(form, self.context.namespace, field)

                if re.search(r"(eq|ne|like)", op) and isinstance(value, list):
                    or_wheres_list = [
                        {
                            op: [
                                get_param(param, value, collate),
                                {
                                    "literal": "%" + item + "%"
                                    if op == "like"
                                    else item
                                },
                            ]
                        }
                        for item in value
                    ]
                    or_wheres = build_where_statement(or_wheres_list, "or")
                    if or_wheres:
                        wheres_list.append(or_wheres)
                elif value:
                    wheres_list.append(
                        {
                            op: [
                                get_param(param, value, collate),
                                {
                                    "literal": "%" + value + "%"
                                    if op == "like"
                                    else value
                                },
                            ]
                        }
                    )

        wheres = build_where_statement(wheres_list, "and")

        if "where" in query and wheres:
            query["where"] = {"and": [query["where"], wheres]}
        elif "where" not in query and wheres:
            query["where"] = wheres

        data["query"] = sql_format(query)

        if form.get("p"):
            data["p"] = form.get("p")

        if form.get("nrOfHits"):
            data["nrOfHits"] = form.get("nrOfHits")

        try:
            req = requests.post(self.context.endpoint_url, data)
            res = req.json()
        except Exception:
            logger.exception("Error in requestion data")
            res = {"results": []}

        if "errors" in res:
            return {"results": []}

        return res

    def change_orientation(self, data):
        """ change orientation """
        res = {}

        if not data:
            return res

        keys = data[0].keys()

        # TO DO: in-memory built, should optimize

        for k in keys:
            res[k] = [row[k] for row in data]

        return res

    # TO DO: persistent caching, periodical refresh, etc
    # @ram.cache(lambda func, self: (self.context.modified(), self.request.form))
    def _provided_data(self):
        """ provided data """
        if not self.context.sql_query:
            return []
        if not has_required_parameters(self.request, self.context):
            return []
        data = self._get_data()

        return self.change_orientation(data["results"])

    @property
    def provided_data(self):
        """ provided data """
        return self._provided_data()
