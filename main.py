import asyncio
from js import navigator, Uint8Array, TextEncoder, document
from pyscript import display, when

port = None
toggle_bit = False


def log_to_ui(message):
    log_div = document.querySelector("#console-log")
    new_entry = document.createElement("div")
    new_entry.style.borderBottom = "1px solid #222"
    new_entry.style.padding = "2px"
    new_entry.innerText = f"> {message}"
    log_div.appendChild(new_entry)
    log_div.scrollTop = log_div.scrollHeight


def visualize_packet(packet_list):
    """
    packet_list: A list of integers representing the packet
    Renders HTML spans with classes for the visualizer
    """
    stream_div = document.querySelector("#packet-stream")
    container = document.createElement("div")
    container.style.marginBottom = "8px"

    # helper to create byte span
    def create_span(val, category, is_comp=False):
        span = document.createElement("span")
        span.classList.add("packet-byte")
        span.classList.add(category)
        if is_comp:
            span.classList.add("byte-comp")
        span.innerText = f"{val:02X}"
        return span

    # Preamble: 0, 1, 2
    for i in range(3):
        container.appendChild(create_span(packet_list[i], "byte-preamble"))

    # Opcode and Complement: 3, 4
    container.appendChild(create_span(packet_list[3], "byte-opcode"))
    container.appendChild(create_span(packet_list[4], "byte-opcode", True))

    # Parameters and Complements: variable length
    # Checksum is always the last two bytes
    param_end = len(packet_list) - 2
    for i in range(5, param_end):
        container.appendChild(create_span(
            packet_list[i], "byte-param", i % 2 == 0))

    # Checksum and Complement: last two
    container.appendChild(create_span(packet_list[-2], "byte-checksum"))
    container.appendChild(create_span(packet_list[-1], "byte-checksum", True))

    # Add to stream and scroll to bottom
    stream_div.appendChild(container)
    stream_div.scrollTop = stream_div.scrollHeight


def encode_rcx_packet(opcode, params=[]):
    global toggle_bit
    tx_opcode = opcode | 0x08 if toggle_bit else opcode
    toggle_bit = not toggle_bit

    packet = [0x55, 0xFF, 0x00]
    packet.extend([tx_opcode, tx_opcode ^ 0xFF])

    checksum = tx_opcode
    for p in params:
        packet.extend([p, p ^ 0xFF])
        checksum = (checksum + p) % 256

    packet.extend([checksum, checksum ^ 0xFF])

    # --- NEW: Update the UI ---
    visualize_packet(packet)
    # --------------------------

    return Uint8Array.new(packet)


async def send_to_esp32(data_bytes):
    if not port:
        log_to_ui("Error: Not connected to ESP32")
        return
    writer = port.writable.getWriter()
    await writer.write(data_bytes)
    writer.releaseLock()


@when("click", "#connect-btn")
async def connect_serial(event):
    global port
    try:
        port = await navigator.serial.requestPort()
        await port.open({"baudRate": 115200})
        document.querySelector(
            "#status-bar").innerText = "Status: Connected to ESP32"
        document.querySelector("#status-bar").style.color = "#2ecc71"
        log_to_ui("Serial Port Opened at 115200 baud")
    except Exception as e:
        log_to_ui(f"Connection Error: {str(e)}")

# --- Live Diagnostic Handlers ---


@when("click", ".btn-test:nth-of-type(1)")  # Ping
async def live_ping(event):
    log_to_ui("Live: Sending Ping (0x10)")
    await send_to_esp32(encode_rcx_packet(0x10))


@when("click", ".btn-test:nth-of-type(2)")  # Beep
async def live_beep(event):
    log_to_ui("Live: Sending Beep (0x51, 0x01)")
    await send_to_esp32(encode_rcx_packet(0x51, [0x01]))


@when("click", ".btn-stop")  # Stop
async def live_stop(event):
    log_to_ui("Live: Sending Stop All (0x50)")
    await send_to_esp32(encode_rcx_packet(0x50))

# --- Flashing Logic ---


async def send_repl_text(text):
    encoder = TextEncoder.new()
    # Adding \r\n simulates hitting Enter in the MicroPython terminal
    await send_to_esp32(encoder.encode(text + "\r\n"))
    await asyncio.sleep(0.05)  # Give ESP32 time to process string


@when("click", "#flash-btn")
async def flash_code(event):
    global port
    if port is None:
        log_to_ui("Connect ESP32 first!")
        return

    # 1. Get the user's logic from the editor
    user_logic = document.querySelector("#code-editor").value

    # 2. Fetch the driver code
    # (Assuming esp32_driver.py is in your pyscript.json files list)
    try:
        with open("esp32_driver.py", "r") as f:
            driver_code = f.read()
    except:
        log_to_ui("Error: Could not find esp32_driver.py")
        return

    # 3. Combine them
    full_script = driver_code + "\n\n# --- User Logic ---\n" + user_logic

    log_to_ui("Flashing full standalone script...")


@when("click", "button[py-click='clear_visualizer']")
def clear_visualizer(event):
    document.querySelector("#packet-stream").innerHTML = ""
    log_to_ui("Packet visualizer cleared.")


@when("click", "button[py-click='clear_console']")
def clear_console(event):
    document.querySelector("#console-log").innerHTML = ""
    # We don't log "cleared" here because it would immediately fill it back up!


@when("click", "#clear-console-btn")
def clear_console(event):
    # Simply empty the container
    document.querySelector("#console-log").innerHTML = ""
    # Optional: Log a fresh start message
    log_to_ui("Console cleared.")
