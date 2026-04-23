"""
sensors_rcx.py — Sensor configuration.

Upload to ESP32 via Install RCX Lib. Requires rcx_driver.py to be installed first.

Usage:
    from sensors_rcx import configure, SENSOR_1, TYPE_LIGHT, MODE_PERCENT

Call configure() once at the start of your script before reading a sensor.
"""

from rcx_driver import rcx

# Sensor port IDs
SENSOR_1 = 0
SENSOR_2 = 1
SENSOR_3 = 2

# Sensor types
TYPE_NONE        = 0
TYPE_SWITCH      = 1
TYPE_TEMPERATURE = 2
TYPE_LIGHT       = 3
TYPE_ROTATION    = 4

# Sensor modes (upper 3 bits = slope, lower 5 bits = mode)
MODE_RAW         = 0x00  # raw A/D value 0-1023
MODE_BOOLEAN     = 0x20  # 0 or 1
MODE_EDGE        = 0x40  # count transitions
MODE_PULSE       = 0x60  # count half-transitions
MODE_PERCENT     = 0x80  # 0-100 scaled
MODE_CELSIUS     = 0xA0  # degrees C (temperature sensor)
MODE_FAHRENHEIT  = 0xC0  # degrees F (temperature sensor)
MODE_ROTATION    = 0xE0  # rotation ticks


def set_type(sensor, type_id):
    """Set the hardware type for a sensor port."""
    rcx._send(0x32, [sensor, type_id])


def set_mode(sensor, mode):
    """Set the reading mode for a sensor port."""
    rcx._send(0x42, [sensor, mode])


def configure(sensor, type_id, mode):
    """Set both type and mode for a sensor in one call."""
    set_type(sensor, type_id)
    set_mode(sensor, mode)


def clear(sensor):
    """Reset the sensor counter/accumulator to zero."""
    rcx._send(0x26, [sensor])
