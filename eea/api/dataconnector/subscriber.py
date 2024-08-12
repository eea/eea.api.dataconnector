""" subscriber module """

from io import BytesIO
from zipfile import ZipFile

from persistent.mapping import PersistentMapping
from plone.namedfile.file import NamedBlobFile
from zope.annotation.interfaces import IAnnotations


def annotations_flourish_set(obj, event):
    """ annotations_flourish_set """
    annotations = IAnnotations(obj)
    annot_data = PersistentMapping()
    blob = obj.flourish_zip
    if blob:
        blob_content = blob.data

        annot_data = PersistentMapping()
        with ZipFile(BytesIO(blob_content)) as myzip:
            for file_name in myzip.namelist():
                with myzip.open(file_name) as file_content:
                    file = NamedBlobFile(
                        filename=file_name, data=file_content.read())
                    annot_data[file_name] = file
    annotations['flourish_zip'] = annot_data
