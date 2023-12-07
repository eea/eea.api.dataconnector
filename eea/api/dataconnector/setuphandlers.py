""" Custom setup
"""
from Products.CMFPlone.interfaces import INonInstallable
from zope.interface import implementer


@implementer(INonInstallable)
class HiddenProfiles:
    """Hidden profiles"""

    def getNonInstallableProfiles(self):
        """Hide uninstall profile from site-creation and quickinstaller."""
        return [
            "eea.api.dataconnector:uninstall",
            "eea.api.dataconnector:upgrade_50",
            "eea.api.dataconnector:upgrade_60",
            "eea.api.dataconnector:upgrade_82",
        ]


def post_install(context):
    """Post install script"""
    # Do something at the end of the installation of this package.


def uninstall(context):
    """Uninstall script"""
    # Do something at the end of the uninstallation of this package.
