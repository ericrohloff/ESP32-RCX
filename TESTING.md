# RoboLab PyScript Program Communication Test Guide

This guide walks you through testing the complete communication pipeline from PyScript IDE to RCX execution.

## Architecture Overview

```
Browser (PyScript)
    ├─ main.py: Packet visualization, test functions
    ├─ control_panel.py: Serial connection, templates, flash code
    └─ index.html: UI (mpy-editor, buttons, terminal)
           ↓
    WebSerial → ESP32 (via USB)
           ↓
    ESP32 MicroPython
    ├─ Imports rcx_driver (uploaded code)
    ├─ Runs user program (from mpy-editor)
    └─ Program calls: from rcx_driver import rcx
           ↓
    IR UART (pins 16/17, 2400 baud)
           ↓
    RCX 2.0 Brick
    ├─ Receives IR packets
    ├─ Executes commands
    └─ Sends replies back
```

## Communication Pipeline Steps

### Step 1: Packet Generation (Validated ✓)
The RCX protocol packet generation has been tested and verified correct:
- **Preamble**: 0x55 0xFF 0x00
- **Opcode + Complement**: Each byte followed by XOR 0xFF complement
- **Toggle Bit**: Alternates in opcode bit 3 (0x08)
- **Checksum**: Sum of opcode + all params, modulo 256

**Test Results**: All protocol tests pass
```
✓ Ping packet (0x10) - 7 bytes
✓ Beep packet (0x51, [0x02]) - 9 bytes
✓ Motor ON packet (0x21) - 9 bytes
✓ Toggle bit alternates correctly
✓ Multi-parameter packets correct
```

### Step 2: Flash Code to ESP32
The `flash_code()` function in control_panel.py now correctly:
1. Imports esp32_driver.code (the MicroPython string)
2. Appends user program from mpy-editor
3. Uploads full script to ESP32 as main.py
4. ESP32 runs main.py on next reboot

**To test**:
1. Open http://localhost:8000 (or your dev server)
2. Connect to ESP32 via "Connect" button
3. Load a template: "Beep Test" → "Load Template"
4. Click "Flash Code"
5. Watch terminal for upload confirmation
6. Press ESP32 reset button to reboot

### Step 3: Program Execution on ESP32
When ESP32 boots, it runs main.py which:
```python
from rcx_driver import rcx
rcx.beep()
```

This calls the RCX class methods which immediately:
1. Build the IR packet
2. Send it over UART
3. Wait for RCX acknowledgment
4. Return success/failure

### Step 4: IR Communication to RCX
The ESP32 UART outputs the packet bytes:
- **Speed**: 2400 baud
- **Format**: 8-bit, ODD parity, 1 stop bit
- **Carrier**: 38 kHz PWM on pin 2
- **UART Pins**: TX=17, RX=16

RCX processes packet and:
- Echoes TX packet back
- Executes command
- Sends reply with result

## Testing Checklists

### Packet Visualization Tests
These test packets without hardware:

- [ ] **Ping**: Click "Ping RCX" → packet visualizer shows blue/green/red bytes
- [ ] **Beep**: Click "Play Beep" → packet visualizer shows 0x51 opcode
- [ ] **Stop**: Shows 0x50 opcode

Expected packet structure visible in colored chips:
```
[Preamble: 55 FF 00] [Opcode: 51] [Opcode^: AE] [Param: 02] [Param^: FD] [CK: 53] [CK^: AC]
```

### Full Communication Tests (Requires ESP32 + RCX)

#### Test 1: Beep Test
- [ ] Load "Beep Test" template
- [ ] Flash to ESP32
- [ ] Reboot ESP32
- [ ] RCX should beep once
- [ ] Terminal shows packet trace

#### Test 2: Move Forward
- [ ] Load "Move Forward (2 s)" template
- [ ] Flash to ESP32
- [ ] Reboot ESP32
- [ ] RCX should move forward for 2 seconds
- [ ] Then beep at end

#### Test 3: Motor Test
- [ ] Load "Motor A / B Test" template
- [ ] Flash to ESP32
- [ ] Reboot ESP32
- [ ] Motor A spins for 1.5s
- [ ] Motor B spins for 1.5s
- [ ] Final beep

#### Test 4: Drive Pattern
- [ ] Load "Drive Pattern" template
- [ ] Flash to ESP32
- [ ] Reboot ESP32
- [ ] RCX: forward 2s → left turn 0.6s → forward 2s → stop → beep

#### Test 5: Spin Turn
- [ ] Load "Spin Left & Right" template
- [ ] Flash to ESP32
- [ ] Reboot ESP32
- [ ] Left turn 1s at speed 5
- [ ] Right turn 1s at speed 5
- [ ] Stop and beep

## Troubleshooting

### "RCX: no response" 
- [ ] Check ESP32 UART pins (TX=17, RX=16)
- [ ] Verify 2400 baud, 8-bit, ODD parity, 1 stop
- [ ] Check IR LED is connected to pin 2
- [ ] Verify RCX is powered on and in range
- [ ] Check IR receiver connection

### Program uploads but RCX doesn't respond
- [ ] Flash "beep_test" template and verify ESP32 terminal shows packet trace
- [ ] If packet traces appear but RCX silent: hardware issue (IR LED/receiver)
- [ ] If packet traces don't appear: code not running on ESP32

### Template doesn't load into editor
- [ ] Check console for errors (browser dev tools)
- [ ] Verify #template-select element exists in HTML
- [ ] Verify #mpCode1 element is the mpy-editor

## Code Files Involved

| File | Role |
|------|------|
| **esp32_driver.py** | Container for RCX class (MicroPython code) |
| **control_panel.py** | Flash handler, template loading |
| **main.py** | Packet visualization, test functions |
| **index.html** | UI: editor, templates, buttons |
| **rcx_lib.py** | PC/browser testable version (queue-based API) |

## Key RCX Opcodes

| Opcode | Command | Parameters | Purpose |
|--------|---------|------------|---------|
| 0x10 | Ping | — | Verify RCX alive |
| 0x51 | Beep | [sound] | Play sound (1-5) |
| 0x21 | Motor On/Off | [flags \| port] | Control motor |
| 0x13 | Set Power | [motor_id, power] | Set motor PWM 0-7 |
| 0x50 | Stop Tasks | — | Emergency stop |

## Next Steps After Testing

1. If hardware communication works: Programs are communicating correctly ✓
2. If beep/ping work but movement doesn't: Motor control may need flag validation
3. If nothing responds: Debug packet transmission (oscilloscope/logic analyzer)

---

**Created**: 2026-04-15
**Protocol Version**: RCX 2.0 Direct Command Mode
