import esp32
from machine import Pin
import time

# Define your target pin
IR_TX_PIN = 2

# Configure the ESP32 RMT (Remote Control) peripheral
# clock_div=80 means 1 tick = 1 microsecond.
# tx_carrier=(38000, 33, 1) creates the required 38kHz carrier wave at 33% duty cycle.
rmt = esp32.RMT(0, pin=Pin(IR_TX_PIN), clock_div=80, tx_carrier=(38000, 33, 1))


def send_ir_bytes(byte_data):
    pulses = []

    # 1. NEC Protocol Header (9000us mark, 4500us space)
    pulses.append(9000)
    pulses.append(4500)

    # 2. Encode each byte into pulses
    for b in byte_data:
        # Standard NEC sends the Least Significant Bit (LSB) first
        for i in range(8):
            bit = (b >> i) & 1
            pulses.append(560)  # Constant Mark for both 0 and 1

            if bit == 1:
                pulses.append(1690)  # Long space for a '1'
            else:
                pulses.append(560)  # Short space for a '0'

    # 3. End Mark to signal the end of the transmission
    pulses.append(560)

    # Send the pulses! '1' means start the first pulse HIGH (Mark)
    rmt.write_pulses(pulses, 1)
    print(f"Sent {len(byte_data)} bytes via IR!")


# Your specific byte sequence
payload = bytes([0x55, 0xFF, 0x00, 0x51, 0xAE, 0x05, 0xFA, 0x56, 0xA9])

print("Starting IR transmission test...")

try:
    while True:
        send_ir_bytes(payload)
        # Wait 2 seconds before firing again so you can test it
        time.sleep(2)

except KeyboardInterrupt:
    # Free up the RMT channel on exit
    rmt.deinit()
    print("\nTransmission stopped.")
