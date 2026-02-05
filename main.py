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


def encode_rcx_packet(opcode, params=[]):
    """
    Implements the RCX Serial Protocol:
    Preamble + Opcode/Comp + Params/Comp + Checksum/Comp
    """
    global toggle_bit

    # Apply toggle bit (bit 3 / 0x08) to differentiate repeated commands
    tx_opcode = opcode | 0x08 if toggle_bit else opcode
    toggle_bit = not toggle_bit

    # 1. Start with Preamble
    packet = [0x55, 0xFF, 0x00]

    # 2. Add Opcode and its Complement
    packet.append(tx_opcode)
    packet.append(tx_opcode ^ 0xFF)

    # 3. Add Parameters and their Complements
    checksum = tx_opcode
    for p in params:
        packet.append(p)
        packet.append(p ^ 0xFF)
        checksum = (checksum + p) % 256

    # 4. Add Checksum and its Complement
    packet.append(checksum)
    packet.append(checksum ^ 0xFF)

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
