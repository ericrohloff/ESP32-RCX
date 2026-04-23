"""
motion_rcx.py — High-level two-motor movement commands.

Upload to ESP32 via Install RCX Lib. Requires rcx_driver.py to be installed first.

Usage:
    from motion_rcx import move, stop, turn_left
"""

from rcx_driver import rcx
import time


def move(speed=7, duration=None):
    """Drive forward on motors A and B. duration in seconds, or None to run until stop()."""
    rcx.set_power(0, speed)
    rcx.set_power(1, speed)
    rcx.motor_on(0, direction=0)
    rcx.motor_on(1, direction=0)
    if duration is not None:
        time.sleep(duration)
        stop()


def backward(speed=7, duration=None):
    """Drive in reverse on motors A and B."""
    rcx.set_power(0, speed)
    rcx.set_power(1, speed)
    rcx.motor_on(0, direction=1)
    rcx.motor_on(1, direction=1)
    if duration is not None:
        time.sleep(duration)
        stop()


def turn_left(speed=7, duration=None):
    """Pivot left: motor A forward, motor B reverse."""
    rcx.set_power(0, speed)
    rcx.set_power(1, speed)
    rcx.motor_on(0, direction=0)
    rcx.motor_on(1, direction=1)
    if duration is not None:
        time.sleep(duration)
        stop()


def turn_right(speed=7, duration=None):
    """Pivot right: motor A reverse, motor B forward."""
    rcx.set_power(0, speed)
    rcx.set_power(1, speed)
    rcx.motor_on(0, direction=1)
    rcx.motor_on(1, direction=0)
    if duration is not None:
        time.sleep(duration)
        stop()


def spin_left(speed=7, duration=None):
    """Spin left in place."""
    turn_left(speed=speed, duration=duration)


def spin_right(speed=7, duration=None):
    """Spin right in place."""
    turn_right(speed=speed, duration=duration)


def stop():
    """Coast all three motors to a stop."""
    rcx.motor_off(0)
    rcx.motor_off(1)
    rcx.motor_off(2)


def brake():
    """Hard-brake all three motors immediately."""
    rcx.motor_brake(0)
    rcx.motor_brake(1)
    rcx.motor_brake(2)


def wait(seconds):
    """Pause execution for the given number of seconds."""
    time.sleep(seconds)
