code = '''
import machine
import time

# 1. Physical Layer: 38kHz Carrier
ir_pwm = machine.PWM(machine.Pin(17))
ir_pwm.freq(38000)
ir_pwm.duty_u16(32768)

# 2. UART: 2400 Baud, Odd Parity (Mandatory for RCX)
uart = machine.UART(1, baudrate=2400, bits=8, parity=1, stop=1, tx=17)

class StandaloneRCX:
    def __init__(self):
        self.toggle = False
        # The specific bytecode sequence from your LASM breakdown
        self.BEEP_SCRIPT = [
            0x43, 0x02, 0x05, 0x00,             # wait 2, 5
            0x05, 0x01, 0x03, 0x02, 0x00, 0x00, # tmrz 3
            0x05, 0x18, 0x09, 0x02, 0x01, 0x00, # set 24, 9, 2, 1
            0x51, 0x05,                         # plays 5
            0x43, 0x02, 0x64, 0x00,             # wait 2, 100
            0x43, 0x02, 0x14, 0x00              # wait 2, 20
        ]

    def _send(self, opcode, params=None):
        """Standard Lego PQC Packet Construction."""
        if params is None: params = []
        
        # Toggle bit 3 to prevent the RCX from ignoring repeat commands
        tx_opcode = opcode | 0x08 if self.toggle else opcode
        self.toggle = not self.toggle

        # [Header] [Opcode + Inv] [Params + Inv] [Checksum + Inv]
        packet = bytearray([0x55, 0xFF, 0x00])
        packet.append(tx_opcode)
        packet.append(tx_opcode ^ 0xFF)
        
        checksum = tx_opcode
        for p in params:
            p &= 0xFF
            packet.append(p)
            packet.append(p ^ 0xFF)
            checksum = (checksum + p) % 256
            
        packet.append(checksum)
        packet.append(checksum ^ 0xFF)

        uart.write(packet)
        time.sleep(0.07) # Required delay for RCX processing

    def beep(self):
        """
        Downloads the full LASM breakdown script to Task 0
        and executes it immediately.
        """
        print("Clearing Task 0...")
        self._send(0x40, [0x00]) # Delete Task 0
        
        print("Downloading LASM Sequence...")
        # Opcode 0x25: Download Task Header
        # Params: Task (0), Source (0), Length Low, Length High, 0, 0
        length = len(self.BEEP_SCRIPT)
        self._send(0x25, [0x00, 0x00, length & 0xFF, (length >> 8) & 0xFF, 0x00, 0x00])
        
        # Opcode 0x45: Transfer Data Body
        self._send(0x45, self.BEEP_SCRIPT)
        
        print("Starting Task...")
        # Opcode 0x21: Start Task (0x00 is Task 0)
        self._send(0x21, [0x00])

    def stop(self):
        """Immediate stop command."""
        self._send(0x50)
'''
