"""
rcx_lib.py - Python wrapper for RCX/LASM commands

This library provides a Pythonic interface to control a LEGO RCX brick
via IR using LASM opcodes. It supports bidirectional communication with
the RCX, sending commands and receiving responses.

Usage:
    from rcx_lib import RCX
    
    rcx = RCX()
    rcx.beep()
    rcx.motor_on(0)  # Turn on motor A
    rcx.motor_off(0)
    rcx.stop_all_tasks()
    rcx.wait(1.0)  # Wait 1 second
    
    # Send and receive responses
    success, payload = rcx_tower.send_and_receive(rcx.get_bytecode(), timeout=0.34)
"""

import time


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
        self.preamble = bytes([0x55, 0xFF, 0x00])

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

    def _validate_checksum(self, data):
        """
        Validate packet checksum.

        Args:
            data: bytes including opcode, params, checksum, and complement
                  (may include preamble as first 3 bytes)

        Returns:
            bool: True if checksum is valid
        """
        if len(data) < 2:
            return False

        # Skip preamble if present (First 3 bytes are preamble)
        start_pos = 0
        if len(data) >= 3 and data[:3] == self.preamble:
            start_pos = 3

        if len(data) - start_pos < 4:
            # Not enough data (need at least opcode + comp + checksum + comp)
            return False

        # Extract checksum and its complement (last two bytes)
        checksum = data[-2]
        checksum_complement = data[-1]

        # Verify complement byte
        if checksum ^ checksum_complement != 0xFF:
            return False

        # Calculate checksum from opcode and params only
        # Start after preamble, skip complement bytes
        calculated = 0
        pos = start_pos

        # First byte is opcode
        if pos < len(data):
            calculated = data[pos]
            pos += 2  # Skip opcode and its complement

        # Process remaining bytes (params with their complements)
        while pos < len(data) - 2:  # Stop before checksum + complement
            if pos + 1 < len(data) - 2:
                # We have both data and complement bytes
                data_byte = data[pos]
                calculated = (calculated + data_byte) % 256
                pos += 2  # Skip this data byte and its complement
            else:
                # Odd byte without complement - shouldn't happen
                return False

        return calculated == checksum

    def _extract_reply(self, response_bytes):
        """
        Extract the actual reply from response bytes (removing echo).

        The response format is:
        - Echo of transmitted message
        - Preamble (0x55, 0xFF, 0x00)
        - Opcode and its complement
        - Payload bytes (each with complement)
        - Checksum and its complement

        Args:
            response_bytes: Raw bytes received

        Returns:
            tuple: (success: bool, payload: bytes or None)
        """
        if len(response_bytes) < len(self.preamble):
            return False, None

        # Try to find the preamble of the actual reply
        # The response may start with an echo, so we need to look for preamble
        preamble_pos = -1

        # Look for preamble in the response
        for i in range(len(response_bytes) - len(self.preamble) + 1):
            if response_bytes[i:i+len(self.preamble)] == self.preamble:
                # Found a potential preamble
                # Try to extract reply from this position
                reply_start = i
                if i >= len(self.preamble):
                    # This is likely the echo followed by the real reply
                    preamble_pos = i
                    break
                elif i == 0:
                    # This could be the first preamble (part of echo or the reply itself)
                    preamble_pos = i

        if preamble_pos == -1:
            # No preamble found
            return False, None

        reply_data = response_bytes[preamble_pos:]

        # Minimum reply: preamble (3) + opcode (1) + complement (1) + checksum (1) + comp (1) = 7 bytes
        if len(reply_data) < 7:
            return False, None

        # Extract opcode and verify it has a complement
        opcode_pos = len(self.preamble)
        if opcode_pos + 1 >= len(reply_data):
            return False, None

        opcode = reply_data[opcode_pos]
        opcode_complement = reply_data[opcode_pos + 1]

        # Verify opcode complement
        if opcode ^ opcode_complement != 0xFF:
            return False, None

        # Extract the data portion (opcode + params for checksum validation)
        # Length is: opcode (1) + complement (1) + params (variable) + checksum (1) + comp (1)
        # We need to figure out where params end and checksum begins

        # The checksum should be the second-to-last byte
        checksum_pos = len(reply_data) - 2
        if checksum_pos < opcode_pos + 1:
            return False, None

        # Extract all data for checksum validation (opcode through all params)
        data_for_checksum = bytearray([opcode])

        # All bytes between opcode+complement and checksum should be params
        param_start = opcode_pos + 2
        param_end = checksum_pos

        if param_end >= param_start:
            # There are payload bytes
            params = reply_data[param_start:param_end]

            # Validate that each param has a complement
            if len(params) % 2 != 0:
                # Odd number of bytes - invalid (should be pairs of data + complement)
                return False, None

            # Extract just the data bytes (every other byte starting at 0)
            payload = bytearray()
            for i in range(0, len(params), 2):
                data_byte = params[i]
                comp_byte = params[i + 1]

                if data_byte ^ comp_byte != 0xFF:
                    # Invalid complement
                    return False, None

                payload.append(data_byte)
                data_for_checksum.append(data_byte)

        # Validate checksum
        checksum = reply_data[checksum_pos]
        checksum_complement = reply_data[checksum_pos + 1]

        if checksum ^ checksum_complement != 0xFF:
            return False, None

        # Calculate expected checksum
        calculated_checksum = sum(data_for_checksum) % 256

        if calculated_checksum != checksum:
            return False, None

        return True, bytes(payload)

    def _process_response(self, response_bytes, tx_bytes):
        """
        Process response including echo handling and reply extraction.

        The tower echoes back the transmitted message, so we need to:
        1. Check for echo
        2. Remove echo from response
        3. Extract the actual reply

        Args:
            response_bytes: Raw bytes received from tower
            tx_bytes: Original transmitted bytes (for echo verification)

        Returns:
            tuple: (success: bool, payload: bytes or None)
        """
        if len(response_bytes) < len(tx_bytes):
            # Response too short to contain even the echo
            return False, None

        # Check if response starts with echo of transmitted message
        if response_bytes[:len(tx_bytes)] == tx_bytes:
            # Standard echo - strip it
            remaining = response_bytes[len(tx_bytes):]
        else:
            # Check for "glitchy echo" (offset by 1 byte)
            if len(response_bytes) > len(tx_bytes) + 1:
                if response_bytes[1:len(tx_bytes)+1] == tx_bytes:
                    # Glitchy echo - strip it and the extra byte
                    remaining = response_bytes[len(tx_bytes)+1:]
                else:
                    # No recognizable echo, try to extract reply from raw response
                    remaining = response_bytes
            else:
                remaining = response_bytes

        # Extract reply from remaining bytes
        return self._extract_reply(remaining if remaining else response_bytes)

    def send_and_receive(self, tx_bytes, timeout=0.34, ignore_reply=False):
        """
        Send command bytes and wait for response.

        This method is intended to be called by the tower/driver code
        that handles actual serial communication.

        Args:
            tx_bytes: bytes to transmit
            timeout: time to wait for response in seconds
            ignore_reply: if True, don't wait for or validate reply

        Returns:
            tuple: (success: bool, payload: bytes or None)
        """
        if ignore_reply:
            return True, None

        # Note: Actual serial communication would happen here
        # This is a placeholder showing the protocol interface
        # The ESP32 driver would implement the actual serial I/O

        return False, None

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


# Example usage for ESP32 tower implementation:
#
# from rcx_lib import RCX
# import serial
#
# rcx = RCX()
# rcx.beep()
# rcx.motor_on(0)
#
# tx_bytes = rcx.get_bytecode()
#
# # ESP32 driver would handle serial communication:
# ser = serial.Serial('/dev/ttyUSB0', 2400, timeout=0.34)
# ser.write(tx_bytes)
#
# # Receive response (including echo)
# response = ser.read(1024)  # Read enough bytes
#
# # Validate and extract payload
# success, payload = rcx.send_and_receive(tx_bytes, timeout=0.34)
# # Or manually:
# success, payload = rcx._process_response(response, tx_bytes)
#
# if success:
#     print(f"Response payload: {payload.hex()}")
# else:
#     print("Invalid response")
