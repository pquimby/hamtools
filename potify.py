from adif import ADIFFile
import sys

if __name__ == "__main__":
    
    in_path = sys.argv[1]
    out_path = sys.argv[2]
    PARK = sys.argv[3]
    
    file_in = open(in_path, "r")
    file_out = open(out_path, "w")
    
    log = ADIFFile()
    log.parse(file_in, verbose=False)
    file_in.close()
    
    allowed_fields = ["COMMENT", "STATION_CALLSIGN", "CALL", "QSO_DATE", "TIME_ON","BAND","MODE","SUBMODE","OPERATOR","MY_SIG","MY_SIG_INFO","SIG","SIG_INFO","MY_STATE"]
    
    print("Removing bad fields...")
    log.remove_except(allowed_fields)
    print("   [DONE]")
    
    print("Setting blanket fields...")
    log.set_all("SIG", "POTA")
    log.set_all("SIG_INFO", PARK)
    log.set_all("STATION_CALLSIGN", "WQ9N")
    print("   [DONE]")
    
    contacts = []
    for r in log.records:
        remove = False
        #if current_date == None and r.get("qso_date") != None:
        #    current_date = r.get("qso_date")
        #    print(f'Found first date: {current_date}')
        #date = r.get("qso_date")
        #if date != current_date and current_date != None:
        #    print(f'Found additional date: {date}! Was previously {current_date}')
        #    contacts = []
        #    current_date = date
        date = r.get("qso_date")
        call = r.get("call")
        band = r.get("band")
        comment = r.get("comment")
            
        sig = (date,call,band)
        if r.type != "header" and (comment == None or not "pota" in comment.lower()):
            if date == None or call == None or band == None:
                print(f'Found log without POTA in comment: {r}, skipping...')
            else:
                print(f'Found log without POTA in comment: {date}, {call}, {band}, skipping...')
            #continue
            r.set("remove", "true")
            
        if sig in contacts:
            print(f'Found duplicate in log for contact {date}, {call}, {band}, skipping...')
            #continue
            #remove = True
            r.set("remove", "true")

        contacts.append(sig)
    
    log.records = [r for r in log.records if not r.get("remove") or r.type == "header"]
    
    print(f'Writing file to {out_path}...')
    log.write(file_out)
    print("   [DONE]")
