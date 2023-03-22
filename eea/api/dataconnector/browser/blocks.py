""" block-related utils """

import re
from plone.restapi.behaviors import IBlocks
from plone.restapi.interfaces import IBlockFieldSerializationTransformer
from zope.component import adapter
from zope.interface import implementer
from zope.publisher.interfaces.browser import IBrowserRequest


@implementer(IBlockFieldSerializationTransformer)
@adapter(IBlocks, IBrowserRequest)
class PlotlyChartSerializeTransformer(object):
    """Plotly chart serializer"""

    order = 100
    block_type = "plotly_chart"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    # def transform(self, value):
    #     # if value.get("visualization", {}).get("provider_url"):
    #     #     value["visualization"]["provider_url"] = self.url_to_path(
    #     #         value["visualization"]["provider_url"]
    #     #     )
    #     return value

    def __call__(self, value):
        if value.get("use_live_data", True):
            newData = (
                value.get("visualization", {}).get("chartData", {}).get("data", None)
            )
            if not newData:
                return value
            for traceIndex, trace in enumerate(newData):
                for tk in trace:
                    originalColumn = re.sub("src$", "", tk)
                    if tk.endswith("src") and originalColumn in trace:
                        newData[traceIndex][originalColumn] = []
                if not trace.get("transforms"):
                    continue
                for transformIndex, _ in enumerate(trace.get("transforms")):
                    newData[traceIndex]["transforms"][transformIndex]["target"] = []
            value["visualization"]["chartData"]["data"] = newData

        return value
