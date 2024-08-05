""" subscriber module """

from io import BytesIO
from persistent.mapping import PersistentMapping
from plone.namedfile.file import NamedBlobFile
from zipfile import ZipFile
from zope.annotation.interfaces import IAnnotations
import logging

logger = logging.getLogger(__name__)


def annotations_flourish_set(obj, event):
    # import pdb
    # pdb.set_trace()
    annotations = IAnnotations(obj)
    annot_data = PersistentMapping()
    blob = obj.flourish_zip
    if blob:
        blob_content = blob.data

        annot_data = PersistentMapping()
        myzip = ZipFile(BytesIO(blob_content))
        for file_name in myzip.namelist():
            file_content = myzip.open(file_name).read()
            file = NamedBlobFile(filename=file_name, data=file_content)
            annot_data[file_name] = file
    annotations['flourish_zip'] = annot_data

    # import pdb
    # pdb.set_trace()
    logger.warning("FlourishObjectModified")
