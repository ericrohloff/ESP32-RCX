"""
motors_rcx.py — Individual motor control.

Upload to ESP32 via Install RCX Lib. Requires rcx_driver.py to be installed first.

Usage:
    from motors_rcx import on, off, power, MOTOR_A, FORWARD
"""

from rcx_driver import rcx

MOTOR_A = 0
MOTOR_B = 1
MOTOR_C = 2

FORWARD = 0
REVERSE = 1


def on(motor_id, direction=FORWARD):
    """Turn on a single motor. direction: FORWARD or REVERSE."""
    rcx.motor_on(motor_id, direction)


def off(motor_id):
    """Coast a single motor to a stop."""
    rcx.motor_off(motor_id)


def brake(motor_id):
    """Hard-brake a single motor."""
    rcx.motor_brake(motor_id)


def power(motor_id, level):
    """Set power level 0-7 for a motor before calling on()."""
    rcx.set_power(motor_id, level)


def all_off():
    """Coast all three motors."""
    rcx.motor_off(MOTOR_A)
    rcx.motor_off(MOTOR_B)
    rcx.motor_off(MOTOR_C)


def all_brake():
    """Hard-brake all three motors."""
    rcx.motor_brake(MOTOR_A)
    rcx.motor_brake(MOTOR_B)
    rcx.motor_brake(MOTOR_C)
