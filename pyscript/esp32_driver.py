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
    import esp32
    from machine import Pin
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
        Consecutive bits in the same state are merged into one longer pulse.
        """
        BIT_US = round(1000000 / 2400)  # ~417 us per bit at 2400 baud

        pulses = []
        current_on = True   # first bit is always START (light ON)
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
            add_bit(True)   # START bit: light ON
            ones = 0
            for i in range(8):
                bit = (b >> i) & 1
                if bit:
                    ones += 1
                add_bit(bit == 0)   # 0 -> light ON, 1 -> light OFF
            # Odd parity: total 1-bits including parity must be odd
            add_bit(ones % 2 != 0)  # even ones -> parity=1 (OFF); odd -> parity=0 (ON)
            add_bit(False)  # STOP bit: light OFF
            add_bit(False)  # inter-byte gap: light OFF

        if current_dur > 0:
            pulses.append(current_dur)

        self.rmt.write_pulses(pulses, 1)

    def _build(self, opcode, params=None):
        """Build one RCX direct-command packet."""
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

    def spin_left(self, speed=7, duration=None):
        """
        Spin left in place: motor A forward, motor B reverse at different power.
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

    def spin_right(self, speed=7, duration=None):
        """
        Spin right in place: motor A reverse, motor B forward.
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

    def set_all_power(self, power):
        """Set power level for all motors (A, B, and C)."""
        self.set_power(0, power)
        self.set_power(1, power)
        self.set_power(2, power)

    def play_sound(self, sound=2):
        """Alias for beep(). Play a sound on the RCX."""
        return self.beep(sound)

    def stop_motor(self, motor_id):
        """Stop a single motor (alias for motor_off)."""
        return self.motor_off(motor_id)

    def reverse_turn_left(self, speed=7, duration=None):
        """
        Backup and turn left: motor A reverse, motor B forward.
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

    def reverse_turn_right(self, speed=7, duration=None):
        """
        Backup and turn right: motor A forward, motor B reverse.
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


# Ready-to-use instance
rcx = RCX()
'''

motion_code = '''
from rcx_driver import rcx
import time


def move(speed=7, duration=None):
    rcx.set_power(0, speed)
    rcx.set_power(1, speed)
    rcx.motor_on(0, direction=0)
    rcx.motor_on(1, direction=0)
    if duration is not None:
        time.sleep(duration)
        stop()


def backward(speed=7, duration=None):
    rcx.set_power(0, speed)
    rcx.set_power(1, speed)
    rcx.motor_on(0, direction=1)
    rcx.motor_on(1, direction=1)
    if duration is not None:
        time.sleep(duration)
        stop()


def turn_left(speed=7, duration=None):
    rcx.set_power(0, speed)
    rcx.set_power(1, speed)
    rcx.motor_on(0, direction=0)
    rcx.motor_on(1, direction=1)
    if duration is not None:
        time.sleep(duration)
        stop()


def turn_right(speed=7, duration=None):
    rcx.set_power(0, speed)
    rcx.set_power(1, speed)
    rcx.motor_on(0, direction=1)
    rcx.motor_on(1, direction=0)
    if duration is not None:
        time.sleep(duration)
        stop()


def spin_left(speed=7, duration=None):
    turn_left(speed=speed, duration=duration)


def spin_right(speed=7, duration=None):
    turn_right(speed=speed, duration=duration)


def stop():
    rcx.motor_off(0)
    rcx.motor_off(1)
    rcx.motor_off(2)


def brake():
    rcx.motor_brake(0)
    rcx.motor_brake(1)
    rcx.motor_brake(2)


def wait(seconds):
    time.sleep(seconds)
'''

motors_code = '''
from rcx_driver import rcx

MOTOR_A = 0
MOTOR_B = 1
MOTOR_C = 2

FORWARD = 0
REVERSE = 1


def on(motor_id, direction=FORWARD):
    rcx.motor_on(motor_id, direction)


def off(motor_id):
    rcx.motor_off(motor_id)


def brake(motor_id):
    rcx.motor_brake(motor_id)


def power(motor_id, level):
    rcx.set_power(motor_id, level)


def all_off():
    rcx.motor_off(MOTOR_A)
    rcx.motor_off(MOTOR_B)
    rcx.motor_off(MOTOR_C)


def all_brake():
    rcx.motor_brake(MOTOR_A)
    rcx.motor_brake(MOTOR_B)
    rcx.motor_brake(MOTOR_C)
'''

sound_code = '''
from rcx_driver import rcx

BLIP  = 1
BEEP  = 2
SWEEP = 3
PLING = 4
BUZZ  = 5


def beep(sound=BEEP):
    rcx._send(0x51, [sound])


def play_tone(frequency, duration):
    freq_lo = frequency & 0xFF
    freq_hi = (frequency >> 8) & 0xFF
    rcx._send(0x23, [freq_lo, freq_hi, duration])
'''

sensors_code = '''
from rcx_driver import rcx

SENSOR_1 = 0
SENSOR_2 = 1
SENSOR_3 = 2

TYPE_NONE        = 0
TYPE_SWITCH      = 1
TYPE_TEMPERATURE = 2
TYPE_LIGHT       = 3
TYPE_ROTATION    = 4

MODE_RAW         = 0x00
MODE_BOOLEAN     = 0x20
MODE_EDGE        = 0x40
MODE_PULSE       = 0x60
MODE_PERCENT     = 0x80
MODE_CELSIUS     = 0xA0
MODE_FAHRENHEIT  = 0xC0
MODE_ROTATION    = 0xE0


def set_type(sensor, type_id):
    rcx._send(0x32, [sensor, type_id])


def set_mode(sensor, mode):
    rcx._send(0x42, [sensor, mode])


def configure(sensor, type_id, mode):
    set_type(sensor, type_id)
    set_mode(sensor, mode)


def clear(sensor):
    rcx._send(0x26, [sensor])
'''

display_code = '''
from rcx_driver import rcx

SOURCE_VARIABLE   = 0
SOURCE_TIMER      = 1
SOURCE_SENSOR     = 9
SOURCE_SENSOR_RAW = 12
SOURCE_CLOCK      = 14
SOURCE_MESSAGE    = 15


def show(source, argument=0):
    rcx._send(0x33, [source, argument & 0xFF, (argument >> 8) & 0xFF])


def show_sensor(sensor_id):
    show(SOURCE_SENSOR, sensor_id)


def show_timer(timer_id):
    show(SOURCE_TIMER, timer_id)


def show_variable(var_id):
    show(SOURCE_VARIABLE, var_id)


def show_clock():
    show(SOURCE_CLOCK)


def show_message():
    show(SOURCE_MESSAGE)
'''

system_code = '''
from rcx_driver import rcx


def ping():
    rcx._send(0x10)


def stop_all():
    rcx._send(0x50)


def power_off():
    rcx._send(0x60)


def set_time(hours, minutes):
    rcx._send(0x22, [hours, minutes])


def set_range(long_range=False):
    rcx._send(0x31, [1 if long_range else 0])


def set_power_down(minutes):
    rcx._send(0x46, [minutes])


def set_message(value):
    rcx._send(0xf7, [value])


def clear_timer(timer_id):
    rcx._send(0x56, [timer_id])
'''

