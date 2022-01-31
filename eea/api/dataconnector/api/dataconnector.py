# -*- coding: utf-8 -*-
""" dataconnector """

from eea.api.dataconnector.interfaces import IBasicDataProvider
from eea.api.dataconnector.interfaces import IDataProvider
from plone.restapi.interfaces import IExpandableElement
from plone.restapi.services import Service
from zope.component import adapter
from zope.component import getMultiAdapter
from zope.interface import implementer
from zope.interface import Interface


@implementer(IExpandableElement)
@adapter(IBasicDataProvider, Interface)
class ConnectorData(object):
    """connector data"""

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, expand=False):
        result = {
            "connector-data": {
                "@id": "{}/@connector-data".format(self.context.absolute_url())
            }
        }

        if not expand:
            return result

        connector = getMultiAdapter((self.context, self.request), IDataProvider)
        result["connector-data"]["data"] = connector.provided_data

        return result


class ConnectorDataGet(Service):
    """connector data - get"""

    def reply(self):
        """reply"""
        data = ConnectorData(self.context, self.request)

        return data(expand=True)["connector-data"]


class ConnectorDataPost(Service):
    """connector data - post"""

    def reply(self):
        """reply"""
        result = ConnectorData(self.context, self.request)(expand=True)

        return result["connector-data"]
