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
        call = r.get("CALL")
        if call in contacts:
            print('Found duplicate in log for contact {call}')
        else:
            contacts.append(call)
    
    print(f'Writing file to {out_path}...')
    log.write(file_out)
    print("   [DONE]")