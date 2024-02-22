from adif import ADIFFile
import re
import sys

if __name__ == "__main__":
    
    in_path = sys.argv[1]
    out_path_prefix = sys.argv[2]
    parks = []
    out_paths = []
    
    file_in = open(in_path, "r")
    
    log = ADIFFile()
    log.parse(file_in, verbose=False)
    file_in.close()
    
    allowed_fields = ["COMMENT", "STATION_CALLSIGN", "CALL", "QSO_DATE", "TIME_ON","BAND","MODE","SUBMODE","OPERATOR","MY_SIG","MY_SIG_INFO","SIG","SIG_INFO","MY_STATE"]
    
    print("Removing bad fields...")
    log.remove_except(allowed_fields)
    print("   [DONE]")
    
    print("Setting blanket fields...")
    log.set_all("MY_SIG", "POTA") # identifies activator
    log.set_all("STATION_CALLSIGN", "WQ9N") # identifies activator
    print("   [DONE]")
    
    contacts = []
    print(f'Total contacts in log.records: {len(log.records)}')
    for r in log.records:
        comment = r.get("comment")
        if r.type == "header":
            continue
        if comment == None:
            print(f'Found log without comment: {r}, TERMINATING!!! Fix and attempt again.')
            sys.exit(1)
            
        results = re.search("POTA.*([a-zA-Z]\-\d{4})", comment)
        if results == None:
            print("ERROR: Couldn't find a park in record!!!")
            print(r)
            continue
        park = results.group(1)
        date = date = r.get("qso_date")
        if park == None or date == None:
            print("ERROR: Couldn't find park id or date in a record!!!")
            print(r)
            continue
            
        if (date,park) in parks: # Don't add if the park is on the list
            print(f'Park already on list')
        else:
            print(f'Found novel park {park} on date {date} in comment:{comment}')
            parks.append((date, park))
            
        # Dedup logic
        remove = False
        call = r.get("call")
        band = r.get("band")
        log_date = date
        
        sig = "%s-%s-%s"%(date,call,band)
        print(f'Computed new sig "{sig}"')
        if r.type != "header" and (comment == None or not "pota" in comment.lower()):
            if comment == None:
                print(f'Found log without comment: {r}, TERMINATING!!! Fix and attempt again.')
                sys.exit(1)
            if log_date == None or call == None or band == None:
                print(f'Found log without POTA in comment: {r}, skipping...')
            else:
                print(f'Found log without POTA in comment: {log_date}, {call}, {band}, skipping...')
            r.set("remove", "true")
            
        if sig in contacts:
            print(f'Found DUPLICATE in log for contact {log_date}, {call}, {band}, skipping...')
            r.set("remove", "true")
        else:
            print(f'Did not find duplicate in log for contact {log_date}, {call}, {band}')
            contacts.append(sig)
            print(f'Adding sig "{sig}" into dictionary')

    print(f'End of parsing...')
        
    for log_date, park in parks:
        out_path = f'{out_path_prefix}POTA-{log_date}-{park}.adi'
        file_out = open(out_path, "w")
        print(f'Writing out file for {park} "{log_date}" to {out_path}')
        
        park_log = ADIFFile()
        park_log.records = [r for r in log.records if r.type == "header" or (not r.get("remove") and r.get("qso_date") == log_date and re.search("([a-zA-Z]\-\d{4})", r.get("comment")).group(1) == park)]
        park_log.set_all("MY_SIG_INFO", park)
        
        print(f'Writing file to {out_path}...')
        #print("SKIPPING WRITE BECAUSE DEBUG!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        for r in park_log.records:
            print(f'      record:{r}')        
        park_log.write(file_out)
        file_out.close()
        print("   [DONE]")
