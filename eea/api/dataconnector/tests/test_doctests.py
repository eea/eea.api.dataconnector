""" Doc tests
"""
import doctest
import unittest
from eea.api.dataconnector.tests.base import FUNCTIONAL_TESTING
from plone.testing import layered

OPTIONFLAGS = (
    doctest.REPORT_ONLY_FIRST_FAILURE
    | doctest.ELLIPSIS
    | doctest.NORMALIZE_WHITESPACE
)


def test_suite():
    """Suite"""
    suite = unittest.TestSuite()
    suite.addTests(
        [
            layered(
                doctest.DocFileSuite(
                    "README.txt",
                    optionflags=OPTIONFLAGS,
                    package="eea.api.dataconnector",
                ),
                layer=FUNCTIONAL_TESTING,
            ),
        ]
    )

    return suite


if __name__ == "__main__":
    unittest.main(defaultTest="test_suite")
