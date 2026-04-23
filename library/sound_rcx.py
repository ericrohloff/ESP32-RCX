"""
sound_rcx.py — Sound and tone output.

Upload to ESP32 via Install RCX Lib. Requires rcx_driver.py to be installed first.

Usage:
    from sound_rcx import beep, play_tone, BEEP, SWEEP

play_tone frequency is in Hz; duration is in 1/100ths of a second (50 = 0.5s).
"""

from rcx_driver import rcx

BLIP  = 1
BEEP  = 2
SWEEP = 3
PLING = 4
BUZZ  = 5


def beep(sound=BEEP):
    """Play a preset RCX sound. sound: BLIP, BEEP, SWEEP, PLING, or BUZZ."""
    rcx._send(0x51, [sound])


def play_tone(frequency, duration):
    """
    Play a tone at the given frequency.
    frequency : Hz (e.g. 440 for concert A)
    duration  : 1/100ths of a second (e.g. 50 = 0.5s, 100 = 1s)
    """
    freq_lo = frequency & 0xFF
    freq_hi = (frequency >> 8) & 0xFF
    rcx._send(0x23, [freq_lo, freq_hi, duration])
