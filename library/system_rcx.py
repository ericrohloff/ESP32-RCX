"""
system_rcx.py — RCX system and utility commands.

Upload to ESP32 via Install RCX Lib. Requires rcx_driver.py to be installed first.

Usage:
    from system_rcx import ping, power_off, set_message
"""

from rcx_driver import rcx


def ping():
    """Send an alive check to the RCX."""
    rcx._send(0x10)


def stop_all():
    """Stop all running tasks on the RCX."""
    rcx._send(0x50)


def power_off():
    """Turn off the RCX."""
    rcx._send(0x60)


def set_time(hours, minutes):
    """Set the RCX internal clock. hours: 0-23, minutes: 0-59."""
    rcx._send(0x22, [hours, minutes])


def set_range(long_range=False):
    """Set IR transmitter range. long_range=True for wider coverage."""
    rcx._send(0x31, [1 if long_range else 0])


def set_power_down(minutes):
    """Set auto power-off delay. 0 disables auto-off."""
    rcx._send(0x46, [minutes])


def set_message(value):
    """Broadcast an IR message (0-255) to nearby RCX bricks."""
    rcx._send(0xf7, [value])


def clear_timer(timer_id):
    """Reset a timer to zero. timer_id: 0-3."""
    rcx._send(0x56, [timer_id])
