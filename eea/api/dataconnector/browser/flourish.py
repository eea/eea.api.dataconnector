"""flourish"""

from zipfile import ZipFile, is_zipfile

import requests
from persistent.mapping import PersistentMapping
from plone.namedfile.file import NamedBlobFile
from plone.namedfile.utils import set_headers, stream_data
from plone.transformchain.interfaces import DISABLE_TRANSFORM_REQUEST_KEY
from Products.Five.browser import BrowserView
from zope.annotation.interfaces import IAnnotations
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse, NotFound
from ZPublisher.HTTPRangeSupport import expandRanges, parseRange


def fix_index_html(text):
    """Localizes external urls"""
    text = text.replace(b"https://public.flourish.studio/",
                        b"./flourish-studio/")
    return text


class IOWrapper:
    """Fake IO wrapper"""

    def __init__(self, content, content_type):
        self.data = content
        self.content_type = content_type
        # self.data = io.BytesIO(content)

    def getSize(self):
        "getSize implementation"
        return len(self.data)


def apply_external_content(url, request):
    """Proxies external content"""
    resp = requests.get(url)
    content_type = resp.headers.get("Content-Type", "text/plain")
    request.response.setHeader(
        "Content-Type", resp.headers.get("Content-Type", "text/plain")
    )

    file = IOWrapper(resp.content, content_type)
    return file


class FlourishUpload(BrowserView):
    """Upload a zip file, extract it and add to context annotation"""

    def list(self):
        """upload form and show current flourish from annotation"""
        response = {}
        response["title"] = self.context.title
        response["portal_type"] = self.context.portal_type
        response["url"] = self.context.absolute_url()
        response["annotations"] = []
        response["message"] = None
        annotations = IAnnotations(self.context)
        fileUploaded = self.request.form.get("fileToUpload", None)
        if fileUploaded:
            if is_zipfile(fileUploaded):
                annot_data = PersistentMapping()
                with ZipFile(fileUploaded.file) as myzip:
                    for file_name in myzip.namelist():
                        with myzip.open(file_name) as file_content:
                            data = file_content.read()
                            if file_name == "index.html":
                                data = fix_index_html(data)
                            file = NamedBlobFile(filename=file_name, data=data)
                            annot_data[file_name] = file
                annotations["flourish_zip"] = annot_data
            else:
                response["message"] = "The file sent was either empty \
                     or not a valid zip archive."
        elif self.request.form.get("delete", None):
            annotations["flourish_zip"] = []

        if "flourish_zip" in annotations:
            response["annotations"] = annotations["flourish_zip"]

        return response


@implementer(IPublishTraverse)
class FlourishDownload(BrowserView):
    """Download a file, via ../context/@@flourish/filename"""

    def __init__(self, context, request):
        super().__init__(context, request)
        self.filename = []

    def publishTraverse(self, request, name):
        """traverse"""
        self.filename += [name]
        return self

    def __call__(self):
        self.request.response.setHeader("X-Theme-Disabled", "1")
        file = self._getFile()

        set_headers(file, self.request.response)
        request_range = self.handle_request_range(file)
        self.request.environ[DISABLE_TRANSFORM_REQUEST_KEY] = True
        return stream_data(file, **request_range)

    def handle_request_range(self, file):
        """handle_request_range"""
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

    def _getFile(self):
        """_getFiles"""

        context = getattr(self.context, "aq_explicit", self.context)
        annotations = IAnnotations(context)
        data = annotations.get("flourish_zip", {})

        if len(self.filename) > 1:  # handle the flourish-studio paths
            bits = self.filename[1:]
            url = "https://public.flourish.studio/" + "/".join(bits)
            content = apply_external_content(url, self.request)
            return content

        filename = self.filename[0]
        file = data.get(filename, None)

        if file is None:
            raise NotFound(self, filename, self.request)

        return file
