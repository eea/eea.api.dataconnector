""" data provider
"""

from io import BytesIO
import xlsxwriter
from eea.api.dataconnector.interfaces import IDataProvider
from Products.Five.browser import BrowserView


class DataProviderView(BrowserView):
    """Basic view for the DataConnector"""

    def data(self):
        """return data from data provider"""
        dataprovider = IDataProvider(self.context)

        return dataprovider.provided_data


class DataProviderDownload(BrowserView):
    """Basic view for the DataConnector"""

    def data_to_xls(self, data):
        """convert data to xls"""
        out = BytesIO()
        workbook = xlsxwriter.Workbook(out, {"in_memory": True})

        worksheet = workbook.add_worksheet("Data")

        headers = data.keys()

        for i, label in enumerate(headers):
            worksheet.write(0, i, label)

        for i, col in enumerate(headers):
            coldata = data[col]

            for j, val in enumerate(coldata):
                worksheet.write(j + 1, i, val)

        workbook.close()
        out.seek(0)

        return out

    def __call__(self):
        dataprovider = IDataProvider(self.context)
        data = dataprovider.provided_data

        return self.download(data)

    def download(self, data):
        """download"""
        xlsio = self.data_to_xls(data)
        sh = self.request.response.setHeader

        sh(
            "Content-Type",
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet",
        )
        sh(
            "Content-Disposition",
            "attachment; filename=%s.xlsx" % self.context.getId(),
        )

        return xlsio.read()
