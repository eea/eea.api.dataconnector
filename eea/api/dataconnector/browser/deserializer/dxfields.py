""" dxfields deserializers """

from urllib.parse import urlparse
from zope.component import adapter
from zope.interface import implementer
from zope.publisher.interfaces.browser import IBrowserRequest
from plone.schema import IJSONField
from plone.dexterity.interfaces import IDexterityContent
from plone.restapi.interfaces import IFieldDeserializer
from plone.restapi.deserializer.dxfields import DefaultFieldDeserializer
from plone.restapi.deserializer.utils import path2uid


def getLink(path):
    """
      Get link
      """

    URL = urlparse(path)

    if URL.netloc.startswith('localhost') and URL.scheme:
        return path.replace(URL.scheme + "://" + URL.netloc, "")
    return path


@implementer(IFieldDeserializer)
@adapter(IJSONField, IDexterityContent, IBrowserRequest)
class JSONFieldDeserializer(DefaultFieldDeserializer):
    """JSON field deserializer"""

    def __call__(self, value):
        if isinstance(value, dict) and 'provider_url' in value:
            url = value["provider_url"]
            value["provider_url"] = path2uid(
                context=self.context, link=getLink(url))
        return value
