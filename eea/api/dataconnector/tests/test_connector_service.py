"""Tests for connector-data service registration."""

import unittest

from eea.api.dataconnector.tests.base import FUNCTIONAL_TESTING
from plone.restapi.interfaces import IExpandableElement
from zope.component import queryMultiAdapter


class TestConnectorDataServiceRegistration(unittest.TestCase):
    """Verify @connector-data is only exposed on supported content."""

    layer = FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.sandbox = self.portal["sandbox"]

    def test_regular_content_does_not_expose_connector_data_service(self):
        self.sandbox.invokeFactory("Document", "regular-document", title="Regular")
        document = self.sandbox["regular-document"]

        service = queryMultiAdapter(
            (document, self.portal.REQUEST), name="@connector-data"
        )
        self.assertIsNone(service)

    def test_connector_content_exposes_connector_data_service(self):
        self.sandbox.invokeFactory("discodataconnector", "connector", title="Connector")
        connector = self.sandbox["connector"]

        service = queryMultiAdapter(
            (connector, self.portal.REQUEST),
            IExpandableElement,
            name="connector-data",
        )
        self.assertIsNotNone(service)
