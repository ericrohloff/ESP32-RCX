# RCX Bidirectional Communication Implementation

## Summary of Changes to rcx_lib.py

The RCX library has been updated to support **full bidirectional communication**
with the RCX brick, not just command generation. This allows the ESP32 tower to
send commands and receive responses.

## New Methods Added

### 1. `_validate_checksum(data)`

- **Purpose**: Verify the checksum of a packet
- **Input**: Packet bytes (may include preamble)
- **Returns**: Boolean - True if checksum is valid
- **How it works**:
    - Extracts checksum and its complement from last 2 bytes
    - Recalculates checksum as sum of: opcode + all parameter bytes (excluding
      complements)
    - Compares calculated vs received checksum
    - Validates that each byte and its complement XOR to 0xFF

### 2. `_extract_reply(response_bytes)`

- **Purpose**: Extract the actual RCX reply from received response bytes
- **Input**: Raw bytes received from RCX
- **Returns**: Tuple `(success: bool, payload: bytes)`
- **How it works**:
    - Finds the preamble (0x55 0xFF 0x00) in the response
    - Validates opcode and its complement XOR to 0xFF
    - Extracts payload bytes (each with validation)
    - Validates checksum
    - Returns extracted payload if valid

### 3. `_process_response(response_bytes, tx_bytes)`

- **Purpose**: Handle full response processing including echo removal
- **Input**:
    - `response_bytes`: Raw bytes received from tower
    - `tx_bytes`: Original transmitted bytes (for echo verification)
- **Returns**: Tuple `(success: bool, payload: bytes)`
- **How it works**:
    - Detects echo from tower (tower sends back TX message)
    - Handles "glitchy echo" (echo offset by 1 byte)
    - Strips echo from response
    - Calls `_extract_reply()` on remaining bytes

### 4. `send_and_receive(tx_bytes, timeout=0.34, ignore_reply=False)`

- **Purpose**: Send command and optionally wait for response
- **Input**:
    - `tx_bytes`: Bytes to transmit
    - `timeout`: Time to wait for response (in seconds)
    - `ignore_reply`: If True, don't validate response
- **Returns**: Tuple `(success: bool, payload: bytes)`
- **Note**: Actual serial I/O is handled by ESP32 driver; this is the protocol
  interface

## Communication Protocol

### Packet Structure (Transmitted)

```
[Preamble] [Opcode] [Opcode^] [Param1] [Param1^] [Param2] [Param2^] ... [Checksum] [Checksum^]
[0x55,0xFF,0x00] [byte] [byte] [byte]   [byte]   [byte]   [byte]   ...  [byte]     [byte]
```

Where:

- **Preamble**: Always 0x55 0xFF 0x00
- **Opcode**: Command code (e.g., 0x51 for beep)
- **Opcode^**: Bitwise complement of opcode (XOR 0xFF)
- **Params**: Command parameters
- **Param^**: Complement of each parameter
- **Checksum**: Sum of (opcode + all params) mod 256
- **Checksum^**: Complement of checksum

### Response Structure (Received)

```
[Echo of TX] [Preamble] [Opcode] [Opcode^] [Payload bytes] [Checksum] [Checksum^]
```

The tower echoes back the transmitted message, then sends the actual reply.

### Toggle Bit

- Alternates on each command
- Set in bit 3 of opcode (OR with 0x08)
- Maintained across multiple commands

## Usage Example (ESP32 MicroPython)

```python
from rcx_lib import RCX

# Create controller
rcx = RCX()

# Queue commands
rcx.beep()
rcx.motor_on(0)

# Get bytecode
tx_bytes = rcx.get_bytecode()

# Transmit via IR (your ESP32 driver handles this)
transmit_to_rcx(tx_bytes)  # Call your ESP32 IR transmission function

# Receive response (including echo)
response = receive_from_rcx(timeout=0.34)  # Call your ESP32 IR receive function

# Process and validate response
success, payload = rcx._process_response(response, tx_bytes)

if success:
    print(f"Response OK - Payload: {payload.hex()}")
else:
    print("Response validation failed")
```

Simply copy `rcx_lib.py` to your ESP32 MicroPython filesystem and import it
directly. All command generation and response validation happens on the
device—no external serial communication needed.

## Key Features

✅ **Echo Detection**: Automatically detects and strips echo from responses ✅
**Checksum Validation**: Verifies data integrity ✅ **Complement Validation**:
Ensures each data byte has valid complement ✅ **Toggle Bit**: Maintains
stateful communication protocol ✅ **Robust Parsing**: Handles edge cases
(glitchy echo, variable payloads) ✅ **Fully Tested**: All functionality
validated with test suite

## Physical Communication

All code runs directly on the ESP32 MicroPython controller. The library handles
command encoding and response validation; your ESP32 IR driver handles the
actual IR transmission/reception.

Typical flow:

1. Python code on ESP32 calls RCX methods to queue commands
2. Call `get_bytecode()` to get IR payload
3. ESP32 IR driver transmits bytecode via IR to RCX
4. RCX processes command and sends response
5. ESP32 IR driver receives response bytes
6. Call `_process_response()` to validate and extract payload
7. All processing happens locally on the ESP32—no external dependencies needed
