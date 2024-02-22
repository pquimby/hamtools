import argparse
import datetime
import json
import requests
import sys
import time
from adif import ADIFFile

def load_auth(f):
    auth = json.load(f)
    return auth

def lotw_fetch(out, qso_time_horizon, details, callsign):
    auth_filename = "auth.json"
    print(f'Loading auth from {auth_filename}...')
    auth_file = open(auth_filename, "r")
    auth = load_auth(auth_file)
    USERNAME = auth['USERNAME']
    PASSWORD = auth['PASSWORD']
    CALLSIGN = callsign
    print(f'   Identified as "{USERNAME}" + "{CALLSIGN}"')
    print(f'   Password as "{"".join(["*"]*len(PASSWORD))}"')

    if details:
        details = "yes"
    
    print(f'Fetching logs from LoTW... at {datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")} local')
    
    qso_qslsince = qso_time_horizon # updated since
    qso_qsorxsince = qso_time_horizon # rx since
    
    print(f'Fetching logs since {qso_qsorxsince} updated since {qso_qslsince}')
    start_time = time.time()
    url = 'https://lotw.arrl.org/lotwuser/lotwreport.adi'
    params = {
        'login': USERNAME,
        'password': PASSWORD,
        'qso_query': '1',
        'qso_qsl': 'no',
        'qso_qslsince': qso_qslsince,
        'qso_qsorxsince': qso_qsorxsince,
        'qso_owncall': callsign,
        'qso_mydetail': details,
        'qso_qsldetail': details
    }
    r = requests.get(url, params=params)
    end_time = time.time()
    print("   Return: ", r.status_code)
    
    # If failure, bail
    if r.status_code != 200:
        print(r.text)
        return None
        
    print("   Fetch completed successfully in %0.1f seconds"%(end_time-start_time))
    print("   [Done]")
    return r
    
if __name__ == "__main__":

    parser = argparse.ArgumentParser(
                    prog='lotw-sync',
                    description="Syncs log files from LoTW's API to your local computer",
                    epilog='End Transmission')

    parser.add_argument('-o', '--output_filename')
    parser.add_argument('-t', '--temp_filename', default=".lotw-sync-tmp.adif")
    parser.add_argument("--details", action="store_true", )
    parser.add_argument("--since", default="2023-03-01")
    parser.add_argument("-c", "--callsign", default=None)
    parser.add_argument("-f", "--fetch", action="store_true")
    parser.add_argument("-g", "--grid", default="")
    args = parser.parse_args()
    
    "lotw-sync.py -o ~/output.adif --details"
    
    temp_filename = args.temp_filename
    output_filename = args.output_filename
    details = args.details
    since = args.since
    fetch = args.fetch
    grid_filter = args.grid
    callsign = args.callsign
    
    if fetch:
        out = open(temp_filename, 'w+')
        raw = lotw_fetch(out, since, details, callsign)
        if raw == None:
            print("ERROR: Stopping after failed fetch")
            sys.exit(1)
        
        print(f'Starting write to "{temp_filename}" ...')
        found_eoh = False
        for line in raw.text.splitlines(True):
            if "PROGRAMID" in line:
                found_eoh = True
                print("   Found header...")
        
            if "<APP_LoTW_EOF>" in line:
                break
        
            if found_eoh:
                out.write(line)
        
            if found_eoh == False:
                continue
        out.close()
        print("   [Done]")
    else:
        print("Skipping fetch.")
    
    print(f'Reading from {temp_filename}...')
    f = open(temp_filename, "r")
    adif = ADIFFile()
    adif.parse(f)
    print("   [DONE]")
    
    print(f'Starting write to "{output_filename}" ...')
    f2 = open(output_filename, "w")
    print(f'   Filtering down to gridsquare: {grid_filter}')
    filter = lambda r : (r.get("MY_GRIDSQUARE") and grid_filter in r.get("MY_GRIDSQUARE"))
    adif.write(f2, filter)
    f2.close()
    print('   [DONE]')
    
