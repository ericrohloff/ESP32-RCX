import esp32
from machine import UART, Pin
import time

# --- Configuration ---
IR_TX_PIN = 2
UART_RX_PIN = 1
UART_TX_PIN = 3  # Standard TX pin, required for init but we aren't using it

# --- Initialize Hardware ---

# 1. Configure the RMT (IR Transmitter)
rmt = esp32.RMT(0, pin=Pin(IR_TX_PIN), clock_div=80, tx_carrier=(38000, 33, 1))

# 2. Configure the UART (IR Receiver Module)
uart = UART(1, baudrate=2400, tx=UART_TX_PIN, rx=UART_RX_PIN)


# --- Functions ---

def send_ir_bytes(byte_data):
    """Encodes bytes into NEC IR pulses and transmits them"""
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


# --- Main Loop ---

print("Starting IR Bridge...")
print(
    f"Listening on GPIO {UART_RX_PIN} (2400 Baud) -> Transmitting on GPIO {IR_TX_PIN} (IR 38kHz)")

try:
    while True:
        # Check if any bytes have arrived from the receiver
        if uart.any():
            # Read all available bytes from the buffer
            incoming_bytes = uart.read()

            # Print to console so you can monitor the traffic
            hex_string = " ".join([f"{b:02x}" for b in incoming_bytes])
            print(f"Received:  {hex_string}")

            # Immediately send those exact bytes out over the IR LED
            send_ir_bytes(incoming_bytes)
            print(f"Forwarded: {len(incoming_bytes)} bytes.\n")

        # Small delay to prevent the loop from maxing out the CPU
        time.sleep_ms(50)

except KeyboardInterrupt:
    # Cleanly release the RMT hardware on exit
    rmt.deinit()
    print("\nIR Bridge stopped.")
