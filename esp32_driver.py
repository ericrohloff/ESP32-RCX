"""
esp32_driver.py

This module is a container for the MicroPython code that runs on the ESP32.
The string `code` is uploaded to the ESP32 as `rcx_driver.py` via the
"Install RCX Lib" button in the web IDE.

After installing, users import it in their ESP32 scripts:

    from rcx_driver import RCX
    rcx = RCX()

    rcx.beep()
    rcx.move(speed=7, duration=2.0)
    rcx.turn_left(duration=0.5)
    rcx.stop()
"""

code = '''
import time

try:
    import machine
    MICROPYTHON = True
except ImportError:
    MICROPYTHON = False


class RCX:
    """
    LEGO RCX 2.0 controller via IR (ESP32 MicroPython, direct command mode).

    Each method sends its IR packet immediately and waits for the RCX
    acknowledgment before returning.  This makes it safe to sequence
    commands with time.sleep() between them:

        rcx = RCX()
        rcx.move(speed=7, duration=2.0)   # forward 2 s, then auto-stop
        rcx.turn_left(duration=0.5)
        rcx.beep()

    Pin defaults (change to match your board):
        tx_pin  = 17   UART TX  -> IR LED driver
        rx_pin  = 16   UART RX  <- IR receiver output
        ir_pin  = 2    38 kHz PWM carrier for the IR LED
    """

    # Sound IDs for beep()
    SOUND_BLIP  = 1
    SOUND_BEEP  = 2
    SOUND_SWEEP = 3
    SOUND_PLING = 4
    SOUND_BUZZ  = 5

    # Motor IDs
    MOTOR_A = 0
    MOTOR_B = 1
    MOTOR_C = 2

    def __init__(self, tx_pin=17, rx_pin=16, ir_pin=2):
        self._toggle = False
        self._preamble = bytes([0x55, 0xFF, 0x00])
        self.uart = None
        self.ir_pwm = None

        if MICROPYTHON:
            try:
                # 38 kHz carrier wave for the IR LED
                self.ir_pwm = machine.PWM(machine.Pin(ir_pin))
                self.ir_pwm.freq(38000)
                self.ir_pwm.duty_u16(32768)  # 50 % duty cycle

                # RCX protocol: 2400 baud, 8-N-1 with ODD parity
                self.uart = machine.UART(
                    1, baudrate=2400, bits=8, parity=1, stop=1,
                    tx=tx_pin, rx=rx_pin)
            except Exception as e:
                print("RCX init warning:", e)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build(self, opcode, params=None):
        """Build one RCX direct-command packet."""
        if params is None:
            params = []
        tx_op = opcode | (0x08 if self._toggle else 0x00)
        self._toggle = not self._toggle
        pkt = bytearray([0x55, 0xFF, 0x00, tx_op, tx_op ^ 0xFF])
        ck = tx_op
        for p in params:
            pkt.extend([p, p ^ 0xFF])
            ck = (ck + p) & 0xFF
        pkt.extend([ck, ck ^ 0xFF])
        return bytes(pkt)

    def _send(self, opcode, params=None, timeout_ms=500, ignore_reply=False):
        """
        Build a packet, transmit it over IR-UART, and wait for the
        RCX acknowledgment.

        Returns:
            (success: bool, payload: bytes)
        """
        if not self.uart:
            print("RCX: UART not available")
            return False, b""

        pkt = self._build(opcode, params)

        # Transmit the whole packet at once; UART hardware handles 2400-baud timing
        try:
            self.uart.write(pkt)
            if MICROPYTHON:
                # Allow enough time for all bytes to clock out at 2400 baud
                # (~4 ms/byte * 9 bytes = ~36 ms) plus inter-packet gap
                time.sleep_ms(100)
            else:
                time.sleep(0.1)
        except Exception as e:
            print("RCX TX error:", e)
            return False, b""

        if ignore_reply:
            return True, b""

        # Collect response bytes until timeout
        buf = bytearray()
        if MICROPYTHON:
            t0 = time.ticks_ms()
        else:
            t0 = time.time() * 1000

        while True:
            if MICROPYTHON:
                elapsed = time.ticks_diff(time.ticks_ms(), t0)
            else:
                elapsed = time.time() * 1000 - t0
            if elapsed > timeout_ms:
                break
            if self.uart.any():
                b = self.uart.read(1)
                if b:
                    buf.extend(b)
                    # Reset deadline after each byte
                    if MICROPYTHON:
                        t0 = time.ticks_ms()
                    else:
                        t0 = time.time() * 1000
            else:
                if MICROPYTHON:
                    time.sleep_ms(1)
                else:
                    time.sleep(0.001)

        if not buf:
            print("RCX: no response")
            return False, b""

        return self._parse(bytes(buf), pkt)

    def _parse(self, response, tx_pkt):
        """
        Strip the TX echo and extract the RCX reply payload.

        Response structure:
            [echo of tx_pkt] [0x55 0xFF 0x00] [opcode] [opcode^] [...payload pairs...] [ck] [ck^]
        """
        # Strip echo (exact match or off-by-one "glitchy" echo)
        n = len(tx_pkt)
        if response[:n] == tx_pkt:
            rest = response[n:]
        elif len(response) > n + 1 and response[1:n + 1] == tx_pkt:
            rest = response[n + 1:]
        else:
            rest = response

        pre = self._preamble
        for i in range(len(rest) - len(pre) + 1):
            if rest[i:i + len(pre)] == pre:
                reply = rest[i + len(pre):]
                # Need at least: opcode(1) + comp(1) + ck(1) + comp(1)
                if len(reply) < 4:
                    return False, b""
                op, op_c = reply[0], reply[1]
                if op ^ op_c != 0xFF:
                    return False, b""
                # Extract payload pairs
                payload = bytearray()
                pos = 2
                while pos < len(reply) - 2:
                    d, c = reply[pos], reply[pos + 1]
                    if d ^ c != 0xFF:
                        return False, b""
                    payload.append(d)
                    pos += 2
                return True, bytes(payload)

        return False, b""

    # ------------------------------------------------------------------
    # Direct commands
    # ------------------------------------------------------------------

    def ping(self):
        """Check whether the RCX is alive. Returns (ok, b"")."""
        return self._send(0x10)

    def beep(self, sound=2):
        """
        Play a sound on the RCX.
        sound: 1=blip  2=beep  3=sweep  4=pling  5=buzz
        """
        return self._send(0x51, [sound])

    def motor_on(self, motor_id, direction=0):
        """
        Turn on a single motor.
        motor_id : 0=A  1=B  2=C
        direction: 0=forward  1=reverse
        """
        if not 0 <= motor_id <= 2:
            return False, b""
        port = 1 << motor_id
        flag = 0x80 if direction == 0 else 0x40
        return self._send(0x21, [flag | port])

    def motor_off(self, motor_id):
        """Float (coast) a single motor. motor_id: 0=A  1=B  2=C"""
        if 0 <= motor_id <= 2:
            port = 1 << motor_id
            return self._send(0x21, [0x40 | port])
        return False, b""

    def motor_brake(self, motor_id):
        """Hard-brake a single motor. motor_id: 0=A  1=B  2=C"""
        if 0 <= motor_id <= 2:
            port = 1 << motor_id
            return self._send(0x21, [0xC0 | port])
        return False, b""

    def set_power(self, motor_id, power):
        """
        Set motor power level before calling motor_on().
        motor_id: 0=A  1=B  2=C
        power   : 0-7
        """
        if 0 <= motor_id <= 2 and 0 <= power <= 7:
            return self._send(0x13, [motor_id, power])
        return False, b""

    # ------------------------------------------------------------------
    # High-level robot commands
    # ------------------------------------------------------------------

    def move(self, speed=7, duration=None):
        """
        Drive forward on motors A and B.
        speed   : 0-7 (default 7 = full power)
        duration: seconds to run; None = run until stop() is called
        """
        self.set_power(0, speed)
        self.set_power(1, speed)
        self.motor_on(0, direction=0)
        self.motor_on(1, direction=0)
        if duration is not None:
            self.wait(duration)
            self.stop()

    def backward(self, speed=7, duration=None):
        """
        Drive backward on motors A and B.
        speed   : 0-7
        duration: seconds; None = until stop()
        """
        self.set_power(0, speed)
        self.set_power(1, speed)
        self.motor_on(0, direction=1)
        self.motor_on(1, direction=1)
        if duration is not None:
            self.wait(duration)
            self.stop()

    def turn_left(self, speed=7, duration=None):
        """
        Pivot left: motor A forward, motor B reverse.
        speed   : 0-7
        duration: seconds; None = until stop()
        """
        self.set_power(0, speed)
        self.set_power(1, speed)
        self.motor_on(0, direction=0)
        self.motor_on(1, direction=1)
        if duration is not None:
            self.wait(duration)
            self.stop()

    def turn_right(self, speed=7, duration=None):
        """
        Pivot right: motor A reverse, motor B forward.
        speed   : 0-7
        duration: seconds; None = until stop()
        """
        self.set_power(0, speed)
        self.set_power(1, speed)
        self.motor_on(0, direction=1)
        self.motor_on(1, direction=0)
        if duration is not None:
            self.wait(duration)
            self.stop()

    def stop(self):
        """Coast all three motors to a stop."""
        self.motor_off(0)
        self.motor_off(1)
        self.motor_off(2)

    def brake(self):
        """Hard-brake all three motors."""
        self.motor_brake(0)
        self.motor_brake(1)
        self.motor_brake(2)

    def wait(self, seconds):
        """Pause execution for the given number of seconds."""
        time.sleep(seconds)


# Ready-to-use instance
rcx = RCX()
'''
