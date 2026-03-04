"""
rcx_lib.py - Python wrapper for RCX/LASM commands

This library provides a simple Pythonicinterface to control a LEGO RCX brick
via IR using LASM opcodes. It generates bytecode that the ESP32 firmware
(esp32_driver.py) can interpret and execute.

Usage:
    from rcx_lib import RCX
    
    rcx = RCX()
    rcx.beep()
    rcx.motor_on(0)  # Turn on motor A
    rcx.motor_off(0)
    rcx.stop_all_tasks()
    rcx.wait(1.0)  # Wait 1 second
    
    # Get the binary payload to send
    bytecode = rcx.get_bytecode()
"""


class RCX:
    """
    Python interface to RCX control via LASM opcodes.

    Supports basic motor control, sound, and timing operations
    compatible with the esp32_driver.py StandaloneRCX class.
    """

    def __init__(self):
        """Initialize RCX controller."""
        self.toggle_bit = False
        self.packets = []

    def _send(self, opcode, params=None):
        """
        Build and queue an RCX packet.

        Args:
            opcode: RCX opcode (e.g., 0x51 for beep)
            params: List of parameter bytes
        """
        if params is None:
            params = []

        # Apply toggle bit to opcode
        tx_opcode = opcode | 0x08 if self.toggle_bit else opcode
        self.toggle_bit = not self.toggle_bit

        # Build packet: [preamble, preamble, preamble, opcode, opcode^0xFF, ...]
        packet = bytearray([0x55, 0xFF, 0x00, tx_opcode, tx_opcode ^ 0xFF])
        checksum = tx_opcode

        # Add parameters with complement bytes
        for p in params:
            packet.extend([p, p ^ 0xFF])
            checksum = (checksum + p) % 256

        # Add checksum and its complement
        packet.extend([checksum, checksum ^ 0xFF])
        self.packets.append(bytes(packet))

    def beep(self):
        """Play a beep sound on the RCX."""
        self._send(0x51, [0x01])

    def motor_on(self, motor_id):
        """
        Turn on a motor.

        Args:
            motor_id: 0 (A), 1 (B), or 2 (C)
        """
        if 0 <= motor_id <= 2:
            self._send(0x21, [0x80 | (1 << motor_id)])

    def motor_off(self, motor_id):
        """
        Turn off a motor.

        Args:
            motor_id: 0 (A), 1 (B), or 2 (C)
        """
        if 0 <= motor_id <= 2:
            self._send(0x21, [0x40 | (1 << motor_id)])

    def stop_all_tasks(self):
        """Stop all running tasks on the RCX."""
        self._send(0x50)

    def set_motor_power(self, motor_id, power):
        """
        Set motor power level (PWM-style).

        Args:
            motor_id: 0 (A), 1 (B), or 2 (C)
            power: 0-7 (power level)
        """
        if 0 <= motor_id <= 2 and 0 <= power <= 7:
            # Opcode 0x13 sets motor power
            self._send(0x13, [motor_id, power])

    def set_direction(self, motor_id, direction):
        """
        Set motor direction.

        Args:
            motor_id: 0 (A), 1 (B), or 2 (C)
            direction: 0 (fwd), 1 (rev), 2 (brake)
        """
        if 0 <= motor_id <= 2 and 0 <= direction <= 2:
            # Opcode 0x13 with different param
            self._send(0x13, [(motor_id << 2) | direction])

    def get_sensor(self, port):
        """
        Request sensor reading.

        Args:
            port: Sensor port (0-3)
        """
        if 0 <= port <= 3:
            self._send(0x07, [port])

    def wait_seconds(self, seconds):
        """
        Wait for N seconds (blocking).

        Args:
            seconds: Float, seconds to wait
        """
        # Units: centiseconds (10ms)
        centiseconds = int(seconds * 100)
        if centiseconds > 0:
            # Opcode 0x24: Wait
            # Param: duration in centiseconds (0-255)
            while centiseconds > 0:
                duration = min(centiseconds, 255)
                self._send(0x24, [duration])
                centiseconds -= duration

    def get_bytecode(self):
        """
        Get the full bytecode sequence as bytes.

        Returns:
            bytes: Concatenated packet data ready to send to RCX
        """
        return b''.join(self.packets)

    def get_packets(self):
        """
        Get list of individual packets.

        Returns:
            list of bytes: Each packet separately
        """
        return self.packets

    def clear(self):
        """Clear the packet queue."""
        self.packets = []
        self.toggle_bit = False


# Convenience instance for quick use
rcx = RCX()
