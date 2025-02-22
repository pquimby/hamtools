# Scripts

## dx.py

This script is used to fetch PSKReporter spots and extract DXCC QSO opportunities. It can be used with a personal log file
to customize the query to your specific band slot needs, or use general DXCC rank to query generally interesting DXCC entities.

Example usage for query without a personal log file:
```python3 dx.py -t .temp --rx_grid CM --app_contact your@email --hf --max_rank 300 -u --fetch```

Example usage for query with a personal log file:
```python3 dx.py --adi my_log.adi -t .temp --rx_grid CM --app_contact your@email --hf --fetch```

## sync.py

This script is used to fetch an ADIF file from LoTW and save it to a local file.

Example usage: ```lotw-sync.py -o ~/my_lotw_download.adif --fetch --grid CM87```

## potify.py

This script is used to convert an ADIF to a minimum compliant POTA upload.

Example usage: TBD