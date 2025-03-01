""" A set of simplistic parser and writer classes for ADIF logs.
    It is not a complete implementation of the ADIF specification and has only been tested with LoTW and WSJT-X ADIF
    files.

    Note: this implementation chooses to read and write single fields per line, though many ADIF files use multiple
    fields per line.

    Note: Field type and comments are very minimally tested.

    See https://www.adif.org/
"""

import re

#TODO: add validation test cases
#TODO: add read and write test cases
#TODO: add minimum field set warning

class ADIFRow:
    """A single row (field) of an ADIF QSO."""
    def __init__(self, string):
        """Initialize an ADIFRow object."""
        self.string = string

    def set(self, field_name, field_data, field_type=None, comment=None):
        """Set the data for a field name."""
        self.field_name = field_name
        self.field_data = field_data
        self.field_length = len(field_data)
        self.field_type = field_type
        self.comment = comment

    def parse(self):
        """Parse the row from its string representation."""
        results = re.search("^<(\w+):(\d+):?(\w+)?>(.*)", self.string)
        if results:
            self.field_name = results.group(1)
            self.field_length = int(results.group(2))
            self.field_type = results.group(3)
            self.field_data = results.group(4).strip()
            self.comment = results.group(5).strip() if len(results.groups()) > 4 else None
            return True
        else:
            return False

    def validate(self):
        # TODO: fix validation due to out of spec comments after //
        return True #self.field_length == len(self.field_data[0:])

    def __str__(self):
        """Get the string representation of the row."""
        data = self.field_data
        if self.field_name == "CALL":
            data = data.ljust(8, " ")
        field_type_str = f':{self.field_type}' if self.field_type else ''
        return f'<{self.field_name}:{self.field_length}{field_type_str}>{data}'

class ADIFRecord:
    """A single record from an ADIF log containing many rows."""
    def __init__(self):
        """Initialize an ADIFRecord object."""
        self.rows = []
        self.type = "record"

    def __add__(self, row):
        """Add a row to the record."""
        self.rows.append(row)
        return self

    def __len__(self):
        """Get the number of rows in the record."""
        return len(self.rows)

    def get(self, field_name):
        """Get the data for a field name."""
        for row in self.rows:
            if row.field_name.upper() == field_name.upper():
                return row.field_data
        return None

    def __str__(self):
        """Get the string representation of the record."""
        result = ""
        for row in self.rows:
            result += str(row) + " "
        if self.type == "record":
            result += "<eor>"
        elif self.type == "header":
            result += "<eoh>\n\n"
        return result

    def remove_except(self, allowed_fields):
        """Remove all rows except the allowed fields."""
        filter = [f.upper() for f in allowed_fields]
        self.rows = [r for r in self.rows if r.field_name.upper() in filter]
        for r in self.rows:
            r.field_name = r.field_name.upper()

    def set(self, field_name, field_data, field_type=None, comment=None):
        """Set the data for a field name."""
        found = False
        for r in self.rows:
            if r.field_name.upper() == field_name.upper():
                r.field_name = r.field_name.upper()
                r.field_data = field_data
                r.field_length = len(field_data)
                r.field_type = field_type
                r.comment = comment
                found = True

        if not found:
            new_row = ADIFRow(None)
            new_row.set(field_name.upper(), field_data)
            self += new_row

class ADIFFile:
    """A collection of ADIF records."""
    def __init__(self):
        """Initialize an ADIFFile object."""
        self.records = []

    def parse(self, file_path, verbose=False):
        """Parse an ADIF file from a given path."""
        current_entry = ADIFRecord()
        input_rows = []
        with open(file_path, 'r') as input_file:
            for i,row in enumerate(input_file):
            # If format uses single lines, split into multiple lines
                if row.count("<") > 1:

                    content = row.replace("<","\n<")
                    for r in content.splitlines():
                        input_rows.append(r)
                else:
                    input_rows.append(row)

        for row in input_rows:
            r = ADIFRow(row)
            if r.parse():
                current_entry += r
                if verbose: print(f'parsed row into {r}')
                if not r.validate():
                    if verbose: print(f'Row "{row.strip()}" didn\'t validate')
            elif "<eor>" in row:
                if verbose: print('found <eor>')
                self.records.append(current_entry)
                current_entry = ADIFRecord()
                continue
            elif "<eoh>" in row:
                if verbose: print('found <eoh>')
                current_entry.type = "header"
                self.records.append(current_entry)
                current_entry = ADIFRecord()
                continue
            else:
                if verbose: print(f'skipping row "{row.strip()}"')
        if verbose:
            print(f'   Parsed {len(self.records)} records into ADIFFile')
            for r in self.records:
                print(len(r), r)

    def write(self, output_file, test=None, verbose=True):
        """Write an ADIF file to a given path."""
        count = 0
        try:
            for r in self.records:
                if (r.type == "header") or (test == None) or (test and test(r)):
                    output_file.write(str(r))
                    output_file.write("\n")
                    count += 1
            if verbose:
                print(f'   Wrote {count} records')
        except IOError as e:
            print(f"Error writing to output file: {e}")
            raise

    def remove_except(self, allowed_fields):
        """Remove all rows except the allowed fields."""
        for r in self.records:
            if r.type == "record":
                r.remove_except(allowed_fields)

    def set_all(self, field_name, field_data):
        """Set the data in one field for all records."""
        for r in self.records:
            if r.type == "record":
                r.set(field_name, field_data)
