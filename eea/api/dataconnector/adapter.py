""" behavior module """

import logging

import requests
from moz_sql_parser import format as sql_format
from plone.memoize import ram
from zope.component import adapter
from zope.interface import implementer
from zope.publisher.interfaces.browser import IBrowserRequest

from eea.api.dataconnector.interfaces import (
    IConnectorDataProvider,
    IDataProvider,
)
from eea.restapi.utils import timing

from eea.api.dataconnector.queryparser import parseQuery
from eea.api.dataconnector.queryfilter import filteredData

logger = logging.getLogger(__name__)


@adapter(IConnectorDataProvider, IBrowserRequest)
@implementer(IDataProvider)
class DataProviderForConnectors(object):
    """data provider for connectors"""

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def _get_metadata(self):
        """_get_metadata."""
        return {"readme": self.context.readme}

    @timing
    def _get_data(self):
        """_get_data."""
        data = {}
        metadata = self._get_metadata()
        sql = parseQuery(self.context, self.request)

        if not sql:
            return {"results": [], "metadata": metadata}

        conditions = sql.get("conditions")
        data_query = sql.get("data_query")
        form = sql.get("form")
        query = sql.get("query")

        if "where" in query and conditions:
            query["where"] = {"and": conditions + [query["where"]]}
        elif "where" not in query and len(conditions) > 1:
            query["where"] = {"and": conditions}
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
            data = {"results": [], "metadata": metadata}

        if "errors" in data:
            return {"results": [], "metadata": metadata}

        # This will also change orientation
        return {
            "results": filteredData(data["results"], data_query),
            "metadata": metadata,
        }

    # TO DO: persistent caching, periodical refresh, etc
    @ram.cache(lambda func, self: (self.context.modified(), self.request.form))
    def _provided_data(self):
        """provided data"""
        if not self.context.sql_query:
            return []
        return self._get_data()

    @property
    def provided_data(self):
        """provided data"""
        return self._provided_data()
