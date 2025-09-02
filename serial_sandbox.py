from ap_utils import Utilities, SwitchBox, HoneywellScanner
import time

scanner = HoneywellScanner()


while True:
    print("🔄 Checking scanner status...")
    if scanner.connected:
        print("✅ Scanner is connected.")       
    else:
        print("❌ Scanner is disconnected.")    

    time.sleep(1) 