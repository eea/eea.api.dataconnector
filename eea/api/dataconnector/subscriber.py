""" subscriber module """

from io import BytesIO
from zipfile import ZipFile
import logging

from persistent.mapping import PersistentMapping
from plone.namedfile.file import NamedBlobFile
from zope.annotation.interfaces import IAnnotations


logger = logging.getLogger(__name__)


def annotations_flourish_set(obj, event):
    """ annotations_flourish_set """
    # import pdb
    # pdb.set_trace()
    annotations = IAnnotations(obj)
    annot_data = PersistentMapping()
    blob = obj.flourish_zip
    if blob:
        blob_content = blob.data

        annot_data = PersistentMapping()
        with ZipFile(BytesIO(blob_content), mode="r") as myzip:
            for file_name in myzip.namelist():
                file_content = myzip.open(file_name).read()
                file = NamedBlobFile(filename=file_name, data=file_content)
                annot_data[file_name] = file
    annotations['flourish_zip'] = annot_data

    # import pdb
    # pdb.set_trace()
    logger.warning("FlourishObjectModified")
