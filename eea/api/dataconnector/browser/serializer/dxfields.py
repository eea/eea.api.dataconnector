""" dxfields serializers """

import copy
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface
from plone.schema import IJSONField
from plone.dexterity.interfaces import IDexterityContent
from plone.restapi.serializer.dxfields import DefaultFieldSerializer
from plone.restapi.serializer.utils import uid_to_url
from plone.restapi.serializer.converters import json_compatible
from plone.restapi.interfaces import IFieldSerializer


@implementer(IFieldSerializer)
@adapter(IJSONField, IDexterityContent, Interface)
class JSONFieldSerializer(DefaultFieldSerializer):
    """JSON field serializer"""

    def __call__(self):
        value = copy.deepcopy(self.get_value())

        if isinstance(value, dict) and 'provider_url' in value:
            value["provider_url"] = uid_to_url(value["provider_url"])

        return json_compatible(value)
