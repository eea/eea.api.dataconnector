""" flourish
"""

from zipfile import (ZipFile, is_zipfile)

from plone.namedfile.utils import set_headers, stream_data
from plone.namedfile.file import NamedBlobFile
from Products.Five.browser import BrowserView
from zope.annotation.interfaces import IAnnotations
from zope.publisher.interfaces import IPublishTraverse, NotFound
from zope.interface import implementer
from ZPublisher.HTTPRangeSupport import expandRanges, parseRange

from persistent.mapping import PersistentMapping
# from AccessControl.ZopeGuards import guarded_getattr
# from plone.rfc822.interfaces import IPrimaryFieldInfo
# from plone.namedfile.utils import extract_media_type


class FlourishUpload(BrowserView):
    """Upload a zip file, extract it and add to context annotation"""

    def list(self):
        """ upload form and show current flourish from annotation """
        response = {}
        response['title'] = self.context.title
        response['portal_type'] = self.context.portal_type
        response['url'] = self.context.absolute_url()
        response['annotations'] = []
        response['message'] = None
        annotations = IAnnotations(self.context)
        fileUploaded = self.request.form.get("fileToUpload", None)
        if fileUploaded:
            if is_zipfile(fileUploaded):
                annot_data = PersistentMapping()
                with ZipFile(fileUploaded.file) as myzip:
                    for file_name in myzip.namelist():
                        with myzip.open(file_name) as file_content:
                            file = NamedBlobFile(
                                filename=file_name, data=file_content.read())
                            annot_data[file_name] = file
                annotations['flourish_zip'] = annot_data
            else:
                response['message'] = 'The file sent was either empty \
                     or not a valid zip archive.'
        elif self.request.form.get("delete", None):
            annotations['flourish_zip'] = []

        if 'flourish_zip' in annotations:
            response['annotations'] = annotations['flourish_zip']
        return response


@implementer(IPublishTraverse)
class FlourishDownload(BrowserView):
    """Download a file, via ../context/@@flourish/filename"""

    def __init__(self, context, request):
        super().__init__(context, request)
        self.filename = None

    def publishTraverse(self, request, name):
        """ traverse """
        if self.filename is None:  # ../@@download/fieldname/filename
            self.filename = name
        else:
            raise NotFound(self, name, request)
        return self

    def __call__(self):
        self.request.response.setHeader('X-Theme-Disabled', '1')
        file = self._getFile()
        self.set_headers(file)
        request_range = self.handle_request_range(file)
        return stream_data(file, **request_range)

    def handle_request_range(self, file):
        """ handle_request_range """
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
            # multipart ranges not implemented
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
        """ set_headers """

        set_headers(file, self.request.response)

    def _getFile(self):
        """ _getFiles """

        context = getattr(self.context, "aq_explicit", self.context)
        annotations = IAnnotations(context)
        data = annotations.get("flourish_zip", {})
        file = data.get(self.filename, None)

        if file is None:
            raise NotFound(self, self.filename, self.request)

        return file
