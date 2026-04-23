from machine import UART, Pin
import time

# Initialize UART 1
# rx=1 sets GPIO 1 as the receiver pin. tx=3 is standard, but we aren't transmitting.
uart = UART(1, baudrate=2400, tx=3, rx=1)

print("Listening for serial bytes at 2400 baud on GPIO 1...")

try:
    while True:
        if uart.any():
            # Read whatever bytes are waiting in the buffer
            raw_bytes = uart.read()

            # Print the literal byte string (e.g., b'\x00\xff')
            print(f"Raw Bytes: {raw_bytes}")

            # Print as a formatted Hex string which is usually easier to read
            # e.g., "00 ff a2"
            hex_string = " ".join([f"{b:02x}" for b in raw_bytes])
            print(f"Hex View:  {hex_string}\n")

        time.sleep_ms(50)

except KeyboardInterrupt:
    print("\nSerial test ended.")
