"""Module where all interfaces, events and exceptions live."""

import json
from plone.app.z3cform.widget import QueryStringFieldWidget
from plone.autoform import directives as form
from plone.autoform.interfaces import IFormFieldProvider
from plone.schema import JSONField
from plone.supermodel import model
from zope import schema
from zope.interface import Interface
from zope.interface import Attribute
from zope.interface import provider
from zope.publisher.interfaces.browser import IDefaultBrowserLayer


class IEeaRestapiDataconnector(IDefaultBrowserLayer):
    """Marker interface that defines a browser layer."""


class IEeaDataconnectorLayer(IDefaultBrowserLayer):
    """Marker interface that defines a browser layer."""


@provider(IFormFieldProvider)
class IDataConnector(model.Schema):
    """A generic discodata connector"""

    endpoint_url = schema.TextLine(
        title="Discodata endpoint URL",
        required=True,
        # default=u"http://discomap.eea.europa.eu/App/SqlEndpoint/query"
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
        description=u"Provider doesn't send data if the reuqired parameter is "
        "not set",
        required=False,
        value_type=schema.TextLine(title="Parameter"),
    )
    required_parameters = schema.List(
        title=u"Required query parameters",
        description=u"Provider doesn't send data if the reuqired parameter is "
        "not set",
        required=False,
        value_type=schema.TextLine(title=u"Parameter"),
    )
    namespace = schema.TextLine(
        title="Connector namespace",
        description=u"Optional namespace string, use it in case data in "
        "this connector is not uniform across the other datasets",
        required=False,
        default="",
    )
    collate = schema.TextLine(
        title="Collate",
        description=u"Optional collate string, use it in case data has a "
        "different encoding then utf-8",
        required=False,
        default="",
    )

    # directives.fieldset('dataconnector', label="Data connector", fields=[
    #     'endpoint_url', 'query',
    # ])


class IBasicDataProvider(Interface):
    """A data provider concept"""


class IDataProvider(IBasicDataProvider):
    """An export of data for remote purposes"""

    provided_data = Attribute("Data made available by this data provider")


class IFileDataProvider(IBasicDataProvider):
    """Marker interface for objects that provide data to visualizations"""


class IConnectorDataProvider(IBasicDataProvider):
    """Marker interface for objects that provide data to visualizations"""


VIZ_SCHEMA = json.dumps({"type": "object", "properties": {}})


@provider(IFormFieldProvider)
class IDataVisualization(model.Schema):
    """A data visualization (chart)"""

    visualization = JSONField(
        title="Visualization", required=False, default={}, schema=VIZ_SCHEMA
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
        # value_type=schema.Dict(
        #     value_type=schema.Object(title=u"Value", schema=NotGiven),
        #     key_type=schema.TextLine(title=u"Key")
        # ),
        required=True,
        missing_value=[],
    )
    form.widget("data_query", QueryStringFieldWidget)
