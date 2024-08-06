from ZPublisher.HTTPRangeSupport import expandRanges
from ZPublisher.HTTPRangeSupport import parseRange
from plone.rest.traverse import RESTWrapper
from zope.component import adapter  # , getUtility
from zope.interface import Interface, implementer
from zope.publisher.interfaces.browser import IBrowserRequest
from zope.traversing.interfaces import ITraversable

# from plone.app.layout.navigation.interfaces import INavigationRoot
# from plone.contentrules.engine.interfaces import IRuleStorage
from plone.namedfile.utils import set_headers
from zope.annotation.interfaces import IAnnotations
from plone.namedfile.utils import stream_data
# @adapter(INavigationRoot, IBrowserRequest)


@adapter(Interface, IBrowserRequest)
@implementer(ITraversable)
class FlourishAcquisitionNamespace(object):
    """Used to traverse to a content.

    Traversing to portal/path/to/something/++flourish++file_name, acquisition-wrapped.
    """

    # def __call__(self):
    #     file = self._getFile()
    #     self.set_headers(file)
    #     request_range = self.handle_request_range(file)
    #     return stream_data(file, **request_range)

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
        # With filename None, set_headers will not add the download headers.
        if not self.filename:
            self.filename = getattr(file, "filename", None)
            if self.filename is None:
                self.filename = self.fieldname
                if self.filename is None:
                    self.filename = "file.ext"
        set_headers(file, self.request.response, filename=self.filename)

    def __init__(self, context, request=None):
        self.context = context
        self.request = request

    def traverse(self, name, ignore):

        base = self.context.restrictedTraverse(name).aq_base
        import pdb
        pdb.set_trace()

        annotations = IAnnotations(self.context)
        data = annotations.get('flourish_zip')
        key = 'README.txt'
        file = None
        if key in data:
            file = data[key]
            # file = self._getFile()
            self.set_headers(file)
            request_range = self.handle_request_range(file)
            return stream_data(file, **request_range)

        return file

        print('123')
        quit()

        # handle ++aq++metadata links in the Observatory
        if isinstance(self.context, RESTWrapper):
            context = self.context.context
            base = base.__of__(context)
            self.context.context = base
            return self.context

        self.request.form["observatory_page"] = "1"
        destination = base.__of__(self.context)
        return destination
