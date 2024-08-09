from plone.namedfile.utils import set_headers, stream_data
from Products.Five.browser import BrowserView
from zope.annotation.interfaces import IAnnotations
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse, NotFound
from ZPublisher.HTTPRangeSupport import expandRanges, parseRange

# from AccessControl.ZopeGuards import guarded_getattr
# from plone.rfc822.interfaces import IPrimaryFieldInfo
# from plone.namedfile.utils import extract_media_type


@implementer(IPublishTraverse)
class FlourishDownload(BrowserView):
    """Download a file, via ../context/@@flourish/filename"""

    def __init__(self, context, request):
        super().__init__(context, request)
        self.filename = None

    def publishTraverse(self, request, name):
        if self.filename is None:  # ../@@download/fieldname/filename
            self.filename = name
        else:
            raise NotFound(self, name, request)
        return self

    def __call__(self):
        file = self._getFile()
        self.set_headers(file)
        request_range = self.handle_request_range(file)
        return stream_data(file, **request_range)

    def handle_request_range(self, file):
        default = {}
        # check if we have a range in the request
        header_range = self.request.getHeader("Range", None)
        if header_range is None:
            return default
        if_range = self.request.getHeader("If-Range", None)
        if if_range is not None:
            # We delete the ranges, which causes us to skip to the 200
            # response.
            return default
        ranges = parseRange(header_range)
        if not ranges or len(ranges) != 1:
            # TODO: multipart ranges not implemented
            return default
        try:
            length = file.getSize()
            [(start, end)] = expandRanges(ranges, length)
            size = end - start
            self.request.response.setHeader("Content-Length", size)
            self.request.response.setHeader(
                "Content-Range", f"bytes {start}-{end - 1}/{length}"
            )
            self.request.response.setStatus(206)  # Partial content
            return dict(start=start, end=end)
        except ValueError:
            return default

    def set_headers(self, file):
        set_headers(file, self.request.response)

    def _getFile(self):

        context = getattr(self.context, "aq_explicit", self.context)
        annotations = IAnnotations(context)
        data = annotations.get("flourish_zip", {})
        file = data.get(self.filename, None)

        if file is None:
            raise NotFound(self, self.filename, self.request)

        return file
