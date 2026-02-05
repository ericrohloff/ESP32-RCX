# esp32_driver.py - This is the hidden code sent to the ESP32
import machine
import time

# 1. Setup 38kHz Carrier (Required for RCX to see IR)
ir_pwm = machine.PWM(machine.Pin(17))  # Adjust pin to your TX pin
ir_pwm.freq(38000)
ir_pwm.duty_u16(32768)  # 50% duty cycle

# 2. Setup UART for 2400 Baud Data
uart = machine.UART(1, baudrate=2400, tx=17)


class StandaloneRCX:
    def __init__(self):
        self.toggle = False

    def _send(self, opcode, params=[]):
        tx_opcode = opcode | 0x08 if self.toggle else opcode
        self.toggle = not self.toggle

        # Build Packet
        packet = bytearray([0x55, 0xFF, 0x00, tx_opcode, tx_opcode ^ 0xFF])
        checksum = tx_opcode
        for p in params:
            packet.extend(bytearray([p, p ^ 0xFF]))
            checksum = (checksum + p) % 256
        packet.extend(bytearray([checksum, checksum ^ 0xFF]))

        uart.write(packet)
        time.sleep(0.1)

    def beep(self): self._send(0x51, [0x01])
    def motor_on(self, m): self._send(0x21, [0x80 | (1 << m)])
    def motor_off(self, m): self._send(0x21, [0x40 | (1 << m)])


rcx = StandaloneRCX()
