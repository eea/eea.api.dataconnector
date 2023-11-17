""" Base test cases
"""
# pylint: disable=C0415
from plone.app.testing import (
    TEST_USER_ID,
    FunctionalTesting,
    PloneSandboxLayer,
    applyProfile,
    setRoles,
)
from plone.testing import z2
from Products.CMFPlone import setuphandlers


class EEAFixture(PloneSandboxLayer):
    """EEA Testing Policy"""

    def setUpZope(self, app, configurationContext):
        """Setup Zope"""
        import eea.api.dataconnector
        import plone.restapi

        self.loadZCML(package=plone.restapi)
        self.loadZCML(package=eea.api.dataconnector)

        z2.installProduct(app, "plone.restapi")
        z2.installProduct(app, "eea.api.dataconnector")

    def setUpPloneSite(self, portal):
        """Setup Plone"""
        applyProfile(portal, "eea.api.dataconnector:default")

        # Default workflow
        wftool = portal["portal_workflow"]
        wftool.setDefaultChain("simple_publication_workflow")

        # Login as manager
        setRoles(portal, TEST_USER_ID, ["Manager"])

        # Add default Plone content
        try:
            applyProfile(portal, "plone.app.contenttypes:plone-content")
        except KeyError:
            # BBB Plone 4
            setuphandlers.setupPortalContent(portal)

        # Create testing environment
        portal.invokeFactory("Folder", "sandbox", title="Sandbox")

    def tearDownZope(self, app):
        """Uninstall Zope"""
        z2.uninstallProduct(app, "eea.api.dataconnector")


EEAFIXTURE = EEAFixture()
FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(EEAFIXTURE,), name="EEAslate:Functional"
)
