""" behavior module """
import csv
import logging
from io import StringIO
from plone.app.dexterity.behaviors.metadata import DCFieldProperty
from plone.app.dexterity.behaviors.metadata import MetadataBase
from plone.dexterity.interfaces import IDexterityContent
from plone.rfc822.interfaces import IPrimaryFieldInfo
from zope.component import adapter
from zope.interface import implementer
from zope.publisher.interfaces.browser import IBrowserRequest
from eea.api.dataconnector.queryparser import computeDataQuery
from eea.api.dataconnector.queryfilter import filteredData
from .interfaces import IConnectorDataParameters
from .interfaces import IDataConnector
from .interfaces import IDataProvider
from .interfaces import IDataVisualization
from .interfaces import IMaps
from .interfaces import IMapVisualization
from .interfaces import ITableauVisualization
from .interfaces import IFileDataProvider
from .interfaces import IElasticConnector
from .interfaces import IFigureNote


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
    required_parameters = DCFieldProperty(
        IDataConnector["required_parameters"]
    )
    collate = DCFieldProperty(IDataConnector["collate"])
    readme = DCFieldProperty(IDataConnector["readme"])


@implementer(IDataProvider)
@adapter(IFileDataProvider, IBrowserRequest)
class DataProviderForFiles:
    """Behavior implementation for content types with a File primary field"""

    def __init__(self, context, request):
        self.context = context
        self.request = request

    @property
    def provided_data(self):
        """provided data"""
        field = IPrimaryFieldInfo(self.context)

        if not field.value:
            return []

        text = field.value.data
        f = StringIO(text.decode("utf-8-sig"))
        try:
            reader = csv.reader(f)
        except Exception:
            return []

        rows = list(reader)

        if not rows:
            return []

        keys = rows[0]
        data = []

        for index, row in enumerate(rows[1:]):
            data.append({})
            for (i, k) in enumerate(keys):
                data[index][k] = row[i]

        data_query = computeDataQuery(self.request)

        return {
            "results": filteredData(data, data_query),
            "metadata": {},
        }


@implementer(IDataProvider)
@adapter(IElasticConnector, IBrowserRequest)
class DataProviderForElasticCSVWidget:
    """Behavior implementation for CT with elastic_csv_widget field"""

    def __init__(self, context, request):
        self.context = context
        self.request = request

    @property
    def provided_data(self):
        """provided data"""

        widget = getattr(self.context, 'elastic_csv_widget', None)

        data = widget['tableData'] if widget else {}

        return {
            "results": data,
            "metadata": {},  # Add metadata if needed
        }


class DataVisualization(MetadataBase):
    """Standard Fise Metadata adaptor"""

    visualization = DCFieldProperty(IDataVisualization["visualization"])


class Maps(MetadataBase):
    """Standard Fise Metadata adaptor"""

    maps = DCFieldProperty(IMaps["maps"])


class MapViewVisualization(MetadataBase):
    """Standard ArcGIS Map View adaptor"""

    map_visualization_data = DCFieldProperty(
        IMapVisualization["map_visualization_data"]
    )


class TableauViewVisualization(MetadataBase):
    """Standard Tableau View adaptor"""

    tableau_visualization = DCFieldProperty(
        ITableauVisualization["tableau_visualization"]
    )


class ConnectorDataParameters(MetadataBase):
    """Provide predefined connector data for parameters"""

    data_query = DCFieldProperty(IConnectorDataParameters["data_query"])


class ElasticConnectorWidget(MetadataBase):
    """Build csv data from ES data"""

    elastic_csv_widget = DCFieldProperty(
        IElasticConnector["elastic_csv_widget"]
    )


class FigureNoteField(MetadataBase):
    """Insert Figure Note field"""

    figure_note = DCFieldProperty(
        IFigureNote["figure_note"]
    )
