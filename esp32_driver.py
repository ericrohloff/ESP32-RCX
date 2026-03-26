code = '''
import machine
import time

# 1. Physical Layer: 38kHz Carrier
# This creates the IR "envelope" that the RCX sensor expects.
ir_pwm = machine.PWM(machine.Pin(2))
ir_pwm.freq(38000)
ir_pwm.duty_u16(32768)  # 50% duty cycle

# 2. UART: 2400 Baud, 8 Bits, ODD Parity, 1 Stop Bit
# Dave Baum / LEGO PQC standard.
uart = machine.UART(1, baudrate=2400, bits=8, parity=1, stop=1, tx=17)

class StandaloneRCX:
    def __init__(self):
        self.toggle = False
        # Your LASM Breakdown: wait, tmrz, set vars, plays 5, wait, wait.
        self.BEEP_SCRIPT = [
            0x43, 0x02, 0x05, 0x00,             # wait 2, 5
            0x05, 0x01, 0x03, 0x02, 0x00, 0x00, # tmrz 3
            0x05, 0x18, 0x09, 0x02, 0x01, 0x00, # set 24, 9, 2, 1
            0x51, 0x05,                         # plays 5
            0x43, 0x02, 0x64, 0x00,             # wait 2, 100
            0x43, 0x02, 0x14, 0x00              # wait 2, 20
        ]

    def _send(self, opcode, params=None):
        """Constructs packet and sends bytes slowly to avoid overwhelming RCX."""
        if params is None: params = []
        
        # Apply the toggle bit (bit 3)
        tx_opcode = opcode | 0x08 if self.toggle else opcode
        self.toggle = not self.toggle

        # Build Packet: [0x55, 0xFF, 0x00, Op, ~Op, P1, ~P1... Sum, ~Sum]
        packet = [0x55, 0xFF, 0x00]
        packet.append(tx_opcode)
        packet.append(tx_opcode ^ 0xFF)
        
        checksum = tx_opcode
        for p in params:
            p_byte = p & 0xFF
            packet.append(p_byte)
            packet.append(p_byte ^ 0xFF)
            checksum = (checksum + p_byte) % 256
            
        packet.append(checksum)
        packet.append(checksum ^ 0xFF)

        # Send bytes with inter-byte delay
        for b in packet:
            uart.write(bytearray([b]))
            # 2400 baud is slow (~4ms/byte). 
            # We wait 7ms to ensure the RCX finishes processing the byte.
            time.sleep_ms(7) 
        
        # Inter-packet delay: Give the RCX time to "breathe" after a command
        time.sleep_ms(100)

    def beep(self):
        """
        Performs the full deployment sequence to the RCX 2.0 memory.
        """
        print("1/4: Stopping RCX and clearing Task 0...")
        self._send(0x50)        # Stop all
        time.sleep_ms(200)      # Wait for stop to process
        self._send(0x40, [0])   # Delete Task 0
        time.sleep_ms(400)      # Memory deletion is slow on RCX 2.0

        print("2/4: Sending Task Header...")
        # Opcode 0x25: Task Index 0, Length of script (Little Endian)
        length = len(self.BEEP_SCRIPT)
        length_low = length & 0xFF
        length_high = (length >> 8) & 0xFF
        # Params: Task, Unknown, LenL, LenH, 0, 0
        self._send(0x25, [0x00, 0x00, length_low, length_high, 0x00, 0x00])

        print("3/4: Uploading Bytecode...")
        # Opcode 0x45: Download Data
        self._send(0x45, self.BEEP_SCRIPT)

        print("4/4: Starting Task 0...")
        # Opcode 0x21: Set Task State. 
        # For RCX 2.0, 0x81 (Task 0 bit + Start bit) is the reliable trigger.
        self._send(0x21, [0x81])
        
        print("Deployment Complete! Listen for the beep.")

    def direct_beep(self):
        """Sends a single 'Play Sound' command without downloading a task."""
        self._send(0x51, [0x01])

# --- INITIALIZATION ---
rcx = StandaloneRCX()

# To use:
# rcx.beep()
'''
