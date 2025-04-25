"""CSV reader/writer that handles NULL values."""
import csv
NULL = 'NULL'


class CsvWriter:
    """CSV writer that handles NULL values."""

    def __init__(self, *args, **kwrds):
        dialect = csv.excel
        self.csv_writer = csv.writer(*args, dialect=dialect, **kwrds)

    def __getattr__(self, name):
        return getattr(self.csv_writer, name)

    def writerow(self, row):
        """Write a single row to the CSV file."""
        self.csv_writer.writerow(
            [item if item is not None else NULL
             for item in row]
        )

    def writerows(self, rows):
        """Write multiple rows to the CSV file."""
        for row in rows:
            self.writerow(row)


class CsvReader:
    """CSV reader that handles NULL values."""

    def __init__(self, *args, **kwrds):
        try:
            inputEntity = args[0] or kwrds.get('csvfile')
            sample = inputEntity.read(1024)
            inputEntity.seek(0)
            dialect = csv.Sniffer().sniff(sample)
        except (csv.Error, TypeError):
            # No dialect found, use default
            dialect = csv.excel
        self.csv_reader = csv.reader(*args, dialect=dialect, **kwrds)

    def __getattr__(self, name):
        return getattr(self.csv_reader, name)

    def __iter__(self):
        rows = iter(self.csv_reader)
        for row in rows:
            yield [item if item != NULL else None for item in row]
