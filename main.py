import asyncio
from js import Uint8Array, document
import json
import RS232
import control_panel


# Core utilities for packet creation and visualization.
toggle_bit = False
myRS232 = RS232.CEEO_RS232(divName='all_things_rs232',
                           suffix='1', myCSS=False, default_code='sd')


def log_to_ui(message):
    log_div = document.querySelector("#console-log")
    new_entry = document.createElement("div")
    new_entry.style.borderBottom = "1px solid #222"
    new_entry.style.padding = "2px"
    new_entry.innerText = f"> {message}"


def visualize_packet(packet_list):
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
