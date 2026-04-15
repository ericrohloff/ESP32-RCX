"""
rcx_lib.py - Python wrapper for RCX/LASM commands

This library provides a Pythonic interface to control a LEGO RCX brick
via IR using LASM opcodes. It supports full bidirectional communication,
handling both command transmission and response reception.

Runs directly on ESP32 MicroPython - includes UART setup and I/O.

Usage:
    from rcx_lib import RCX
    
    rcx = RCX()
    rcx.beep()
    rcx.motor_on(0)  # Turn on motor A
    rcx.motor_off(0)
    
    # Get bytecode and transmit/receive in one call
    success, payload = rcx.transceive(timeout=0.34)
"""

import time

# Try to import MicroPython modules (for ESP32)
try:
    import machine
    MICROPYTHON = True
except ImportError:
    MICROPYTHON = False


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

        # Initialize UART for IR communication (ESP32 MicroPython only)
        self.uart = None
        self.ir_pwm = None

        if MICROPYTHON:
            try:
                # 38kHz IR carrier
                self.ir_pwm = machine.PWM(machine.Pin(2))
                self.ir_pwm.freq(38000)
                self.ir_pwm.duty_u16(32768)  # 50% duty cycle

                # UART: 2400 Baud, 8 Bits, ODD Parity, 1 Stop Bit (RCX standard)
                self.uart = machine.UART(
                    1, baudrate=2400, bits=8, parity=1, stop=1, tx=17, rx=16)
            except Exception as e:
                print(f"Warning: UART initialization failed: {e}")
                self.uart = None

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
        if self.toggle_bit:
            tx_opcode = opcode | 0x08
        else:
            tx_opcode = opcode
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

    def _transmit_packet(self, packet_bytes):
        """
        Send a single packet over UART with inter-byte delays.

        Args:
            packet_bytes: bytes to transmit

        Returns:
            bool: True if transmission successful
        """
        if not self.uart:
            print("Error: UART not initialized")
            return False

        try:
            # Send the whole packet; UART hardware handles 2400-baud timing
            self.uart.write(packet_bytes)
            # Allow ~4 ms/byte * 9 bytes + inter-packet gap
            if MICROPYTHON:
                time.sleep_ms(100)
            else:
                time.sleep(0.1)

            return True
        except Exception as e:
            print(f"Transmission error: {e}")
            return False

    def _receive_bytes(self, timeout_ms=340):
        """
        Receive bytes from UART with timeout.

        Args:
            timeout_ms: timeout in milliseconds

        Returns:
            bytes: received data or empty bytes if timeout
        """
        if not self.uart:
            return b''

        try:
            received = bytearray()
            start_time = time.ticks_ms() if MICROPYTHON else time.time() * 1000

            while True:
                if MICROPYTHON:
                    elapsed = time.ticks_diff(time.ticks_ms(), start_time)
                else:
                    elapsed = (time.time() * 1000) - start_time

                if elapsed > timeout_ms:
                    break

                # Check for available bytes
                if self.uart.any():
                    byte = self.uart.read(1)
                    if byte:
                        received.extend(byte)
                        # Reset timeout after each byte received
                        start_time = time.ticks_ms() if MICROPYTHON else time.time() * 1000
                else:
                    # Small sleep to avoid busy-waiting
                    if MICROPYTHON:
                        time.sleep_ms(1)
                    else:
                        time.sleep(0.001)

            return bytes(received)
        except Exception as e:
            print(f"Reception error: {e}")
            return b''

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
        Send command bytes and wait for response (with actual UART I/O).

        Args:
            tx_bytes: bytes to transmit
            timeout: time to wait for response in seconds
            ignore_reply: if True, don't wait for or validate reply

        Returns:
            tuple: (success: bool, payload: bytes or None)
        """
        if not self.uart:
            print("Error: UART not initialized for communication")
            return False, None

        # Send the command
        success = self._transmit_packet(tx_bytes)
        if not success:
            return False, None

        if ignore_reply:
            return True, None

        # Receive response (convert timeout to ms)
        timeout_ms = int(timeout * 1000)
        response = self._receive_bytes(timeout_ms)

        if not response:
            print("Error: No response received from RCX")
            return False, None

        # Process and validate response
        return self._process_response(response, tx_bytes)

    def transceive(self, timeout=0.34, ignore_reply=False):
        """
        Transmit queued commands and receive response in one call.

        This is the main method to use after queueing commands.

        Args:
            timeout: time to wait for response in seconds
            ignore_reply: if True, don't validate response

        Returns:
            tuple: (success: bool, payload: bytes or None)
        """
        # Get all queued packets
        tx_bytes = self.get_bytecode()

        if not tx_bytes:
            print("Error: No commands queued")
            return False, None

        # Send and receive
        return self.send_and_receive(tx_bytes, timeout, ignore_reply)

    def beep(self):
        """Play a beep sound on the RCX."""
        self._send(0x51, [1])

    def motor_on(self, motor_id):
        """
        Turn on a motor.

        Args:
            motor_id: 0 (A), 1 (B), or 2 (C)
        """
        if 0 <= motor_id <= 2:
            self._send(33, [128 | (1 << motor_id)])

    def motor_off(self, motor_id):
        """
        Turn off a motor.

        Args:
            motor_id: 0 (A), 1 (B), or 2 (C)
        """
        if 0 <= motor_id <= 2:
            self._send(33, [64 | (1 << motor_id)])

    def stop_all_tasks(self):
        """Stop all running tasks on the RCX."""
        self._send(80)

    def set_motor_power(self, motor_id, power):
        """
        Set motor power level (PWM-style).

        Args:
            motor_id: 0 (A), 1 (B), or 2 (C)
            power: 0-7 (power level)
        """
        if 0 <= motor_id <= 2 and 0 <= power <= 7:
            # Opcode 19 sets motor power
            self._send(19, [motor_id, power])

    def set_direction(self, motor_id, direction):
        """
        Set motor direction.

        Args:
            motor_id: 0 (A), 1 (B), or 2 (C)
            direction: 0 (fwd), 1 (rev), 2 (brake)
        """
        if 0 <= motor_id <= 2 and 0 <= direction <= 2:
            # Opcode 19 with different param
            self._send(19, [(motor_id << 2) | direction])

    def get_sensor(self, port):
        """
        Request sensor reading.

        Args:
            port: Sensor port (0-3)
        """
        if 0 <= port <= 3:
            self._send(7, [port])

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
                self._send(36, [duration])
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


# Example usage for ESP32 MicroPython:
#
# from rcx_lib import RCX
#
# rcx = RCX()
#
# # Queue commands
# rcx.beep()
# rcx.motor_on(0)
#
# # Send commands and receive response in one call
# success, payload = rcx.transceive(timeout=0.34)
#
# if success:
#     print(f"Response OK - Payload: {payload.hex()}")
# else:
#     print("Communication failed")
