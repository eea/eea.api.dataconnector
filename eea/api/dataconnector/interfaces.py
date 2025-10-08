"""Module where all interfaces, events and exceptions live."""
import json
from plone.app.z3cform.widget import QueryStringFieldWidget
from plone.autoform import directives as form
from plone.autoform.interfaces import IFormFieldProvider
from plone.schema import JSONField
from plone.supermodel import model
from zope import schema
from zope.interface import Interface, Attribute, provider
from zope.publisher.interfaces.browser import IDefaultBrowserLayer
from eea.schema.slate.field import SlateJSONField


class IEeaRestapiDataconnector(IDefaultBrowserLayer):
    """Marker interface that defines a browser layer."""


class IEeaDataconnectorLayer(IDefaultBrowserLayer):
    """Marker interface that defines a browser layer."""


class IBasicDataProvider(Interface):
    """A data provider concept"""


class IDataProvider(IBasicDataProvider):
    """An export of data for remote purposes"""

    provided_data = Attribute("Data made available by this data provider")


class IElasticDataProvider(IBasicDataProvider):
    """An export of data for remote purposes"""

    provided_data = Attribute("Data made available by this data provider")


class IFileDataProvider(IBasicDataProvider):
    """Marker interface for objects that provide data to visualizations"""


class IConnectorDataProvider(IBasicDataProvider):
    """Marker interface for objects that provide data to visualizations"""


@provider(IFormFieldProvider)
class IDataConnector(model.Schema):
    """A generic discodata connector"""

    endpoint_url = schema.TextLine(
        title="Discodata endpoint URL",
        required=True,
        default="https://discodata.eea.europa.eu/sql",
    )
    sql_query = schema.Text(
        title="SQL Query",
        required=True,
        default="Select top 10000 * from [FISE].[v1].[CLC]",
    )
    parameters = schema.List(
        title="Query parameters",
        description="Names for potential WHERE SQL filters",
        required=False,
        value_type=schema.TextLine(title="Parameter"),
    )
    required_parameters = schema.List(
        title="Required query parameters",
        description="Provider doesn't send data if the reuqired parameter is "
        "not set",
        required=False,
        value_type=schema.TextLine(title="Parameter"),
    )
    collate = schema.TextLine(
        title="Collate",
        description="Optional collate string, use it in case data has a "
        "different encoding then utf-8",
        required=False,
        default="",
    )
    readme = schema.Text(
        title="Readme",
        required=False,
        default="",
    )


EMBED_MAP_VIEW_SCHEMA = json.dumps({"type": "object", "properties": {}})


@provider(IFormFieldProvider)
class IMaps(model.Schema):
    """An maps view"""

    maps = JSONField(
        title="Maps", required=False, default={}, schema=EMBED_MAP_VIEW_SCHEMA
    )


MAP_VIEW_SCHEMA = json.dumps({"type": "object", "properties": {}})


@provider(IFormFieldProvider)
class IMapVisualization(model.Schema):
    """An ArcGIS Map view"""

    map_visualization_data = JSONField(
        title="Map Widget(ArcGIS)",
        required=False,
        default={},
        schema=MAP_VIEW_SCHEMA,
    )


TABLEAU_VIEW_SCHEMA = json.dumps({"type": "object", "properties": {}})


@provider(IFormFieldProvider)
class ITableauVisualization(model.Schema):
    """Tableau view"""

    tableau_visualization = JSONField(
        title="Tableau Widget",
        required=False,
        default={},
        schema=TABLEAU_VIEW_SCHEMA,
    )


@provider(IFormFieldProvider)
class IConnectorDataParameters(model.Schema):
    """Allow content to preset parameters for connector data"""

    # data_parameters = JSONField(
    #     title=_(u'Parameter values'),
    #     description=u"Predefined parameter values",
    #     schema=GENERIC_LIST_SCHEMA,
    #     required=False,
    # )

    data_query = schema.List(
        title="Data query parameters",
        description="Define the data query parameters",
        value_type=schema.Dict(value_type=schema.Field(),
                               key_type=schema.TextLine()),
        required=False,
        missing_value=[],
        default=[],
    )
    form.widget("data_query", QueryStringFieldWidget)


ELASTIC_CONNECTOR_WIDGET_SCHEMA = json.dumps(
    {"type": "object", "properties": {}}
)


@provider(IFormFieldProvider)
class IElasticConnector(model.Schema):
    """An Elastic search to CSV data builder widget"""

    elastic_csv_widget = JSONField(
        title="Elastic CSV widget",
        required=False,
        default={},
        schema=ELASTIC_CONNECTOR_WIDGET_SCHEMA,
    )


@provider(IFormFieldProvider)
class IFigureNote(model.Schema):
    """FigureNote Slate widget field"""

    figure_note = SlateJSONField(
        title="Figure Note",
        description="Metadata field for visualization content-types",
        required=False,
    )
