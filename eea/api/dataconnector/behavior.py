""" behavior module """
import csv
import logging
from collections import defaultdict
from io import StringIO
from plone.app.dexterity.behaviors.metadata import DCFieldProperty
from plone.app.dexterity.behaviors.metadata import MetadataBase
from plone.dexterity.interfaces import IDexterityContent
from plone.rfc822.interfaces import IPrimaryFieldInfo
from zope.component import adapter
from zope.interface import implementer
from zope.publisher.interfaces.browser import IBrowserRequest
from .interfaces import IConnectorDataParameters
from .interfaces import IDataConnector
from .interfaces import IDataProvider
from .interfaces import IDataVisualization
from .interfaces import IFileDataProvider


logger = logging.getLogger(__name__)


@implementer(IDataConnector)
@adapter(IDexterityContent)
class DataConnector(MetadataBase):
    """Allow data connectivity to discodata

    See http://discomap.eea.europa.eu/App/SqlEndpoint/Browser.aspx
    """

    endpoint_url = DCFieldProperty(IDataConnector["endpoint_url"])
    sql_query = DCFieldProperty(IDataConnector["sql_query"])
    parameters = DCFieldProperty(IDataConnector["parameters"])
    namespace = DCFieldProperty(IDataConnector["namespace"])
    required_parameters = DCFieldProperty(
        IDataConnector["required_parameters"]
    )
    collate = DCFieldProperty(IDataConnector["collate"])
    readme = DCFieldProperty(IDataConnector["readme"])


@implementer(IDataProvider)
@adapter(IFileDataProvider, IBrowserRequest)
class DataProviderForFiles(object):
    """Behavior implementation for content types with a File primary field"""

    def __init__(self, context, request):
        self.context = context
        self.request = request

    @property
    def provided_data(self):
        """ provided data """
        field = IPrimaryFieldInfo(self.context)

        if not field.value:
            return []

        text = field.value.data
        f = StringIO(text.decode("utf-8"))
        try:
            reader = csv.reader(f)
        except Exception:
            return []

        rows = list(reader)

        if not rows:
            return []

        keys = rows[0]
        res = defaultdict(list)

        for (i, k) in enumerate(keys):
            for row in rows[1:]:
                res[k].append(row[i])

        return res


class DataVisualization(MetadataBase):
    """Standard Fise Metadata adaptor"""
    visualization = DCFieldProperty(IDataVisualization["visualization"])


class ConnectorDataParameters(MetadataBase):
    """Provide predefined connector data for parameters"""

    # data_parameters = DCFieldProperty(
    #     IConnectorDataParameters['data_parameters'])
    data_query = DCFieldProperty(IConnectorDataParameters["data_query"])
