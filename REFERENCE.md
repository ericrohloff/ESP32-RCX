# RoboLab ESP32-RCX Reference Notes

## Project Overview

PyScript-based web IDE that lets users write Python to control a LEGO RCX 2.0 brick
via IR through an ESP32 acting as an IR tower.

**Useful links**
- LASM Opcodes: https://www.mralligator.com/rcx/opcodes.html
- WebPBrick JS reference: https://github.com/maehw/WebPBrick/blob/main/en/src/fileFormats/KaitaiStream.js

---

## IR Protocol (How the ESP32 talks to the RCX)

The RCX communicates over IR using **raw UART serial** modulated onto a 38 kHz carrier.
It is NOT NEC, RC5, or any standard IR protocol. Missing the parity bit causes the RCX
to silently ignore all transmissions — the most common failure mode.

### Physical Layer
| Parameter         | Value                        |
|-------------------|------------------------------|
| Carrier frequency | 38 kHz                       |
| Carrier duty cycle| 33% (17–33% works)           |
| Baud rate         | 2400 baud                    |
| Bit duration      | ~417 µs (1,000,000 / 2400)   |
| IR light ON       | Logic LOW — UART SPACE       |
| IR light OFF      | Logic HIGH — UART MARK       |

The line idles with IR light OFF (logic HIGH).

### 12-Bit Byte Frame
Each byte is transmitted as 12 bits:

```
Bit 1    : START BIT      — always light ON  (logic LOW)
Bits 2-9 : DATA BITS      — LSB first
Bit 10   : PARITY BIT     — odd parity
Bit 11   : STOP BIT       — always light OFF (logic HIGH)
Bit 12   : INTER-BYTE GAP — always light OFF (idle)
```

Total: 12 bits × 417 µs = ~5 ms per byte.

### Parity Rule (Odd Parity)
Count the 1-bits in the data byte:
- Even count → parity bit = 1 (light OFF)
- Odd count  → parity bit = 0 (light ON)

Example: `0x55 = 0b01010101` → four 1-bits (even) → parity = 1 (light OFF)

### RMT Pulse Encoding
The ESP32 RMT peripheral takes a flat list of pulse durations. Consecutive bits in the
same state are merged into one longer pulse (run-length encoding).

```python
rmt = esp32.RMT(0, pin=Pin(2), clock_div=80, tx_carrier=(38000, 33, 1))
# clock_div=80 → 1 tick = 1 µs
# tx_carrier=(38000, 33, 1) → 38 kHz at 33% duty cycle
# start_val=1 → first pulse is light ON (START bit)
```

---

## RCX Packet Format (Direct Command Mode)

```
[55 FF 00] [op] [op^FF] [p1] [p1^FF] ... [ck] [ck^FF]
```

- `55 FF 00` — fixed preamble, always the same
- Each opcode and parameter byte is followed by its bitwise complement (`^ 0xFF`)
- Checksum `ck = (opcode + sum(params)) & 0xFF`, also followed by complement
- Toggle bit (`0x08`) is XOR'd into the opcode on alternating packets so the RCX
  can distinguish retransmissions from new commands

### Example — beep (sound 5)
```
55  FF  00  51  AE  05  FA  56  A9
preamble    op  ~op  p1  ~p1  ck  ~ck
```
`0x51 ^ 0xFF = 0xAE`, `0x05 ^ 0xFF = 0xFA`, `(0x51 + 0x05) & 0xFF = 0x56`

### Key Opcodes
| Command           | Opcode | Params                          |
|-------------------|--------|---------------------------------|
| Alive / ping      | 0x10   | none                            |
| Set motor on/off  | 0x21   | byte flags\|port_mask           |
| Set motor power   | 0x13   | byte motor_id, byte power (0-7) |
| Set time          | 0x22   | byte hours, byte minutes        |
| Play tone         | 0x23   | short freq (LE), byte duration  |
| Set sensor type   | 0x32   | byte sensor, byte type          |
| Set sensor mode   | 0x42   | byte sensor, byte mode          |
| Stop all tasks    | 0x50   | none                            |
| Play sound        | 0x51   | byte sound (1-5)                |
| Set display       | 0x33   | byte source, short argument     |
| Set TX range      | 0x31   | byte range (0=short, 1=long)    |
| Power off         | 0x60   | none                            |
| Set power-down    | 0x46   | byte minutes                    |
| Set message       | 0xF7   | byte value                      |
| Clear sensor      | 0x26   | byte sensor                     |
| Clear timer       | 0x56   | byte timer                      |

Full opcode list: https://www.mralligator.com/rcx/opcodes.html

---

## Motor Control (Opcode 0x21)

The `0x21` opcode uses a bit-flag byte to control direction and on/off state:

| Flags byte | Effect              |
|------------|---------------------|
| `0x80\|port` | Motor ON, forward  |
| `0x40\|port` | Motor OFF (coast)   |
| `0xC0\|port` | Motor brake         |

Port mask: Motor A = `0x01`, Motor B = `0x02`, Motor C = `0x04`

Example: motor A forward → `flags = 0x80 | 0x01 = 0x81`

---

## Hardware Notes

- Use an NPN transistor (PN2222A) in common-emitter to drive the IR LED
- Base resistor: 330 Ω – 1 kΩ. **10 kΩ is too high** — transistor won't saturate
- GPIO HIGH → transistor ON → LED ON (normal polarity)
- RCX IR receiver is less sensitive than the LEGO IR Tower
- Transmit at close range (a few centimetres) aimed at the RCX IR window
- Direct-to-RCX requires more IR power than tower-to-RCX

### ESP32 Pin Defaults
| Pin | Role                  |
|-----|-----------------------|
| 2   | IR LED (RMT output)   |
| 16  | UART RX (unused now)  |
| 17  | UART TX (unused now)  |

Only pin 2 is active. UART is no longer used — RMT handles all transmission.

---

## Common Mistakes

1. **Missing parity bit** → RCX silently ignores everything
2. **Wrong polarity** → garbled signal
3. **Using NEC or other IR protocol** → completely wrong encoding
4. **Base resistor too high** → weak IR signal, intermittent operation
5. **Wrong carrier duty cycle** → RCX receiver may reject signal
6. **NEC header pulses** → the `test/send.py` approach was wrong; `test/beep_test.py` is correct

---

## File Structure

```
/
├── index.html          main web app
├── commands.html       library reference (opens as modal)
├── styles.css
├── mini-coi.js         required for PyScript WebSerial (must be at root)
├── pyscript.toml       PyScript config — maps filenames to paths
├── pyscript/           browser-side Python
│   ├── main.py         packet building, template preview, UI helpers
│   ├── control_panel.py  serial connect, flash button, template loading
│   ├── RS232.py        serial terminal component + Install RCX Lib
│   └── esp32_driver.py   ESP32 MicroPython code as strings (uploaded to ESP32)
├── library/            standalone ESP32 module files (source of truth for library code)
│   ├── motion_rcx.py
│   ├── motors_rcx.py
│   ├── sound_rcx.py
│   ├── sensors_rcx.py
│   ├── display_rcx.py
│   └── system_rcx.py
└── test/               validated reference ESP32 scripts
    ├── beep_test.py    CORRECT encoding — 12-bit UART framing
    ├── send.py         early NEC test (wrong for RCX, kept for reference)
    ├── recieve.py
    └── snedrecieve.py
```

### How the library gets to the ESP32
The `library/` files are the readable source. Their content is duplicated as
`*_code` strings inside `pyscript/esp32_driver.py`. When the user clicks
**Install RCX Lib**, `RS232.py` uploads all strings via `board.upload()`.

If you edit a library module, update **both** the `library/` file and the
corresponding `*_code` string in `esp32_driver.py`.
