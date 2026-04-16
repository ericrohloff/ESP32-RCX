import asyncio
from pyscript import document, window
from js import Uint8Array
import json
import RS232
import control_panel
from rcx_lib import RCX


# Core utilities for packet creation and visualization.
toggle_bit = False
myRS232 = RS232.CEEO_RS232(divName='all_things_rs232',
                           suffix='1', myCSS=False, default_code='sd')


def log_to_ui(message):
    """Log message to the console-log div; fallback to console if not present."""
    log_div = document.querySelector("#console-log")
    if not log_div:
        window.console.log(message)
        return
    new_entry = document.createElement("div")
    new_entry.style.borderBottom = "1px solid #222"
    new_entry.style.padding = "2px"
    new_entry.innerText = f"> {message}"
    log_div.appendChild(new_entry)


def visualize_packet(packet_list):
    """Visualize an RCX packet as colored byte chips in the packet-stream div."""
    stream_div = document.querySelector("#packet-stream")
    if not stream_div:
        return
    container = document.createElement("div")
    container.style.marginBottom = "8px"

    def create_span(val, category, is_comp=False):
        span = document.createElement("span")
        span.classList.add("packet-byte")
        span.classList.add(category)
        if is_comp:
            span.classList.add("byte-comp")
        span.innerText = f"{val:02X}"
        return span

    for i in range(3):
        container.appendChild(create_span(packet_list[i], "byte-preamble"))
    container.appendChild(create_span(packet_list[3], "byte-opcode"))
    container.appendChild(create_span(packet_list[4], "byte-opcode", True))
    param_end = len(packet_list) - 2
    for i in range(5, param_end):
        container.appendChild(create_span(
            packet_list[i], "byte-param", i % 2 == 0))
    container.appendChild(create_span(packet_list[-2], "byte-checksum"))
    container.appendChild(create_span(packet_list[-1], "byte-checksum", True))
    stream_div.appendChild(container)
    stream_div.scrollTop = stream_div.scrollHeight


def encode_rcx_packet(opcode, params=None):
    global toggle_bit
    if params is None:
        params = []
    tx_opcode = opcode | 0x08 if toggle_bit else opcode
    toggle_bit = not toggle_bit
    packet = [0x55, 0xFF, 0x00]
    packet.extend([tx_opcode, tx_opcode ^ 0xFF])
    checksum = tx_opcode
    for p in params:
        packet.extend([p, p ^ 0xFF])
        checksum = (checksum + p) % 256
    packet.extend([checksum, checksum ^ 0xFF])
    visualize_packet(packet)
    return Uint8Array.new(packet)


def build_ping_packet():
    return encode_rcx_packet(0x10)


def build_beep_packet():
    return encode_rcx_packet(0x51, [0x01])


def build_stop_packet():
    return encode_rcx_packet(0x50)


# Template packet generators for preview
def get_template_packets(template_name):
    """Generate expected packets for a template for preview."""
    packets_list = []

    if template_name == "beep_test":
        packets_list = [
            ("0x51 [0x02]", "Beep (sound 2)"),
        ]

    elif template_name == "move_forward":
        packets_list = [
            ("0x13 [0x00, 0x07]", "Set Power A=7"),
            ("0x13 [0x01, 0x07]", "Set Power B=7"),
            ("0x21 [0x81]", "Motor A ON (fwd)"),
            ("0x21 [0x81]", "Motor B ON (fwd)"),
            ("wait 2.0s", "Pause 2 seconds"),
            ("0x21 [0x41]", "Motor A OFF"),
            ("0x21 [0x42]", "Motor B OFF"),
            ("0x21 [0x44]", "Motor C OFF"),
            ("0x51 [0x02]", "Beep (sound 2)"),
        ]

    elif template_name == "drive_pattern":
        packets_list = [
            ("0x13 [0x00, 0x07]", "Set Power A=7"),
            ("0x13 [0x01, 0x07]", "Set Power B=7"),
            ("0x21 [0x81]", "Motor A ON (fwd)"),
            ("0x21 [0x81]", "Motor B ON (fwd)"),
            ("wait 2.0s", "Forward 2s"),
            ("0x13 [0x00, 0x07]", "Set Power A=7"),
            ("0x13 [0x01, 0x07]", "Set Power B=7"),
            ("0x21 [0x81]", "Motor A ON (fwd)"),
            ("0x21 [0x42]", "Motor B ON (rev)"),
            ("wait 0.6s", "Turn left 0.6s"),
            ("0x13 [0x00, 0x07]", "Set Power A=7"),
            ("0x13 [0x01, 0x07]", "Set Power B=7"),
            ("0x21 [0x81]", "Motor A ON (fwd)"),
            ("0x21 [0x81]", "Motor B ON (fwd)"),
            ("wait 2.0s", "Forward 2s"),
            ("0x21 [0x41]", "Motor A OFF"),
            ("0x21 [0x42]", "Motor B OFF"),
            ("0x21 [0x44]", "Motor C OFF"),
            ("0x51 [0x02]", "Beep"),
        ]

    elif template_name == "motor_test":
        packets_list = [
            ("0x13 [0x00, 0x05]", "Set Power A=5"),
            ("0x21 [0x81]", "Motor A ON"),
            ("wait 1.5s", "Motor A runs"),
            ("0x21 [0x41]", "Motor A OFF"),
            ("0x13 [0x01, 0x05]", "Set Power B=5"),
            ("0x21 [0x81]", "Motor B ON"),
            ("wait 1.5s", "Motor B runs"),
            ("0x21 [0x42]", "Motor B OFF"),
            ("0x51 [0x02]", "Beep"),
        ]

    elif template_name == "spin_turn":
        packets_list = [
            ("0x13 [0x00, 0x05]", "Set Power A=5"),
            ("0x13 [0x01, 0x05]", "Set Power B=5"),
            ("0x21 [0x81]", "Motor A ON (fwd)"),
            ("0x21 [0x42]", "Motor B ON (rev)"),
            ("wait 1.0s", "Spin left 1.0s"),
            ("0x13 [0x00, 0x05]", "Set Power A=5"),
            ("0x13 [0x01, 0x05]", "Set Power B=5"),
            ("0x21 [0x42]", "Motor A ON (rev)"),
            ("0x21 [0x81]", "Motor B ON (fwd)"),
            ("wait 1.0s", "Spin right 1.0s"),
            ("0x21 [0x41]", "Motor A OFF"),
            ("0x21 [0x42]", "Motor B OFF"),
            ("0x21 [0x44]", "Motor C OFF"),
            ("0x51 [0x02]", "Beep"),
        ]

    elif template_name == "square_pattern":
        packets_list = [
            ("0x13 [0x00, 0x05]", "Set Power A=5"),
            ("0x13 [0x01, 0x05]", "Set Power B=5"),
            ("(4x) Move + Turn Sequence", "Forward 1.5s, turn 0.5s"),
            ("0x21 [0x41]", "Motor A OFF"),
            ("0x21 [0x42]", "Motor B OFF"),
            ("0x21 [0x44]", "Motor C OFF"),
            ("0x51 [0x03]", "Beep (sweep sound)"),
        ]

    elif template_name == "acceleration":
        packets_list = [
            ("0x13 [0x00, 0x02]", "Set Power A=2"),
            ("0x13 [0x01, 0x02]", "Set Power B=2"),
            ("(6x) Power levels 2-7", "Each for 0.8s + 0.3s wait"),
            ("0x21 [0x41]", "Motor A OFF"),
            ("0x21 [0x42]", "Motor B OFF"),
            ("0x21 [0x44]", "Motor C OFF"),
            ("0x51 [0x02]", "Beep"),
        ]

    return packets_list


def display_template_packets(template_name):
    """Display expected packets for a template in the packet stream."""
    stream_div = document.querySelector("#packet-stream")
    if not stream_div:
        return

    packets_list = get_template_packets(template_name)
    if not packets_list:
        stream_div.innerHTML = f"<div style='color: #666; font-size: 0.9rem;'>Template '{template_name}' not found</div>"
        return

    stream_div.innerHTML = ""  # Clear

    for opcode_str, description in packets_list:
        container = document.createElement("div")
        container.style.marginBottom = "6px"
        container.style.fontSize = "0.85rem"
        container.style.display = "flex"
        container.style.justifyContent = "space-between"
        container.style.alignItems = "center"
        container.style.padding = "6px 8px"
        container.style.background = "#f9fafb"
        container.style.borderRadius = "4px"
        container.style.borderLeft = "3px solid #3b82f6"

        opcode_span = document.createElement("span")
        opcode_span.innerText = opcode_str
        opcode_span.style.fontFamily = "Courier New, monospace"
        opcode_span.style.fontWeight = "600"
        opcode_span.style.color = "#0b1220"

        desc_span = document.createElement("span")
        desc_span.innerText = description
        desc_span.style.color = "#6b7280"
        desc_span.style.fontSize = "0.8rem"
        desc_span.style.marginLeft = "8px"

        container.appendChild(opcode_span)
        container.appendChild(desc_span)
        stream_div.appendChild(container)

    stream_div.scrollTop = 0


# Template Program Generators
def get_template_program_commands(template_name):
    """Get RCX command sequence for a template (for program download)."""
    from esp32_driver import ProgramBuilder

    if template_name == "beep_test":
        prog = ProgramBuilder("beep_test")
        prog.beep()
        return prog.get_commands()

    elif template_name == "move_forward":
        prog = ProgramBuilder("move_forward")
        prog.set_power(0, 7).set_power(1, 7)
        prog.motor_on(0, 0).motor_on(1, 0)
        prog.motor_off(0).motor_off(1).motor_off(2)
        prog.beep()
        return prog.get_commands()

    elif template_name == "drive_pattern":
        prog = ProgramBuilder("drive_pattern")
        # Forward
        prog.set_power(0, 7).set_power(1, 7)
        prog.motor_on(0, 0).motor_on(1, 0)
        # Turn left
        prog.set_power(0, 7).set_power(1, 7)
        prog.motor_on(0, 0).motor_on(1, 1)
        # Forward
        prog.set_power(0, 7).set_power(1, 7)
        prog.motor_on(0, 0).motor_on(1, 0)
        # Stop
        prog.motor_off(0).motor_off(1).motor_off(2)
        prog.beep()
        return prog.get_commands()

    elif template_name == "motor_test":
        prog = ProgramBuilder("motor_test")
        prog.set_power(0, 5)
        prog.motor_on(0, 0)
        prog.motor_off(0)
        prog.set_power(1, 5)
        prog.motor_on(1, 0)
        prog.motor_off(1)
        prog.beep()
        return prog.get_commands()

    elif template_name == "spin_turn":
        prog = ProgramBuilder("spin_turn")
        prog.set_power(0, 5).set_power(1, 5)
        prog.motor_on(0, 0).motor_on(1, 1)  # spin left
        prog.set_power(0, 5).set_power(1, 5)
        prog.motor_on(0, 1).motor_on(1, 0)  # spin right
        prog.motor_off(0).motor_off(1).motor_off(2)
        prog.beep()
        return prog.get_commands()

    elif template_name == "square_pattern":
        prog = ProgramBuilder("square_pattern")
        prog.set_power(0, 5).set_power(1, 5)
        for i in range(4):
            prog.motor_on(0, 0).motor_on(1, 0)  # forward
            prog.motor_on(0, 1).motor_on(1, 0)  # turn right
        prog.motor_off(0).motor_off(1).motor_off(2)
        prog.beep(sound=3)
        return prog.get_commands()

    elif template_name == "acceleration":
        prog = ProgramBuilder("acceleration")
        for speed in [2, 3, 4, 5, 6, 7]:
            prog.set_power(0, speed).set_power(1, speed)
            prog.motor_on(0, 0).motor_on(1, 0)
            prog.motor_off(0).motor_off(1)
        prog.beep()
        return prog.get_commands()

    return []
    """Display expected packets for a template in the packet stream."""
    stream_div = document.querySelector("#packet-stream")
    if not stream_div:
        return

    packets_list = get_template_packets(template_name)
    if not packets_list:
        stream_div.innerHTML = f"<div style='color: #666; font-size: 0.9rem;'>Template '{template_name}' not found</div>"
        return

    stream_div.innerHTML = ""  # Clear

    for opcode_str, description in packets_list:
        container = document.createElement("div")
        container.style.marginBottom = "6px"
        container.style.fontSize = "0.85rem"
        container.style.display = "flex"
        container.style.justifyContent = "space-between"
        container.style.alignItems = "center"
        container.style.padding = "6px 8px"
        container.style.background = "#f9fafb"
        container.style.borderRadius = "4px"
        container.style.borderLeft = "3px solid #3b82f6"

        opcode_span = document.createElement("span")
        opcode_span.innerText = opcode_str
        opcode_span.style.fontFamily = "Courier New, monospace"
        opcode_span.style.fontWeight = "600"
        opcode_span.style.color = "#0b1220"

        desc_span = document.createElement("span")
        desc_span.innerText = description
        desc_span.style.color = "#6b7280"
        desc_span.style.fontSize = "0.8rem"
        desc_span.style.marginLeft = "8px"

        container.appendChild(opcode_span)
        container.appendChild(desc_span)
        stream_div.appendChild(container)

    stream_div.scrollTop = 0
