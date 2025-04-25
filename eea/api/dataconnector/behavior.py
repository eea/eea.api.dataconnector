""" behavior module """

import csv
import logging
from io import StringIO

from plone.app.dexterity.behaviors.metadata import (
    DCFieldProperty,
    MetadataBase
)
from plone.dexterity.interfaces import IDexterityContent
from plone.restapi.deserializer import json_body
from zope.component import adapter
from zope.interface import implementer
from zope.publisher.interfaces.browser import IBrowserRequest

from eea.api.dataconnector.queryparser import computeDataQuery
from eea.api.dataconnector.queryfilter import filteredData
from eea.api.dataconnector.io_csv import CsvReader


from .interfaces import (
    IConnectorDataParameters, IDataConnector,
    IDataProvider,
    IMaps, IMapVisualization, ITableauVisualization,
    IFileDataProvider,
    IElasticConnector, IFigureNote
)


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
        IDataConnector["required_parameters"])
    collate = DCFieldProperty(IDataConnector["collate"])
    readme = DCFieldProperty(IDataConnector["readme"])


@implementer(IDataProvider)
@adapter(IFileDataProvider, IBrowserRequest)
class DataProviderForFiles:
    """Behavior implementation for content types with a File primary field"""

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def fileToJson(self, file):
        """Convert binary file data to JSON"""
        if not file:
            return None
        data = file.data
        if not data:
            return None
        buff = StringIO(data.decode('utf-8'))
        try:
            data = []
            headers = []
            i = -1
            for row in CsvReader(buff):
                i += 1
                j = -1
                for cell in row:
                    if i == 0:
                        headers.append(cell)
                        continue
                    j += 1
                    if i > len(data):
                        data.append({})
                    data[i - 1][headers[j]] = cell
            return data
        except csv.Error:
            return None

    @property
    def provided_data(self):
        """provided data"""
        file = self.context.file

        page = json_body(self.request).get("form", {}).get("p", 0)
        nrOfHits = json_body(self.request).get("form", {}).get("nrOfHits", 0)

        if not file:
            return []

        data = self.fileToJson(file)

        if page >= 1 and nrOfHits >= 1:
            data = data[(page - 1) * nrOfHits:page * nrOfHits]

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

        widget = getattr(self.context, "elastic_csv_widget", None)

        data = widget["tableData"] if widget else {}

        return {
            "results": data,
            "metadata": {},  # Add metadata if needed
        }


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
        IElasticConnector["elastic_csv_widget"])


class FigureNoteField(MetadataBase):
    """Insert Figure Note field"""

    figure_note = DCFieldProperty(IFigureNote["figure_note"])
