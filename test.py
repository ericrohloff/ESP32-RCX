# test.py - ESP32 RCX Driver Test

from rcx_lib import RCX

rcx = RCX()
rcx.beep()
success, payload = rcx.transceive(timeout=0.34)

if success:
    print("Beep sent successfully!")
else:
    print("Beep failed")
