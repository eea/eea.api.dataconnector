""" Evolve script to cleanup Plotly BOM characters """
import logging
from Products.CMFCore.utils import getToolByName
logger = logging.getLogger("eea.api.dataconnector")


def cleanup_dict(data):
    """ Cleanup Plotly BOM characters """
    for key, value in data.items():
        if isinstance(value, dict):
            cleanup_dict(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    cleanup_dict(item)
        elif isinstance(value, str):
            data[key] = value.replace("\ufeff", "")
    return data


def cleanup(context):
    """ Cleanup Plotly BOM characters """
    ctool = getToolByName(context, "portal_catalog")
    portal_type = "visualization"
    brains = ctool.unrestrictedSearchResults(portal_type=portal_type)
    total = len(brains)

    logger.info("Upgrading %s: type %s", total, portal_type)
    for brain in brains:
        doc = brain.getObject()
        if doc is None:
            continue

        visualization = getattr(doc, 'visualization', {})
        if not visualization:
            continue

        doc.visualization = cleanup_dict(visualization)
        logger.info("Updated %s", brain.getURL())
    logger.info("Upgraded %s: type %s", total, portal_type)
