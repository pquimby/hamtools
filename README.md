# Scripts

## dx.py

This script is used to process ADIF files and extract DXCC statuses.

Example usage for query without a personal log file:
```python3 dx.py -t .temp --rx_grid CM --app_contact your@email --hf --max_rank 300 -u --fetch```

Example usage for query with a personal log file:
```python3 dx.py --adi my_log.adi -t .temp --rx_grid CM --app_contact your@email --hf --fetch```

## sync.py

This script is used to fetch an ADIF file from LoTW and save it to a local file.

Example usage: TBD

## potify.py

This script is used to convert an ADIF to a minimum compliant POTA upload.

Example usage: TBD