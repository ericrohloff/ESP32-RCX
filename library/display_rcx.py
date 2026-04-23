"""
display_rcx.py — RCX LCD display control.

Upload to ESP32 via Install RCX Lib. Requires rcx_driver.py to be installed first.

Usage:
    from display_rcx import show_sensor, show_timer

The RCX LCD shows one value at a time.
"""

from rcx_driver import rcx

SOURCE_VARIABLE   = 0
SOURCE_TIMER      = 1
SOURCE_SENSOR     = 9
SOURCE_SENSOR_RAW = 12
SOURCE_CLOCK      = 14
SOURCE_MESSAGE    = 15


def show(source, argument=0):
    """Display any RCX source value. source: SOURCE_* constant, argument: index."""
    rcx._send(0x33, [source, argument & 0xFF, (argument >> 8) & 0xFF])


def show_sensor(sensor_id):
    """Display a sensor reading. sensor_id: 0, 1, or 2."""
    show(SOURCE_SENSOR, sensor_id)


def show_timer(timer_id):
    """Display a timer value. timer_id: 0-3."""
    show(SOURCE_TIMER, timer_id)


def show_variable(var_id):
    """Display a variable value. var_id: 0-31."""
    show(SOURCE_VARIABLE, var_id)


def show_clock():
    """Display minutes since the RCX was powered on."""
    show(SOURCE_CLOCK)


def show_message():
    """Display the current IR message buffer value."""
    show(SOURCE_MESSAGE)
