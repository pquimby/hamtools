"""Tools for analyzing PSKReporter spots and identifying DX opportunities."""

'''
WARNING: This script queries the PSKRerporter website.
The authors of PSKReporter.info request respectful load on their servers.

Please use the --fetch option and rate limit yourself to avoid any issues.
You can run the script multiple times without re-fetching since the results are
cached locally in the .

If you are not respectful of our friends at PSKReporter, they will hunt you down,
tie you to a chair, and force you to listen to colonoscopy stories on 7.200 MHz
for the rest of your life.

The original purpose of this script was to decrease the load on the PSKReporter
servers because having many tabs open at once generates a lot of queries that
are not really useful, and it could be done with just one query.

Note: This script assumes that the input ADIF (if used) is from LoTW for QSL status.

Note: There are some weaknesses in string matching that arise when PSKReporter
reports DXCC names differently than LoTW. This is fixed by adding entries
to the dxcc.txt file for each DXCC entity.

Note: There are sometimes unranked DXCC entries. You can add entries into the
most_wanted.txt file to set a rank for these.
'''

import argparse
import json
import sys
import urllib.request
from typing import Dict, Any

from adif import ADIFFile

# TODO make band list more exhaustive
ALL_BANDS = [
    "13cm", "23cm", "70cm", "2m", "6m", "10m", "12m", "15m", "17m", "20m",
    "30m", "40m", "60m", "80m", "160m", "630m", "2200m", "GHZ",
    "UNK", "0m",
]

# TODO be more pedantic about definition of HF bands
HF_BANDS = [
    "80m", "40m", "30m", "20m", "17m", "15m", "12m", "10m", "6m"
]
MAX_DXCC_NUM = 600
IGNORED_CALLSIGNS = ["D1FF"] # Certain callsigns are annoying and not DX

def dxcc_name_strip(dxcc_input):
    """Strip and normalize DXCC entity names for consistent comparison."""
    return (dxcc_input.strip().upper()
            .replace(".", "")
            .replace(" ISLANDS", "")
            .replace(" ISLAND", "")
            .replace(" IS", ""))


def get_pskr_url(callsign, timerange=900):
    """Generate a PSKReporter URL for viewing spots for a given callsign within the last timerange seconds."""
    return (
        f"https://pskreporter.info/pskmap.html?preset&callsign={callsign}"
        f"&timerange={timerange}&hideunrec=1&blankifnone=1&hidepink=1"
        f"&showtx=1&showlines=1"
    )


def fetch_reports(tmp_file_path, app_contact, seconds=60*5, grid="FN"):
    """Query PSKReporter for reports in the last N seconds for a given grid and write to a filepath."""
    print("Fetching reports...")
    email = app_contact
    url = (
        'https://pskreporter.info/cgi-bin/pskquery5.pl?'
        'encap=1&callback=doNothing&statistics=1&noactive=true&'
        f'rronly=true&nolocator=1&flowStartSeconds=-{seconds}&'
        f'modify=grid&receiverCallsign={grid}&'
        'appcontact={email}'
    )

    user_agent = (
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    )

    request = urllib.request.Request(
        url,
        data=None,
        headers={'User-Agent': user_agent}
    )

    try:
        r = urllib.request.urlopen(request, timeout=120)

        try:
            with open(tmp_file_path, "w") as f:
                f.write(r.read().decode('utf-8'))
            print("   [Done]")
        except IOError as e:
            print(f"Error writing to temporary file {tmp_file_path}: {e}")
            raise
        except UnicodeDecodeError as e:
            print(f"Error decoding response from PSKReporter: {e}")
            raise

    except urllib.error.URLError as e:
        print(f"Error connecting to PSKReporter: {e}")
        raise
    except urllib.error.HTTPError as e:
        print(f"HTTP error from PSKReporter (code {e.code}): {e.reason}")
        raise
    except TimeoutError:
        print("Timeout while connecting to PSKReporter")
        raise
    except Exception as e:
        print(f"Unexpected error fetching reports: {e}")
        raise

def load_reports(tmp_file_path):
    """Load PSKReporter spots from file and return dict."""
    try:
        with open(tmp_file_path, "r", encoding="UTF-8") as f:
            try:
                # trim the non-json part of the response
                json_string = f.read()[46:-12]
                reports = json.loads(json_string)
                return reports
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from PSKReporter response: {e}")
                raise
            except IndexError as e:
                print(f"Error trimming PSKReporter response - response format may have changed: {e}")
                raise
            except Exception as e:
                print(f"Unexpected error processing PSKReporter response: {e}")
                raise
    except IOError as e:
        print(f"Error reading temporary file {tmp_file_path}: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error loading reports: {e}")
        raise

def load_logs(paths) -> Dict[int, Dict[str, Dict[str, Any]]]:
    """Load log files and return a dictionary of DXCC statuses."""
    dxcc2status: Dict[int, Dict[str, Dict[str, Any]]] = {}
    for i in range(1, MAX_DXCC_NUM):
        dxcc2status[i] = {}
        for band in ALL_BANDS:
            dxcc2status[i][band] = {
                "LOTW": 0,
                "IN LOG": 0,
                "lotw-example": None
            }

    for p in paths:
        try:
            with open(p, "r", encoding='utf-8', errors='ignore') as file_in:
                try:
                    log = ADIFFile()
                    log.parse(file_in, verbose=False)
                except Exception as e:
                    print(f"Error parsing ADIF file {p}: {e}")
                    continue

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

                if my_dxcc_number is None:
                    print("skipping over log for no MY_DXCC", r)
                    continue
                if dxcc_number is None or dxcc_number == 0:
                    # print("skipping over log for no DXCC", r)
                    continue

                if band is None:
                    print(f"QSO in log without band: {r}")
                if band not in ALL_BANDS:
                    print(f"ERROR!!! UNKNOWN BAND: {band}")
                    sys.exit(1)
                if not int(my_dxcc_number) == args.my_dxcc_num:
                    continue  # skip since I'm a US HAM in my DXCC account
                status = r.get("QSL_RCVD")
                if status == "Y":
                    dxcc2status[dxcc_number][band]['LOTW'] += 1
                    dxcc2status[dxcc_number][band]['lotw-example'] = r
                else:
                    # print(dxcc_number, my_dxcc_number, status)
                    dxcc2status[dxcc_number][band]['IN LOG'] += 1  # TODO: ARG (count worked)
        except IOError as e:
            print(f"Error opening log file {p}: {e}")
            continue
        except Exception as e:
            print(f"Unexpected error processing log file {p}: {e}")
            continue
    # print("log summary", dxcc2status)
    return dxcc2status


def relevant_rx(grid, grids):
    """Return relevant reports based on receiver grid string of comma-separated grids."""
    if grids is None or grids == []:
        return True

    grids = grids.split(",")
    for g in grids:
        if g in grid[0:4]:  # Note: future bug report... make regex against start to fix
            return True

    return False


def get_rank(tx_dxcc_code, most_wanted):
    """Get the rank of a DXCC entity based on its code."""
    lookup = [i for i, x in enumerate(most_wanted) if x == tx_dxcc_code]
    if not lookup:
        return None
    return lookup[0]


def relevant_tx(dxcc, most_wanted):
    """Determine if a DXCC entity is relevant based on its rank."""
    rank = get_rank(dxcc, most_wanted)
    # Return True if rank is None or less than max_rank
    # Lower ranks are more desirable DX entities (rank 1 = most wanted)
    # max_rank represents the worldwide rank threshold of the least interesting
    # DX entity to report
    if rank is None or rank < args.max_rank:
        return True

    return False


def get_interesting_reports(reports, dxcc2status, bands=None, verbose=False):
    """Return a list of reports that are interesting based on the receiver grid, band, and DXCC status."""
    if not dxcc2status:
        print("Did not receive log status input")
    interesting_reports = []
    odd_reports = []

    for r in reports['receptionReport']:
        if ("senderDXCCCode" not in r
                or "senderDXCC" not in r
                or "receiverLocator" not in r
                or "senderLocator" not in r
                or "frequency" not in r):

            if "frequency" not in r:
                continue  # skip the frequency-less reports

            if verbose:
                print("ODD SITUATION: ", r)
            if not r["senderCallsign"] in IGNORED_CALLSIGNS:
                odd_reports.append(r)
            continue

        rx_locator = r["receiverLocator"]
        tx_dxcc_code = r["senderDXCCCode"]
        tx_dxcc_name = dxcc_name_strip(r["senderDXCC"])
        tx_callsign = r["senderCallsign"]
        tx_locator = "UNK"
        if "senderLocator" in r.keys():
            tx_locator = r["senderLocator"]
        else:
            r["senderLocator"] = tx_locator

        mode = r["mode"]
        frequency = "UNKNOWN"
        band = None
        if "frequency" in r:
            frequency = int(r["frequency"])/1000000
            r["frequency"] = frequency
            band = get_band(r["frequency"])
            r["band"] = band
        snr = r['sNR']

        if tx_dxcc_name not in name2dxcc.keys():
            print("!!!")
            print(f"UNKNOWN DXCC: `{tx_dxcc_name}`")
            print("!!!")
            sys.exit(1)
        tx_dxcc_number = name2dxcc[tx_dxcc_name]

        rank = get_rank(tx_dxcc_code, most_wanted)
        lotw_confirmed = None
        if dxcc2status and band: # ignore null band reports
            if tx_dxcc_number in dxcc2status.keys():
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

        if rank is None:
            print(f"Using #200 priority for report from {tx_dxcc_code}")
            rank = 200
        r['rank'] = rank

        if dxcc2status and lotw_confirmed:
            continue
        if dxcc2status is None:
            if not relevant_tx(tx_dxcc_code, most_wanted):
                continue

        # filter out reports not near rx of interest / add info
        if not relevant_rx(rx_locator, args.rx_grid):
            continue

        if bands and band and band not in bands:
            continue

        interesting_reports.append(r)

    return (interesting_reports, odd_reports)


def get_interesting_dx(interesting_reports):
    """Extract and organize interesting DX opportunities from reports."""
    interesting_dx = {}
    for r in interesting_reports:
        rx_locator = r["receiverLocator"]
        tx_dxcc_code = r["senderDXCCCode"]
        tx_dxcc_name = r["senderDXCC"]
        tx_callsign = r["senderCallsign"]
        tx_locator = r["senderLocator"]
        mode = r["mode"]
        frequency = r["frequency"]
        snr = r['sNR']
        rank = r['rank']
        band = r['band']
        if tx_callsign not in interesting_dx.keys():
            interesting_dx[tx_callsign] = {
                    "senderDXCCCode": tx_dxcc_code,
                    "senderDXCC": tx_dxcc_name,
                    "senderCallsign": tx_callsign,
                    "mode": [mode,],
                    "frequency": [frequency,],
                    "rank": rank,
                    "receiverLocator": [rx_locator[0:4]],
                    "senderLocator": tx_locator[0:4],
                    "band": band
            }
        else:
            interesting_dx[tx_callsign]['receiverLocator'].append(rx_locator[0:4])
            interesting_dx[tx_callsign]['mode'].append(mode)
            interesting_dx[tx_callsign]['frequency'].append(frequency)

    return interesting_dx


def get_band(freq):
    """Determine the amateur radioband for a given frequency."""
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
    if freq < 0.1:  # an error
        return "0m"
    else:
        return "UNK"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
                    prog='PSKReporter DX Tools',
                    description="Fetches and analyzes PSKReporter spots for DX",
                    epilog='End Transmission')

    parser.add_argument('-f', '--fetch', action="store_true", help="Fetch PSKReporter data from the server instead of using the cache.")
    parser.add_argument('--app_contact', default="not-provided", help="Email address to use for PSKReporter API")
    parser.add_argument('--adi', help="Path to your LoTW ADIF file containing log to use for finding useful DX")
    parser.add_argument('--rx_grid', default=None, help="2-character or 4-character grid to filter reports by")
    parser.add_argument('-u', '--url', action='store_true', help="Print PSK URLs for each report")
    parser.add_argument('--modes', default=[]) #TODO: Implement
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help="Print out details like unusual report data"
    )
    parser.add_argument(
        '--hf',
        action='store_true',
        help="Filter reports to HF bands only (160m-6m). Ignored if --bands is specified."
    )
    parser.add_argument(
        '--bands',
        type=lambda x: [b for b in x.split(',') if b in ALL_BANDS],
        help="Comma-separated list of bands to filter reports by (must be one of the following: " + ", ".join(ALL_BANDS) + "). Overrides --hf if specified."
    )
    parser.add_argument(
        '--dxcc_file',
        type=str,
        help="Write out a debug .adi file at this path containing one example QSL from each DXCC entity from the --adi input log"
    )
    parser.add_argument(
        '-t', '--temp_filename',
        required=True,
        default=".pskr-tmp.xml",
        help="Path to the temporary file containing PSKReporter data after fetch to avoid re-fetching (use --fetch to fetch)"
    )
    parser.add_argument(
        '--my_dxcc_num',
        type=int,
        default=291,
        help="DXCC number of the user for filtering, since only home DXCC contacts count. (USA = 291)"
    )
    parser.add_argument(
        '--max_rank',
        type=int,
        default=300,
        help="Maximum rank of DX entities to report if no --adi. 300 is the default."
    )
    args = parser.parse_args()

    most_wanted = []
    try:
        most_wanted_file = open("most_wanted.txt", "r", encoding="utf-8")
    except IOError as e:
        print(f"Error opening most_wanted.txt file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error opening most_wanted.txt: {e}")
        sys.exit(1)
    for line in most_wanted_file:
        items = line.split(" ")
        most_wanted.append(items[1])

    dxcc2name = {}
    name2dxcc = {}
    try:
        dxcc_file = open("dxcc.txt", "r", encoding="utf-8")
    except IOError as e:
        print(f"Error opening dxcc.txt file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error opening dxcc.txt: {e}")
        sys.exit(1)
    for line in dxcc_file:
        items = line.split(",")
        dxcc_number = int(items[0])
        dxcc_name = dxcc_name_strip(" ".join(items[1:]))
        dxcc2name[dxcc_number] = dxcc_name
        name2dxcc[dxcc_name] = dxcc_number

    dxcc2status = None
    if args.adi is not None:
        dxcc2status = load_logs([args.adi,])

    input_file = args.temp_filename

    if args.dxcc_file:
        try:
            dxcc_log = ADIFFile()
            with open(args.dxcc_file, "w", encoding="utf-8") as dxcc_out_file:
                if dxcc2status is not None:
                    for v, k in enumerate(dxcc2status):
                        for v2, b in enumerate(dxcc2status[k]):
                            example = dxcc2status[k][b]['lotw-example']
                            if example:
                                dxcc_log.records.append(example)
                try:
                    dxcc_log.write(dxcc_out_file)
                    print(f"Wrote DXCC example QSLs to {args.dxcc_file}")
                except Exception as e:
                    print(f"Error writing DXCC file: {e}")
        except IOError as e:
            print(f"Error opening DXCC output file {args.dxcc_file}: {e}")
        except Exception as e:
            print(f"Unexpected error processing DXCC file: {e}")
    odd_reports = []

    if args.fetch:
        # Validate app_contact is a valid email address
        import re
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not hasattr(args, 'app_contact') or not re.match(email_regex, args.app_contact):
            print("Error: --app-contact must be a valid email address")
            sys.exit(1)

        app_contact = args.app_contact.replace('@', '%40')
        fetch_reports(input_file, app_contact, grid=args.rx_grid)

    reports = load_reports(input_file)
    for r in reports['receptionReport']:
        lookup1 = None
        lookup2 = None
        if "senderDXCC" in r.keys():
            tx_dxcc = dxcc_name_strip(r["senderDXCC"])
            if tx_dxcc in name2dxcc.keys():
                lookup1 = name2dxcc[tx_dxcc]
            else:
                print("UNKNOWN DXCC", dxcc_name_strip(r["senderDXCC"]))
        if "receiverDXCC" in r.keys():
            rx_dxcc = dxcc_name_strip(r["receiverDXCC"])
            if rx_dxcc in name2dxcc.keys():
                lookup2 = name2dxcc[rx_dxcc]
            else:
                print("UNKNOWN DXCC", rx_dxcc)

    # Determine which bands to filter on
    filter_bands = None
    if args.bands:
        filter_bands = args.bands
    elif args.hf:
        filter_bands = HF_BANDS
    else:
        filter_bands = ALL_BANDS
    print(f"Filtering reports for bands: {filter_bands}")

    interesting_reports, odd_reports = get_interesting_reports(
        reports,
        dxcc2status,
        bands=filter_bands,
        verbose=args.verbose
    )

    interesting_dx = get_interesting_dx(interesting_reports)

    report_count = len(reports['receptionReport'])
    interesting_report_count = len(interesting_reports)

    print(
        f'Fetched {report_count} reports. '
        f'{interesting_report_count}/{report_count} '
        f'({round(interesting_report_count*100.0/report_count,1)}%) interesting'
    )
    print()
    print(
        '          Code DXCC Name                Mode  Freq  Band Rank '
        'Callsign   Grid          Grid'
    )

    for r in sorted(interesting_dx.values(), key=lambda r: (r["frequency"], r["senderCallsign"])):
        rx_locator = r["receiverLocator"]
        tx_dxcc_code = r["senderDXCCCode"]
        tx_dxcc_name = r["senderDXCC"]
        tx_dxcc_name_strip = dxcc_name_strip(tx_dxcc_name)
        tx_callsign = r["senderCallsign"]
        tx_locator = r["senderLocator"]
        mode = r["mode"]
        frequency = r["frequency"]
        band = r["band"]
        rank = r['rank']
        dxcc_number = name2dxcc[tx_dxcc_name_strip]

        # Format the output components
        mode_str = ",".join(set(mode))
        freq_str = ",".join(set([format(round(f, 3), "6.3f") for f in frequency]))
        band_str = ",".join(set([get_band(f) for f in frequency]))
        rx_str = ",".join(sorted(set(rx_locator))[0:20])

        print(
            f'Relevant: {tx_dxcc_code.ljust(4)} '
            f'{str(name2dxcc[tx_dxcc_name_strip]).ljust(3)} '
            f'{tx_dxcc_name.ljust(20)[-20:]} {mode_str.ljust(5)} {freq_str} '
            f'{band_str} #{str(rank).ljust(3)} {tx_callsign.ljust(10)} '
            f'{tx_locator} heard in {rx_str}'
        )
        if args.url:
            print(f"{get_pskr_url(tx_callsign)}")

    if args.verbose:
        print()
        print("ODD REPORTS:")
        odd_summary = {}
        for o in odd_reports:
            summary = {}
            callsign = o["senderCallsign"]
            summary["senderCallsign"] = callsign
            odd_summary[callsign] = summary

        for k, v in enumerate(odd_summary):
            print(f"{v}")
