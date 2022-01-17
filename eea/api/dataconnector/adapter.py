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

from eea.api.dataconnector.interfaces import IConnectorDataProvider, \
    IDataProvider
from eea.restapi.utils import timing

from eea.api.dataconnector.queryparser import parseQuery
from eea.api.dataconnector.queryfilter import filteredData

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
        data = {}
        sql = parseQuery(self.context, self.request)

        if not sql:
            return {"results": []}

        conditions = sql.get('conditions')
        data_query = sql.get('data_query')
        form = sql.get('form')
        query = sql.get('query')

        if "where" in query and conditions:
            query["where"] = {"and": conditions + [query["where"]]}
        elif "where" not in query and len(conditions) > 1:
            query["where"] = {'and': conditions}
        elif len(conditions) == 1:
           query["where"] = conditions[0]

        data["query"] = sql_format(query)

        if form.get("p"):
            data["p"] = form.get("p")

        if form.get("nrOfHits"):
            data["nrOfHits"] = form.get("nrOfHits")

        try:
            req = requests.post(self.context.endpoint_url, data)
            data = req.json()
        except Exception:
            logger.exception("Error in requestion data")
            data = {"results": []}

        if "errors" in data:
            return {"results": []}

        # This will also change orientation
        return filteredData(data['results'], data_query)


    # TO DO: persistent caching, periodical refresh, etc
    # @ram.cache(lambda func, self: (self.context.modified(), self.request.form))
    def _provided_data(self):
        """ provided data """
        if not self.context.sql_query:
            return []
        return self._get_data()

    @property
    def provided_data(self):
        """ provided data """
        return self._provided_data()
