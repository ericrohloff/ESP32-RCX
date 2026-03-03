import asyncio
from js import navigator, Uint8Array, TextEncoder, document, window
from pyscript import display, when
from pyscript.js_modules.micro_repl import default as Board
import json

# Check for serial support
try:
    navigator.serial.requestPort
except:
    window.alert('You must use Chrome to communicate over Serial')

class SerialBoard:
    def __init__(self):
        self.board = None
        self.terminal = None
        self.connected = False
    
    def is_connected(self):
        return self.connected and self.board is not None

serial_board = SerialBoard()
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
    global serial_board
    # Check if board is connected
    if not serial_board.is_connected():
        log_to_ui("Error: Serial port is not connected.")
        return

    try:
        # Convert Uint8Array to bytes string for micro_repl
        byte_str = ""
        for byte in data_bytes:
            byte_str += chr(byte)
        
        await serial_board.board.write(byte_str)
        log_to_ui(f"✓ Sent {len(data_bytes)} bytes")
    except Exception as e:
        log_to_ui(f"Write Error: {str(e)}")


@when("click", "#connect-btn")
async def connect_serial(event):
    global serial_board
    
    # If already connected, disconnect
    if serial_board.is_connected():
        try:
            await serial_board.board.disconnect()
            serial_board.board = None
            serial_board.terminal = None
            serial_board.connected = False
            document.querySelector("#status-bar").innerText = "Status: Disconnected"
            document.querySelector("#status-bar").style.color = "#e74c3c"
            log_to_ui("Serial Port Closed")
            return
        except Exception as e:
            log_to_ui(f"Disconnect Error: {str(e)}")
    
    try:
        # Initialize Board on first connection
        if serial_board.board is None:
            serial_board.board = Board({
                "baudRate": 115200,
                "dataType": "string",
                "onconnect": on_board_connect,
                "ondisconnect": on_board_disconnect,
                "dataBufferSize": 4096,
                "fontSize": "14",
                "fontFamily": "Courier New",
                "theme": {
                    "background": "#000",
                    "foreground": "#0f0",
                },
            })
        
        # Connect to selected port - this renders the terminal into the div
        port_name = await serial_board.board.connect("repl-terminal", False)  # False = don't reset
        
        if port_name:
            # Store terminal reference after connection
            serial_board.terminal = serial_board.board.terminal
            serial_board.connected = True
            document.querySelector("#status-bar").innerText = f"Status: Connected to {port_name} @ 115200"
            document.querySelector("#status-bar").style.color = "#2ecc71"
            log_to_ui(f"Serial Port Opened: {port_name}")
        else:
            log_to_ui("Connection cancelled by user")
            serial_board.board = None
            
    except Exception as e:
        log_to_ui(f"Connection Error: {str(e)}")
        serial_board.board = None
        serial_board.connected = False


def on_board_connect():
    """Callback when board connects"""
    log_to_ui("Board connected and ready")


async def on_board_disconnect():
    """Callback when board disconnects"""
    global serial_board
    serial_board.board = None
    serial_board.terminal = None
    serial_board.connected = False
    document.querySelector("#status-bar").innerText = "Status: Disconnected"
    document.querySelector("#status-bar").style.color = "#e74c3c"
    log_to_ui("Board disconnected")

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


@when("click", "#list-board-files-btn")
async def list_board_files(event):
    global serial_board
    if not serial_board.is_connected():
        log_to_ui("Error: Not connected to ESP32")
        return
    
    log_to_ui("Fetching file list from ESP32...")
    
    try:
        # Run Python code on board to get file list
        list_code = """import os
result = os.listdir('/')
result"""
        
        files = await serial_board.board.eval(list_code, hidden=True)
        log_to_ui(f"Found {len(files)} files on ESP32")
        
        # Clear and populate the file selector
        selector = document.querySelector("#file-selector")
        selector.innerHTML = '<option value="">-- Select a file --</option>'
        
        if files and isinstance(files, list):
            for f in files:
                log_to_ui(f"  📄 {f}")
                option = document.createElement('option')
                option.value = f
                option.text = f
                selector.appendChild(option)
        
    except Exception as e:
        log_to_ui(f"Error listing files: {str(e)}")


@when("click", "#load-file-btn")
async def load_file_to_editor(event):
    global serial_board
    if not serial_board.is_connected():
        log_to_ui("Error: Not connected to ESP32")
        return
    
    selector = document.querySelector("#file-selector")
    filename = selector.value
    
    if not filename:
        log_to_ui("Please select a file to load")
        return
    
    log_to_ui(f"Loading {filename} from ESP32...")
    
    try:
        # Read file from board
        read_code = f"""with open('{filename}', 'r') as f:
    content = f.read()
content"""
        
        file_content = await serial_board.board.eval(read_code, hidden=True)
        
        if file_content:
            document.querySelector("#code-editor").value = file_content
            log_to_ui(f"✓ Loaded {filename} into editor")
        else:
            log_to_ui(f"File is empty or could not be read")
            
    except Exception as e:
        log_to_ui(f"Error loading file: {str(e)}")

# --- Flashing Logic ---


async def send_repl_text(text):
    encoder = TextEncoder.new()
    # Adding \r\n simulates hitting Enter in the MicroPython terminal
    await send_to_esp32(encoder.encode(text + "\r\n"))
    await asyncio.sleep(0.05)  # Give ESP32 time to process string


@when("click", "#flash-btn")
async def flash_code(event):
    global serial_board
    if not serial_board.is_connected():
        log_to_ui("Connect ESP32 first!")
        return

    # 1. Get the user's logic from the editor
    user_logic = document.querySelector("#code-editor").value

    # 2. Fetch the driver code
    try:
        with open("esp32_driver.py", "r") as f:
            driver_code = f.read()
    except:
        log_to_ui("Error: Could not find esp32_driver.py")
        return

    # 3. Combine them
    full_script = driver_code + "\n\n# --- User Logic ---\n" + user_logic

    log_to_ui("Flashing script to ESP32...")
    
    try:
        # Upload as main.py - this will auto-run on boot
        success = await serial_board.board.upload("main.py", full_script)
        if success:
            log_to_ui("✓ Script uploaded successfully to main.py")
            log_to_ui("Board will run this script on next reboot")
        else:
            log_to_ui("✗ Upload failed")
    except Exception as e:
        log_to_ui(f"Flash Error: {str(e)}")


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
