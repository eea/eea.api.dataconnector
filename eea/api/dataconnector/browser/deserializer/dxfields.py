""" dxfields deserializers """

from urllib.parse import urlparse
from plone.schema import IJSONField
from plone.dexterity.interfaces import IDexterityContent
from plone.restapi.interfaces import IFieldDeserializer
from zope.component import adapter
from zope.interface import implementer
from zope.publisher.interfaces.browser import IBrowserRequest
from plone.restapi.deserializer.dxfields import DefaultFieldDeserializer
from plone.restapi.deserializer.utils import path2uid
from plone.restapi.serializer.utils import RESOLVEUID_RE


def getLink(path):
    """
      Get link
      """

    URL = urlparse(path)

    if URL.netloc.startswith('localhost') and URL.scheme:
        return path.replace(URL.scheme + "://" + URL.netloc, "")
    return path


def getUid(context, link, retry=True):
    """
      Get the UID corresponding to a given link.

      Parameters:
      - context: The context or object providing the link.
      - link (str): The link for which to retrieve the UID.
      - retry (bool, optional): If True, attempt to resolve the UID
        even if the initial attempt fails. Defaults to True.

      Returns:
      - str or None: The UID corresponding to the provided link,
        or None if the link is empty or cannot be resolved.

      If the link is empty, the function returns the link itself.
      If the link cannot be resolved in the initial attempt and retry
      is True, the function retries resolving the link by calling itself
      with retry set to False.

      The function uses the RESOLVEUID_RE regular expression to match
      and extract the UID from the link.
      """

    if not link:
        return link
    match = RESOLVEUID_RE.match(link)
    if match is None:
        if not retry:
            return link
        # Alin Voinea a zis sa las asa
        return getUid(context, path2uid(context=context, link=getLink(link)),
                      False)

    uid, _ = match.groups()
    return uid


@implementer(IFieldDeserializer)
@adapter(IJSONField, IDexterityContent, IBrowserRequest)
class JSONFieldDeserializer(DefaultFieldDeserializer):
    """JSON field deserializer"""

    def __call__(self, value):
        if isinstance(value, dict) and 'provider_url' in value:
            url = value["provider_url"]
            uid = getUid(self.context, url)
            value["provider_url"] = ("../resolveuid/%s" %
                                     uid) if uid != url else url

            return value
