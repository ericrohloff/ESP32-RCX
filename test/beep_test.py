import esp32
from machine import Pin
import time

# --- Configuration ---
IR_TX_PIN = 2
BAUD_RATE = 2400
# At 2400 baud, 1 bit takes ~417 microseconds
BIT_US = round(1000000 / BAUD_RATE)

# Configure the ESP32 RMT peripheral
# tx_carrier=(38000, 33, 1) creates the 38kHz carrier wave at 33% duty cycle.
rmt = esp32.RMT(0, pin=Pin(IR_TX_PIN), clock_div=80, tx_carrier=(38000, 33, 1))


def send_custom_ir_frame(byte_data):
    """
    Simulates a custom 12-bit UART serial transmission using the RMT.
    Flashes the IR LED at 38kHz to represent logic LOWs (Light ON).
    """
    pulses = []

    # Track the current state. 'True' means the 38kHz light is ON.
    # We initialize it to True because the first bit is always a Start Bit (ON).
    current_state_is_on = True
    current_duration = 0

    def add_bit(is_light_on):
        nonlocal current_state_is_on, current_duration
        if is_light_on == current_state_is_on:
            # If the state hasn't changed, extend the duration of the current pulse
            current_duration += BIT_US
        else:
            # If the state changed, record the duration, reset, and flip the state
            pulses.append(current_duration)
            current_duration = BIT_US
            current_state_is_on = is_light_on

    # --- Build the 12-Bit Frame for each byte ---
    for b in byte_data:
        # Bit 1: START BIT (Always light ON / logic LOW)
        add_bit(True)

        # Bits 2-9: DATA BITS (LSB first)
        ones_count = 0
        for i in range(8):
            bit = (b >> i) & 1
            if bit == 1:
                ones_count += 1

            # 0 -> Light ON (True), 1 -> Light OFF (False)
            add_bit(bit == 0)

        # Bit 10: PARITY BIT (Odd Parity)
        # For odd parity, the total number of '1's in the data + parity bit must be an odd number.
        if ones_count % 2 == 0:
            # Data has an even number of 1s, so Parity bit must be '1' (Light OFF)
            add_bit(False)
        else:
            # Data has an odd number of 1s, so Parity bit must be '0' (Light ON)
            add_bit(True)

        # Bit 11: STOP BIT (Always light OFF / logic HIGH)
        add_bit(False)

        # Bit 12: INTER-BYTE GAP (Always light OFF / idle)
        add_bit(False)

    # Append the very last duration to the list once the loop finishes
    if current_duration > 0:
        pulses.append(current_duration)

    # Send the pulses! '1' means start the first pulse HIGH (Light ON)
    rmt.write_pulses(pulses, 1)
    print(f"Sent {len(byte_data)} bytes using 12-bit framing!")


# Your specific byte sequence
payload = bytes([0x55, 0xFF, 0x00, 0x51, 0xAE, 0x05, 0xFA, 0x56, 0xA9])

print(f"Starting 12-bit custom IR transmission test...")

try:
    while True:
        send_custom_ir_frame(payload)
        # Wait 2 seconds before firing again
        time.sleep(2)

except KeyboardInterrupt:
    # Free up the RMT channel on exit
    rmt.deinit()
    print("\nTransmission stopped.")
