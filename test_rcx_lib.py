"""
Test suite for rcx_lib.py bidirectional communication

Tests response parsing, checksum validation, and echo handling.
"""

from rcx_lib import RCX


def test_basic_command_generation():
    """Test that commands generate correct bytecode."""
    rcx = RCX()
    rcx.beep()

    bytecode = rcx.get_bytecode()
    assert len(bytecode) > 0, "Bytecode should not be empty"
    assert bytecode[:3] == bytes(
        [0x55, 0xFF, 0x00]), "Should start with preamble"
    print("✓ Basic command generation works")


def test_toggle_bit():
    """Test that toggle bit alternates correctly."""
    rcx = RCX()

    # First command without toggle bit
    assert rcx.toggle_bit == False
    rcx.beep()
    assert rcx.toggle_bit == True, "Toggle bit should flip after first command"

    rcx.beep()
    assert rcx.toggle_bit == False, "Toggle bit should flip after second command"
    print("✓ Toggle bit alternates correctly")


def test_checksum_validation():
    """Test checksum validation."""
    rcx = RCX()

    # Create a valid payload with correct checksum
    opcode = 0x51
    params = [0x01]

    # Calculate checksum as done in _send()
    checksum = opcode
    for p in params:
        checksum = (checksum + p) % 256

    # Valid data: opcode + complement + params + complements + checksum + complement
    valid_data = bytearray([opcode, opcode ^ 0xFF])
    for p in params:
        valid_data.extend([p, p ^ 0xFF])
    valid_data.extend([checksum, checksum ^ 0xFF])

    assert rcx._validate_checksum(
        bytes(valid_data)), "Valid checksum should pass"

    # Test invalid checksum
    invalid_data = bytearray(valid_data)
    invalid_data[-2] ^= 0x01  # Corrupt the checksum

    assert not rcx._validate_checksum(
        bytes(invalid_data)), "Invalid checksum should fail"
    print("✓ Checksum validation works")


def test_response_extraction_simple():
    """Test extracting reply from response."""
    rcx = RCX()

    # Create a simple reply packet (no payload)
    opcode = 0x00
    checksum = opcode % 256

    reply = bytearray([0x55, 0xFF, 0x00])  # Preamble
    reply.extend([opcode, opcode ^ 0xFF])  # Opcode + complement
    reply.extend([checksum, checksum ^ 0xFF])  # Checksum + complement

    success, payload = rcx._extract_reply(bytes(reply))
    assert success, "Should successfully extract valid reply"
    assert payload == b'', "Payload should be empty for this reply"
    print("✓ Simple reply extraction works")


def test_response_extraction_with_echo():
    """Test extracting reply with echo present."""
    rcx = RCX()

    # Create TX message (command)
    tx_msg = bytearray([0x55, 0xFF, 0x00, 0x51, 0xAE, 0x01, 0xFE, 0x52, 0xAD])

    # Create RX response with echo + reply
    opcode = 0x00
    checksum = opcode % 256
    reply = bytearray([0x55, 0xFF, 0x00])  # Preamble
    reply.extend([opcode, opcode ^ 0xFF])  # Opcode + complement
    reply.extend([checksum, checksum ^ 0xFF])  # Checksum + complement

    # Response = echo + reply
    response = bytes(tx_msg) + bytes(reply)

    success, payload = rcx._process_response(response, bytes(tx_msg))
    assert success, "Should successfully extract reply with echo"
    assert payload == b'', "Payload should be empty"
    print("✓ Reply extraction with echo works")


def test_response_with_payload():
    """Test extracting reply with actual payload."""
    rcx = RCX()

    # Create a reply with payload bytes
    opcode = 0x07  # Some command
    payload_bytes = [0x42, 0x13]  # Example sensor reading

    # Calculate checksum
    checksum = opcode
    for p in payload_bytes:
        checksum = (checksum + p) % 256

    reply = bytearray([0x55, 0xFF, 0x00])  # Preamble
    reply.extend([opcode, opcode ^ 0xFF])  # Opcode + complement

    # Add payload with complements
    for p in payload_bytes:
        reply.extend([p, p ^ 0xFF])

    reply.extend([checksum, checksum ^ 0xFF])  # Checksum + complement

    success, extracted_payload = rcx._extract_reply(bytes(reply))
    assert success, "Should successfully extract reply with payload"
    assert extracted_payload == bytes(
        payload_bytes), f"Payload mismatch: {extracted_payload.hex()} vs {bytes(payload_bytes).hex()}"
    print("✓ Reply extraction with payload works")


def test_clear():
    """Test clearing packet queue."""
    rcx = RCX()
    rcx.beep()
    rcx.beep()

    packets = rcx.get_packets()
    assert len(packets) == 2, "Should have 2 packets"

    rcx.clear()
    packets = rcx.get_packets()
    assert len(packets) == 0, "Packets should be cleared"
    assert rcx.toggle_bit == False, "Toggle bit should be reset"
    print("✓ Clear function works")


def run_all_tests():
    """Run all tests."""
    print("\nRunning rcx_lib tests...\n")

    test_basic_command_generation()
    test_toggle_bit()
    test_checksum_validation()
    test_response_extraction_simple()
    test_response_extraction_with_echo()
    test_response_with_payload()
    test_clear()

    print("\n✅ All tests passed!\n")


if __name__ == "__main__":
    run_all_tests()
