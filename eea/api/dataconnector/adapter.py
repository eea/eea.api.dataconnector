""" behavior module """

import logging

import requests
from eea.restapi.utils import timing
from eea.restapi.interfaces import IConnectorDataProvider
from eea.restapi.interfaces import IDataProvider
from moz_sql_parser import format as sql_format
from moz_sql_parser import parse
from plone.memoize import ram
from zope.component import adapter
from zope.interface import implementer
from zope.publisher.interfaces.browser import IBrowserRequest


logger = logging.getLogger(__name__)


def build_where_statement(wheres, operator="and"):
    """make where statement for moz_sql_parser"""
    if wheres:
        if len(wheres) == 1:
            return wheres[0]
        return {operator: wheres}
    return False


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
        query = parse(self.context.sql_query)
        wheres_list = []
        data = {}

        if self.context.parameters:
            for param in self.context.parameters:
                value = None

                if self.context.namespace:
                    value = form.get(
                        "{}:{}".sql_format(self.context.namespace, param)
                    )

                if not value:
                    value = form.get(param)

                if isinstance(value, list):
                    or_wheres_list = [
                        {"eq": [param, {"literal": str(item)}]}
                        for item in value
                    ]
                    or_wheres = build_where_statement(or_wheres_list, "or")
                    if or_wheres:
                        wheres_list.append(or_wheres)
                elif value:
                    wheres_list.append(
                        {"eq": [param, {"literal": str(value)}]}
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
    @ram.cache(lambda func, self: (self.context.modified(), self.request.form))
    def _provided_data(self):
        """ provided data """
        if not self.context.sql_query:
            return []

        data = self._get_data()

        return self.change_orientation(data["results"])

    @property
    def provided_data(self):
        """ provided data """
        return self._provided_data()
