
from adif import ADIFFile
import xmltodict
import sys
import urllib.request
import argparse

ALL_BANDS = ["13cm","70cm", "2m", "6m", "10m", "12m", "15m", "17m", "20m", "30m", "40m", "60m", "80m", "160m","630m","2200m","GHZ","UNK","0m", "23cm"]
MAX_DXCC_NUM = 600

#print(reports)

def name_strip(input):
    return input.strip().upper().replace(".","").replace(" ISLANDS","").replace(" ISLAND","").replace(" IS","")

def get_pskr_url(callsign):
    return f"https://pskreporter.info/pskmap.html?preset&callsign={callsign}&timerange=900&hideunrec=1&blankifnone=1&hidepink=1&showtx=1&showlines=1"

'''
Query PSKReporter for reports and write to file
'''
def fetch_reports(tmp_file_path, seconds=60*1, seqno=0, mode="FT8"):

    print("Fetching reports...")

    url = f'https://retrieve.pskreporter.info/query?noactive=true&flowStartSeconds=-{seconds}&rronly=true&statistics=true&appcontact=paul.quimby%40gmail.com&mode={mode}'
    if seqno != 0 and seqno != None:
        url += f'&lastseqno={seqno}'
    
    #url = f'https://pskreporter.info/cgi-bin/pskquery5.pl?encap=1&callback=doNothing&statistics=1&noactive=1&nolocator=1&flowStartSeconds=-{seconds}&mode={mode}&modify=grid&receiverCallsign=FN'

    request = urllib.request.Request(
    url,
    data=None,
    headers={
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    })
    r = urllib.request.urlopen(request)

    f = open(tmp_file_path, "w")
    f.write(r.read().decode('utf-8'))
    f.close()

    print("   [Done]")

'''
Load PSKReporter spots from file and return dict
'''
def load_reports(tmp_file_path):
    f = open(tmp_file_path, "r", encoding="UTF-8")

    xml_string=f.read()
#    xml_string = xml_string[18:-5]
    reports=xmltodict.parse(xml_string)
    #print(reports.keys())
    #print(reports['js'][10:])
    f.close()

    return reports

def load_logs(paths):
    dxcc2status = {}
    for i in range(1,MAX_DXCC_NUM):
        dxcc2status[i]={}
        for band in ALL_BANDS:
            dxcc2status[i][band] = {
                "LOTW": 0,
                "IN LOG": 0
            }

    for p in paths:
        file_in = open(p, "r", encoding='utf-8', errors='ignore')
        log = ADIFFile()
        log.parse(file_in, verbose=False)
        file_in.close()

        for r in log.records:
            if r.type == "header":
                continue

            dxcc_number = r.get("DXCC")
            my_dxcc_number = r.get("MY_DXCC")
            if dxcc_number:
                dxcc_number = int(dxcc_number)
            if my_dxcc_number:
                my_dxcc_number = int(my_dxcc_number)
            band = r.get("BAND").lower()

            if my_dxcc_number == None:
                print("skipping over log for no MY_DXCC", r)
                continue
            if dxcc_number == None or dxcc_number == 0:
                #print("skipping over log for no DXCC", r)
                continue

            if band == None:
                print(f"QSO in log without band: {r}")
            if not band in ALL_BANDS:
                print(f"ERROR!!! UNKNOWN BAND: {band}")
                sys.exit(1)
            if not int(my_dxcc_number) == 291: #TODO ARG
                continue # skip since I'm a US HAM in my DXCC account
            status = r.get("QSL_RCVD")
            if status == "Y":
                #print(dxcc_number, my_dxcc_number, status)
                dxcc2status[dxcc_number][band]['LOTW'] += 1
            else:
                #print(dxcc_number, my_dxcc_number, status)
                dxcc2status[dxcc_number][band]['IN LOG'] += 1 # TODO ARG (count worked)
    #print("log summary", dxcc2status)
    return dxcc2status

def relevant_rx(grid, grids):
    if grids == None or grids == []:
        return True

    grids = grids.split(",")
    for g in grids:
        if g in grid[0:4]: #Note: future bug report... make regex against start to fix
            return True

    return False

def get_rank(tx_dxcc_code, most_wanted):
    lookup = [i for i,x in enumerate(most_wanted) if x == tx_dxcc_code]
    if lookup == []:
        return None
    else:
        return lookup[0] # first column is rank field

def relevant_tx(dxcc, most_wanted):
    rank = get_rank(dxcc, most_wanted)

    if rank == None or rank < 300:
        return True

    return False

def get_interesting_reports(reports, dxcc2status, bands = None, verbose = False):
    if not dxcc2status:
        print("Did not receive log status input")
    interesting_reports = []
    odd_reports = []
    
    last_sequence_number = int(reports['receptionReports']['lastSequenceNumber']['@value'])
    print("Last sequence: " + str(last_sequence_number))
    
    for r in reports['receptionReports']['receptionReport']:

        if not "@senderDXCCCode" in r \
            or not "@senderDXCC" in r \
            or not "@receiverLocator" in r \
            or not "@senderLocator" in r \
            or not "@frequency" in r:

            if not "@frequency" in r:
                continue # skip the frequency-less reports

            if verbose:
                print("ODD SITUATION: ", r)
            if not r["@senderCallsign"] in ["D1FF",]:
                odd_reports.append(r)
            continue

        rx_locator = r["@receiverLocator"]
        tx_dxcc_code = r["@senderDXCCCode"]
        tx_dxcc_name = name_strip(r["@senderDXCC"])
        tx_callsign = r["@senderCallsign"]
        tx_locator = "UNK"
        if "@senderLocator" in r.keys():
            tx_locator = r["@senderLocator"]
        else:
            r["@senderLocator"] = tx_locator

        mode = r["@mode"]
        frequency = "UNKNOWN"
        band = None
        if "@frequency" in r:
            #frequency = str(int(r["@frequency"])/1000000).rjust(10)
            frequency = int(r["@frequency"])/1000000
            r["@frequency"] = frequency
            band = get_band(r["@frequency"])
            r["@band"] = band
        snr = r['@sNR']
        #print(name2dxcc)

        if tx_dxcc_name not in name2dxcc.keys():
            print("!!!")
            print(f"UNKNOWN DXCC: `{tx_dxcc_name}`")
            print("!!!")
            sys.exit(1)
        tx_dxcc_number = name2dxcc[tx_dxcc_name]
        #print(tx_dxcc_number, r)

        rank = get_rank(tx_dxcc_code, most_wanted)
        lotw_confirmed = None
        if dxcc2status and band: # ignore null band reports
            if tx_dxcc_number in dxcc2status.keys():
                #print(f"looking up {tx_dxcc_number}:{band} -> {dxcc2status[tx_dxcc_number][band]}")
                if band == "UNK":
                    print("Received NON-US band report:")
                    print(r)
                    continue
                if dxcc2status[tx_dxcc_number][band]['LOTW'] > 0:
                    # LOTW QSL in log
                    lotw_confirmed = True
                else:
                    lotw_confirmed = False
            else:
                print(f"Encountered unknown tx_dxcc_number {tx_dxcc_number}")
                sys.exit(1)

        if rank == None:
            print(f"Using #200 priority for report from {tx_dxcc_code}")
            rank = 200
        r['@rank'] = rank

        if dxcc2status and lotw_confirmed:
            # relevant!
            continue
        if dxcc2status == None:
            #print("Using fallback logic beacuse no dxcc2status/adi used")
            if not relevant_tx(tx_dxcc_code, most_wanted):
                continue

        # filter out reports not near rx of interest / add info
        if not relevant_rx(rx_locator, args.rx_grids):
            continue
        #     r["@hearable"] = False
        # else:
        #     r["@hearable"] = True

        if bands and band and not band in bands:
            continue

        interesting_reports.append(r)
        #print(f"Adding {r} because {lotw_confirmed} based on {dxcc2status[tx_dxcc_number][band]}")

    return (interesting_reports, odd_reports)

def get_interesting_dx(interesting_reports):
    interesting_dx = {}
    for r in interesting_reports:
        rx_locator = r["@receiverLocator"]
        tx_dxcc_code = r["@senderDXCCCode"]
        tx_dxcc_name = r["@senderDXCC"]
        tx_callsign = r["@senderCallsign"]
        tx_locator = r["@senderLocator"]
        mode = r["@mode"]
        frequency = r["@frequency"]
        snr = r['@sNR']
        rank = r['@rank']
        band = r['@band']
        if not tx_callsign in interesting_dx.keys():
            interesting_dx[tx_callsign] = {
                    "@senderDXCCCode": tx_dxcc_code,
                    "@senderDXCC": tx_dxcc_name,
                    "@senderCallsign": tx_callsign,
                    "@mode": [mode,],
                    "@frequency": [frequency,],
                    "@rank": rank,
                    "@receiverLocator": [rx_locator[0:4]],
                    "@senderLocator": tx_locator[0:4],
                    "@band": band
            }
        else:
            interesting_dx[tx_callsign]['@receiverLocator'].append(rx_locator[0:4])
            interesting_dx[tx_callsign]['@mode'].append(mode)
            interesting_dx[tx_callsign]['@frequency'].append(frequency)

    return interesting_dx

def get_band(freq):
    if freq > 2300:
        return "GHZ"
    if freq > 144 and freq < 148:
        return "2m"
    if freq > 219 and freq < 225:
        return "1.25"
    if freq > 420 and freq < 450:
        return "70cm"
    if freq > 902 and freq < 928:
        return "33cm"
    if freq > 1240 and freq < 1300:
        return "23cm"
    if freq > 50.0 and freq < 54.0:
        return "6m"
    if freq > 28.0 and freq < 29.7:
        return "10m"
    if freq > 24.890 and freq < 24.990:
        return "12m"
    if freq > 21.00 and freq < 21.45:
        return "15m"
    if freq > 17.068 and freq < 18.168:
        return "17m"
    if freq > 14.00 and freq < 14.35:
        return "20m"
    if freq > 10.1 and freq < 10.15:
        return "30m"
    if freq > 7.0 and freq < 7.3:
        return "40m"
    if freq > 5.3 and freq < 5.5:
        return "60m"
    if freq > 3.5 and freq < 4.0:
        return "80m"
    if freq > 1.8 and freq < 2.0:
        return "160m"
    if freq > 0.472 and freq < 479:
        return "630m"
    if freq > 0.135 and freq < 0.1378:
        return "2200m"
    if freq <0.1: # an error
        return "0m"
    else:
        return "UNK"

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
                    prog='PSKReporter DX Tools',
                    description="Fetches and analyzes PSKReporter spots for DX",
                    epilog='End Transmission')

    parser.add_argument('-t', '--temp_filename', required=True, default=".pskr-tmp.xml")
    parser.add_argument('-f', '--fetch', action="store_true")
    parser.add_argument('--adi')
    parser.add_argument('--rx_grids', default=None)
    parser.add_argument('-u', '--url', action='store_true')
    parser.add_argument('--modes', default = [])
    parser.add_argument('-v', '--verbose', action='store_true', help="Print out details like unusual report data")
    parser.add_argument('-s', metavar="seqno", help="Sequence number to start fetch for PSKReporter")
    args = parser.parse_args()

    most_wanted = []
    most_wanted_file = open("most_wanted.txt", "r")
    for line in most_wanted_file:
        items = line.split(" ")
        most_wanted.append(items[1])
    #print(most_wanted[300:])

    dxcc2name = {}
    name2dxcc = {}
    dxcc_file = open("dxcc.txt", "r")
    for line in dxcc_file:
        items = line.split(",")
        dxcc_number = int(items[0])
        dxcc_name = name_strip(" ".join(items[1:]))
        dxcc2name[dxcc_number] = dxcc_name
        name2dxcc[dxcc_name] = dxcc_number
    #print(dxcc2name)

    dxcc2status = None
    if args.adi != None:
        dxcc2status = load_logs([args.adi,])

    input_file = args.temp_filename
    seqno = None
    if "s" in args and args.s != None:
        seqno = int(args.s)

    odd_reports = []

    if args.fetch:
        fetch_reports(input_file, seqno=seqno)

    reports = load_reports(input_file)
    for r in reports['receptionReports']['receptionReport']:
        lookup1 = None
        lookup2 = None
        if "@senderDXCC" in r.keys():
            tx_dxcc = name_strip(r["@senderDXCC"])
            if tx_dxcc in name2dxcc.keys():
                lookup1 = name2dxcc[tx_dxcc]
            else:
                print("UNKNOWN DXCC", name_strip(r["@senderDXCC"]))
        if "@receiverDXCC" in r.keys():
            rx_dxcc = name_strip(r["@receiverDXCC"])
            if rx_dxcc in name2dxcc.keys():
                lookup2 = name2dxcc[rx_dxcc]
            else:
                print("UNKNOWN DXCC", rx_dxcc)

#    print(reports['receptionReports']['receptionReport'])

    interesting_reports, odd_reports = get_interesting_reports(reports, dxcc2status, bands = ["80m","40m","30m","20m","17m","15m","12m","10m","6m"], verbose=args.verbose)

    interesting_dx = get_interesting_dx(interesting_reports)

    report_count = len(reports['receptionReports']['receptionReport'])
    interesting_report_count = len(interesting_reports)

    print(f'Fetched {report_count} reports. {interesting_report_count}/{report_count} ({round(interesting_report_count*100.0/report_count,1)}%) interesting')
    print()

    for r in sorted(interesting_dx.values(), key=lambda r: (r["@rank"], r["@senderCallsign"])):
        rx_locator = r["@receiverLocator"]
        tx_dxcc_code = r["@senderDXCCCode"]
        tx_dxcc_name = r["@senderDXCC"]
        tx_dxcc_name_strip = name_strip(tx_dxcc_name)
        tx_callsign = r["@senderCallsign"]
        tx_locator = r["@senderLocator"]
        mode = r["@mode"]
        frequency = r["@frequency"]
        band = r["@band"]
        #snr = r['@sNR']
        rank = r['@rank']
        dxcc_number = name2dxcc[tx_dxcc_name_strip]
        print(f'Relevant: {tx_dxcc_code.ljust(4)} {str(name2dxcc[tx_dxcc_name_strip]).ljust(3)} {tx_dxcc_name.ljust(20)[-20:]} {",".join(set(mode))} {",".join(set([format(round(f,3),"6.3f") for f in frequency]))} {",".join(set([get_band(f) for f in frequency]))} #{str(rank).ljust(3)} {tx_callsign.ljust(10)} {tx_locator} heard in {",".join(rx_locator)}')
        #print(f"{dxcc2status[dxcc_number][band]}")
        if args.url:
            print(f"{get_pskr_url(tx_callsign)}")

    if args.verbose:
        print()
        print("ODD REPORTS:")
        odd_summary = {}
        for o in odd_reports:
            summary = {}
            callsign = o["@senderCallsign"]
            summary["@senderCallsign"] = callsign
            odd_summary[callsign] = summary

        for k,v in enumerate(odd_summary):
            print(f"{v}")
