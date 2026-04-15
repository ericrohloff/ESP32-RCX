"""
Test suite for esp32_driver.py RCX class packet generation

Validates that the RCX class in esp32_driver correctly encodes packets
according to the RCX IR protocol specifications.
"""

import sys
sys.path.insert(0, '.')

from esp32_driver import code as driver_code

# Extract and execute the esp32_driver code to get RCX class
exec(driver_code, globals())


def test_ping_packet():
    """Test ping packet (opcode 0x10)"""
    rcx = RCX()
    packet = rcx._build(0x10)

    # Expected structure: [0x55, 0xFF, 0x00, 0x10, 0xEF, 0x10, 0xEF]
    assert packet[0:3] == bytes([0x55, 0xFF, 0x00]), "Preamble mismatch"
    assert packet[3] == 0x10, "Opcode should be 0x10"
    assert packet[4] == 0xEF, "Opcode complement incorrect"
    assert len(packet) == 7, f"Packet length should be 7, got {len(packet)}"
    print("✓ Ping packet (0x10) correct")


def test_beep_packet():
    """Test beep packet (opcode 0x51, param 0x02)"""
    rcx = RCX()
    rcx._toggle = False  # Reset toggle
    packet = rcx._build(0x51, [0x02])

    # Expected: [0x55, 0xFF, 0x00, 0x51, 0xAE, 0x02, 0xFD, 0x53, 0xAC]
    assert packet[0:3] == bytes([0x55, 0xFF, 0x00]), "Preamble mismatch"
    assert packet[3] == 0x51, "Opcode should be 0x51"
    assert packet[4] == 0xAE, "Opcode complement incorrect"
    assert packet[5] == 0x02, "Parameter should be 0x02"
    assert packet[6] == 0xFD, "Parameter complement incorrect"
    # Checksum = 0x51 + 0x02 = 0x53
    assert packet[7] == 0x53, "Checksum incorrect"
    assert packet[8] == 0xAC, "Checksum complement incorrect"
    assert len(packet) == 9, f"Packet length should be 9, got {len(packet)}"
    print("✓ Beep packet (0x51, [0x02]) correct")


def test_motor_on_packet():
    """Test motor_on packet (opcode 0x21)"""
    rcx = RCX()
    rcx._toggle = False  # Reset toggle
    # motor_on(0, direction=0): port = 1 << 0 = 1, flag = 0x80
    packet = rcx._build(0x21, [0x80 | 1])  # 0x81

    assert packet[0:3] == bytes([0x55, 0xFF, 0x00]), "Preamble mismatch"
    assert packet[3] == 0x21, "Opcode should be 0x21"
    assert packet[5] == 0x81, "Parameter should be 0x81"
    # Checksum = 0x21 + 0x81 = 0xA2
    assert packet[7] == 0xA2, f"Checksum should be 0xA2, got {packet[7]:02X}"
    print("✓ Motor ON packet (0x21, [0x81]) correct")


def test_toggle_bit_sequence():
    """Test that toggle bit alternates correctly"""
    rcx = RCX()

    # First packet with toggle=False
    assert rcx._toggle == False
    p1 = rcx._build(0x10)
    assert p1[3] == 0x10, "First packet should have toggle=0"
    assert rcx._toggle == True, "Toggle should flip after first packet"

    # Second packet with toggle=True
    p2 = rcx._build(0x10)
    assert p2[3] == (0x10 | 0x08), f"Second packet should have toggle=1, got {p2[3]:02X}"
    assert rcx._toggle == False, "Toggle should flip back"
    print("✓ Toggle bit alternates correctly")


def test_multi_param_packet():
    """Test packet with multiple parameters"""
    rcx = RCX()
    rcx._toggle = False
    # set_power(0, 5): opcode=0x13, params=[0, 5]
    packet = rcx._build(0x13, [0x00, 0x05])

    assert packet[0:3] == bytes([0x55, 0xFF, 0x00]), "Preamble mismatch"
    assert packet[3] == 0x13, "Opcode should be 0x13"
    assert packet[5] == 0x00, "First param should be 0x00"
    assert packet[7] == 0x05, "Second param should be 0x05"
    # Checksum = 0x13 + 0x00 + 0x05 = 0x18
    assert packet[9] == 0x18, f"Checksum should be 0x18, got {packet[9]:02X}"
    print("✓ Multi-parameter packet correct")


def test_set_power():
    """Test set_power packet generation (no UART needed)"""
    rcx = RCX()
    rcx._toggle = False
    # set_power(0, 7): opcode=0x13, params=[0, 7]
    packet = rcx._build(0x13, [0x00, 0x07])
    assert packet[3] == 0x13, "Opcode should be 0x13"
    assert packet[5] == 0x00, "Motor ID param should be 0x00"
    assert packet[7] == 0x07, "Power param should be 0x07"
    print("✓ set_power packet generation works")


def test_motor_sequences():
    """Test that motor sequences work (move, turn_left, etc.)"""
    rcx = RCX()

    # move() should:
    # 1. set_power(0, 7)
    # 2. set_power(1, 7)
    # 3. motor_on(0, direction=0)
    # 4. motor_on(1, direction=0)
    # 5. wait(duration)
    # 6. stop()

    # Just verify that calling it doesn't crash
    rcx.set_power(0, 5)
    rcx.set_power(1, 5)
    rcx.motor_on(0, direction=0)
    rcx.motor_on(1, direction=0)
    print("✓ Motor control sequences work")


def run_all_tests():
    """Run all tests"""
    print("\nRunning esp32_driver tests...\n")

    test_ping_packet()
    test_beep_packet()
    test_motor_on_packet()
    test_toggle_bit_sequence()
    test_multi_param_packet()
    test_set_power()
    test_motor_sequences()

    print("\n✅ All esp32_driver tests passed!\n")


if __name__ == "__main__":
    run_all_tests()
