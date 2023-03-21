import re

class ADIFRow:
    def __init__(self, string):
        self.string = string
    
    def parse(self):
        #<F:L:T>D
        results = re.search("^<(\w+):(\d+):?(\w+)?>(.*)$", self.string)
        if results:
            self.field_name = results.group(1)
            self.field_length = int(results.group(2))
            self.field_type = results.group(3)
            self.field_data = results.group(4)
            return True
        else:
            return False
    
    def validate(self):
        # TODO: fix validation due to out of spec comments after //
        return True #self.field_length == len(self.field_data[0:])
    
    def __str__(self):
        # TODO: support field_type iff provided
        return f'<{self.field_name}:{self.field_length}>{self.field_data}'
        
class ADIFRecord:
    def __init__(self):
        self.rows = []
        self.type = "record"
    
    def __add__(self, row):
        self.rows.append(row)
        return self
        
    def get(self, field_name):
        for row in self.rows:
            if row.field_name.lower() == field_name.lower():
                return row.field_data
        return None
    
    def __str__(self):
        result = ""
        for row in self.rows:
            result += str(row) + "\n"
        if self.type == "record":
            result += "<eor>\n"
        elif self.type == "header":
            result += "<eoh>\n"
        return result

class ADIFFile:
    def __init__(self):
        self.records = []
        self.headers = []
    
    def parse(self, input_file, verbose=False):
        current_entry = ADIFRecord()
        for row in input_file:
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
    
    def write(self, output_file, test=None):
        count = 0
        for r in self.records:
            if (r.type == "header") or (test == None) or (test and test(r)):
                output_file.write(str(r))
                output_file.write("\n")
                count += 1
        print(f'   Wrote {count} records')