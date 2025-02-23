"""A tool for downloading logs from LoTW into a local ADIF file."""

import argparse
import datetime
import json
import requests
import sys
import time

from adif import ADIFFile


def load_auth(filepath):
    """Load authentication credentials from a JSON file at the filepath."""
    try:
        with open(filepath, "r", encoding='utf-8') as auth_file:
            auth = json.load(auth_file)
        return auth
    except FileNotFoundError:
        print(f"Error: Authentication file '{filepath}' not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Authentication file '{filepath}' contains invalid JSON")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading authentication file: {str(e)}")
        sys.exit(1)


def lotw_fetch(qso_time_horizon, callsign, details=True):
    """Fetch logs from LoTW and save to a file."""
    auth_filename = "auth.json"
    print(f'Loading auth from {auth_filename}...')
    auth = load_auth(auth_filename)

    USERNAME = auth['USERNAME']
    PASSWORD = auth['PASSWORD']
    CALLSIGN = callsign

    print(f'   Identified as "{USERNAME}" + "{CALLSIGN}"')
    print(f'   Password as "{"".join(["*"]*len(PASSWORD))}"')

    if details:
        details = "yes"

    print(f'Fetching logs from LoTW... at {datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")} local')

    qso_qslsince = qso_time_horizon  # updated since
    qso_qsorxsince = qso_time_horizon  # rx since

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
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
    except requests.exceptions.Timeout:
        print("Error: Request timed out while connecting to LoTW")
        return None
    except requests.exceptions.ConnectionError:
        print("Error: Failed to connect to LoTW - check your internet connection")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Error: HTTP error occurred: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error: An error occurred while fetching logs: {e}")
        return None
    end_time = time.time()
    print("   Return: ", r.status_code)

    # If failure, bail
    if r.status_code != 200:
        print(r.text)
        print("   [Done]")
        return None

    print("   Fetch completed successfully in %0.1f seconds"%(end_time-start_time))
    print("   [Done]")
    return r


def fetch_lotw_to_file(temp_filename, since, callsign, details=True):
    """Fetch logs from LoTW and save to a temporary ADIF file."""
    with open(temp_filename, 'w+', encoding='utf-8') as out:
        raw = lotw_fetch(since, callsign, details)
        if raw is None:
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

            if not found_eoh:
                continue
        print("   [Done]")


def read_adif_file(filename):
    """Read and parse an ADIF file, returning ADIFFile object."""
    print(f'Reading from {filename}...')
    adif = ADIFFile()
    try:
        with open(filename, "r", encoding='utf-8') as f:
            try:
                adif.parse(f)
            except Exception as e:
                print(f"ERROR: Failed to parse ADIF file: {str(e)}")
                sys.exit(1)
    except FileNotFoundError:
        print(f"ERROR: Could not find file {filename}")
        sys.exit(1)
    except PermissionError:
        print(f"ERROR: Permission denied accessing {filename}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to open {filename}: {str(e)}")
        sys.exit(1)
    print("   [DONE]")
    return adif


def write_filtered_adif(adif, output_filename, grid_filter):
    """Write ADIF data to file, filtered by grid square."""
    print(f'Starting write to "{output_filename}" ...')
    try:
        with open(output_filename, "w", encoding='utf-8') as f2:
            print(f'   Filtering down to gridsquare: {grid_filter}')
            def grid_filter_func(r):
                return (r.get("MY_GRIDSQUARE") and
                       grid_filter in r.get("MY_GRIDSQUARE"))
            adif.write(f2, grid_filter_func)
    except FileNotFoundError:
        print(f"ERROR: Could not create output file {output_filename}")
        sys.exit(1)
    except PermissionError:
        print(f"ERROR: Permission denied writing to {output_filename}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to write to {output_filename}: {str(e)}")
        sys.exit(1)
    print('   [DONE]')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
                    prog='lotw-sync',
                    description="Fetches log files from LoTW's API to your local computer",
                    epilog='End Transmission')

    # TODO: Add help text
    parser.add_argument(
        '-o', '--output_filename',
        required=True,
        help="The output ADIF filepath to write to"
    )
    parser.add_argument(
        '-t', '--temp_filename',
        default=".lotw-tmp.adi",
        help="A temporary ADIF filepath to write to for caching purposes"
    )
    parser.add_argument(
        "--details",
        action="store_true",
        default=True,
        help="Whether to include detailed QSO information in the output"
    )
    parser.add_argument(
        "-f", "--fetch",
        action="store_true",
        default=True,
        help=(
            "Whether to fetch the logs from LoTW or use the cached file. "
            "This is useful if you want to change the filtering on the same query. "
            "Keep in mind LoTW rate limts the number of fetches you can make."
        )
    )
    parser.add_argument("-s", "--since", default="1970-01-01", help="The date after which to fetch QSOs")
    parser.add_argument("-c", "--callsign", default=None, help="Fetch QSOs for a specific callsign or leave blank for all")
    parser.add_argument("-g", "--my_grid", default="", help="Filter to only include QSOs from a specific grid square")
    args = parser.parse_args()

    temp_filename = args.temp_filename
    output_filename = args.output_filename
    details = args.details
    since = args.since
    fetch = args.fetch
    grid_filter = args.my_grid
    callsign = args.callsign

    if fetch:
        fetch_lotw_to_file(temp_filename, since, callsign, details)
    else:
        print("Skipping fetch.")

    adif = read_adif_file(temp_filename)
    write_filtered_adif(adif, output_filename, grid_filter)
    print("   [DONE]")

