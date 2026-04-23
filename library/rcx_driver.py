"""
rcx_driver.py — Core RCX driver for ESP32 MicroPython.

This is the readable source. The identical code lives as the `code` string
inside pyscript/esp32_driver.py and is what actually gets uploaded to the ESP32
via the "Install RCX Lib" button.

Usage on ESP32:
    from rcx_driver import rcx
    rcx.beep()
    rcx.move(speed=7, duration=2.0)
    rcx.turn_left(duration=0.5)
    rcx.stop()
"""

import time

try:
    import machine
    import esp32
    from machine import Pin
    MICROPYTHON = True
except ImportError:
    MICROPYTHON = False


class RCX:
    """
    LEGO RCX 2.0 controller via IR (ESP32 MicroPython, direct command mode).

    Sends IR packets using the ESP32 RMT peripheral with proper 12-bit UART
    framing at 2400 baud over a 38 kHz carrier. Fire-and-forget — no response
    reading. Commands are transmitted immediately and the RCX executes them
    as they arrive.

    Pin default:
        ir_pin = 2   RMT output -> IR LED driver transistor
    """

    SOUND_BLIP  = 1
    SOUND_BEEP  = 2
    SOUND_SWEEP = 3
    SOUND_PLING = 4
    SOUND_BUZZ  = 5

    MOTOR_A = 0
    MOTOR_B = 1
    MOTOR_C = 2

    def __init__(self, ir_pin=2):
        self._toggle = False
        self.rmt = None

        if MICROPYTHON:
            try:
                self.rmt = esp32.RMT(0, pin=Pin(ir_pin), clock_div=80,
                                     tx_carrier=(38000, 33, 1))
            except Exception as e:
                print("RCX init warning:", e)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_ir_bytes(self, byte_data):
        """
        Encode bytes as 12-bit raw UART frames over IR and transmit via RMT.

        Each byte is framed as:
          START (light ON) | 8 data bits LSB-first | odd parity | STOP | GAP

        Consecutive bits in the same state are merged into one longer RMT pulse.
        Parity: if even number of 1-bits -> parity=1 (light OFF); odd -> parity=0 (ON).
        """
        BIT_US = round(1000000 / 2400)  # ~417 us per bit at 2400 baud

        pulses = []
        current_on = True  # first bit is always START (light ON)
        current_dur = 0

        def add_bit(is_on):
            nonlocal current_on, current_dur
            if is_on == current_on:
                current_dur += BIT_US
            else:
                pulses.append(current_dur)
                current_dur = BIT_US
                current_on = is_on

        for b in byte_data:
            add_bit(True)  # START bit: light ON
            ones = 0
            for i in range(8):
                bit = (b >> i) & 1
                if bit:
                    ones += 1
                add_bit(bit == 0)  # 0 -> light ON, 1 -> light OFF
            add_bit(ones % 2 != 0)  # odd parity
            add_bit(False)  # STOP bit
            add_bit(False)  # inter-byte gap

        if current_dur > 0:
            pulses.append(current_dur)

        self.rmt.write_pulses(pulses, 1)

    def _build(self, opcode, params=None):
        """
        Build one RCX direct-command packet.

        Format: [55 FF 00] [op] [op^FF] [p1] [p1^FF] ... [ck] [ck^FF]
        Toggle bit (0x08) alternates each packet so the RCX detects retransmissions.
        """
        if params is None:
            params = []
        tx_op = opcode | (0x08 if self._toggle else 0x00)
        self._toggle = not self._toggle
        pkt = bytearray([0x55, 0xFF, 0x00, tx_op, tx_op ^ 0xFF])
        ck = tx_op
        for p in params:
            pkt.append(p)
            pkt.append(p ^ 0xFF)
            ck = (ck + p) & 0xFF
        pkt.append(ck)
        pkt.append(ck ^ 0xFF)
        return bytes(pkt)

    def _send(self, opcode, params=None):
        """Build a packet and transmit it. 100 ms gap after each send."""
        if not self.rmt:
            print("RCX: not available")
            return
        pkt = self._build(opcode, params)
        self._send_ir_bytes(pkt)
        time.sleep_ms(100)

    # ------------------------------------------------------------------
    # Direct commands
    # ------------------------------------------------------------------

    def ping(self):
        self._send(0x10)

    def beep(self, sound=2):
        self._send(0x51, [sound])

    def motor_on(self, motor_id, direction=0):
        if 0 <= motor_id <= 2:
            port = 1 << motor_id
            flag = 0x80 if direction == 0 else 0x40
            self._send(0x21, [flag | port])

    def motor_off(self, motor_id):
        if 0 <= motor_id <= 2:
            port = 1 << motor_id
            self._send(0x21, [0x40 | port])

    def motor_brake(self, motor_id):
        if 0 <= motor_id <= 2:
            port = 1 << motor_id
            self._send(0x21, [0xC0 | port])

    def set_power(self, motor_id, power):
        if 0 <= motor_id <= 2 and 0 <= power <= 7:
            self._send(0x13, [motor_id, power])

    # ------------------------------------------------------------------
    # High-level robot commands
    # ------------------------------------------------------------------

    def move(self, speed=7, duration=None):
        self.set_power(0, speed)
        self.set_power(1, speed)
        self.motor_on(0, direction=0)
        self.motor_on(1, direction=0)
        if duration is not None:
            self.wait(duration)
            self.stop()

    def backward(self, speed=7, duration=None):
        self.set_power(0, speed)
        self.set_power(1, speed)
        self.motor_on(0, direction=1)
        self.motor_on(1, direction=1)
        if duration is not None:
            self.wait(duration)
            self.stop()

    def turn_left(self, speed=7, duration=None):
        self.set_power(0, speed)
        self.set_power(1, speed)
        self.motor_on(0, direction=0)
        self.motor_on(1, direction=1)
        if duration is not None:
            self.wait(duration)
            self.stop()

    def turn_right(self, speed=7, duration=None):
        self.set_power(0, speed)
        self.set_power(1, speed)
        self.motor_on(0, direction=1)
        self.motor_on(1, direction=0)
        if duration is not None:
            self.wait(duration)
            self.stop()

    def spin_left(self, speed=7, duration=None):
        self.turn_left(speed=speed, duration=duration)

    def spin_right(self, speed=7, duration=None):
        self.turn_right(speed=speed, duration=duration)

    def stop(self):
        self.motor_off(0)
        self.motor_off(1)
        self.motor_off(2)

    def brake(self):
        self.motor_brake(0)
        self.motor_brake(1)
        self.motor_brake(2)

    def wait(self, seconds):
        time.sleep(seconds)

    def set_all_power(self, power):
        self.set_power(0, power)
        self.set_power(1, power)
        self.set_power(2, power)

    def reverse_turn_left(self, speed=7, duration=None):
        self.set_power(0, speed)
        self.set_power(1, speed)
        self.motor_on(0, direction=1)
        self.motor_on(1, direction=0)
        if duration is not None:
            self.wait(duration)
            self.stop()

    def reverse_turn_right(self, speed=7, duration=None):
        self.set_power(0, speed)
        self.set_power(1, speed)
        self.motor_on(0, direction=0)
        self.motor_on(1, direction=1)
        if duration is not None:
            self.wait(duration)
            self.stop()


# Ready-to-use instance
rcx = RCX()
