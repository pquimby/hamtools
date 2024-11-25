import re

class ADIFRow:
    def __init__(self, string):
        self.string = string

    def set(self, field_name, field_data):
        self.field_name = field_name
        self.field_data = field_data
        self.field_length = len(field_data)

    def parse(self):
        #<F:L:T>D

        results = re.search("^<(\w+):(\d+):?(\w+)?>(.*)", self.string)
        if results:
            self.field_name = results.group(1)
            self.field_length = int(results.group(2))
            self.field_type = results.group(3)
            self.field_data = results.group(4).strip()
            return True
        else:
            return False

    def validate(self):
        # TODO: fix validation due to out of spec comments after //
        return True #self.field_length == len(self.field_data[0:])

    def __str__(self):
        # TODO: support field_type iff provided
        data = self.field_data
        if self.field_name == "CALL":
            data = data.ljust(8, " ")
        return f'<{self.field_name}:{self.field_length}>{data}'

class ADIFRecord:
    def __init__(self):
        self.rows = []
        self.type = "record"

    def __add__(self, row):
        self.rows.append(row)
        return self

    def __len__(self):
        return len(self.rows)

    def get(self, field_name):
        for row in self.rows:
            if row.field_name.upper() == field_name.upper():
                return row.field_data
        return None

    def __str__(self):
        result = ""
        for row in self.rows:
            result += str(row) + " "
        if self.type == "record":
            result += "<eor>"
        elif self.type == "header":
            result += "<eoh>\n\n"
        return result

    def remove_except(self, allowed_fields):
        #print(f'Removing all except {allowed_fields} in {len(self.rows)} rows...')

        filter = [f.upper() for f in allowed_fields]
        self.rows = [r for r in self.rows if r.field_name.upper() in filter]
        for r in self.rows:
            r.field_name = r.field_name.upper()
        #print(f'   [DONE]')

    def set(self, field_name, field_data):
        found = False
        for r in self.rows:
            if r.field_name.upper() == field_name.upper():
                r.field_name = r.field_name.upper()
                r.field_data = field_data
                r.field_length = len(field_data)
                found = True

        if not found:
            new_row = ADIFRow(None)
            new_row.set(field_name.upper(), field_data)
            self += new_row

class ADIFFile:
    def __init__(self):
        self.records = []

    def parse(self, input_file, verbose=False):
        current_entry = ADIFRecord()
        input_rows = []
        for i,row in enumerate(input_file):
            #print(i,row.strip())
            # If format uses single lines, split into multiple lines
            if row.count("<") > 1:
                #print("Identified row as single line type.")
                content = row.replace("<","\n<")
                #print("New row: *******")
                #print(content)
                #print("/>")
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
                    print(f'Row "{row.strip()}" didn\'t validate')
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
        print(f'   Parsed {len(self.records)} records into ADIFFile')
        if verbose:
            for r in self.records:
                print(len(r), r)

    def write(self, output_file, test=None):
        count = 0
        for r in self.records:
            if (r.type == "header") or (test == None) or (test and test(r)):
                output_file.write(str(r))
                output_file.write("\n")
                count += 1
        print(f'   Wrote {count} records')

    def remove_except(self, allowed_fields):
        #print(f'Removing all except {allowed_fields} from {len(self.records)} records')
        for r in self.records:
            if r.type == "record":
                r.remove_except(allowed_fields)

    def set_all(self, field_name, field_data):
        for r in self.records:
            if r.type == "record":
                r.set(field_name, field_data)
