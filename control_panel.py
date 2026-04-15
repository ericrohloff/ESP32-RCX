import asyncio
from pyscript import when, document, window
from pyscript.js_modules.micro_repl import default as Board
import json
import main as core


class SerialBoard:
    def __init__(self):
        self.board = None
        self.terminal = None
        self.connected = False

    def is_connected(self):
        return self.connected and self.board is not None


serial_board = SerialBoard()


def log_to_ui(message):
    core.log_to_ui(message)


@when("click", "#connect-btn")
async def connect_serial(event):
    global serial_board
    if serial_board.is_connected():
        try:
            await serial_board.board.disconnect()
            serial_board.board = None
            serial_board.terminal = None
            serial_board.connected = False
            document.querySelector(
                "#status-bar").innerText = "Status: Disconnected"
            document.querySelector("#status-bar").style.color = "#e74c3c"
            log_to_ui("Serial Port Closed")
            return
        except Exception as e:
            log_to_ui(f"Disconnect Error: {e}")

    try:
        if serial_board.board is None:
            serial_board.board = Board({
                "baudRate": 115200,
                "dataType": "string",
                "onconnect": on_board_connect,
                "ondisconnect": on_board_disconnect,
                "dataBufferSize": 4096,
                "fontSize": "14",
                "fontFamily": "Courier New",
                "theme": {"background": "#000", "foreground": "#0f0"},
            })

        port_name = await serial_board.board.connect("repl-terminal", False)
        if port_name:
            serial_board.terminal = serial_board.board.terminal
            serial_board.connected = True
            document.querySelector(
                "#status-bar").innerText = f"Status: Connected to {port_name} @ 115200"
            document.querySelector("#status-bar").style.color = "#2ecc71"
            log_to_ui(f"Serial Port Opened: {port_name}")
        else:
            log_to_ui("Connection cancelled by user")
            serial_board.board = None
    except Exception as e:
        log_to_ui(f"Connection Error: {e}")
        serial_board.board = None
        serial_board.connected = False


def on_board_connect():
    log_to_ui("Board connected and ready")


async def on_board_disconnect():
    global serial_board
    serial_board.board = None
    serial_board.terminal = None
    serial_board.connected = False
    document.querySelector("#status-bar").innerText = "Status: Disconnected"
    document.querySelector("#status-bar").style.color = "#e74c3c"
    log_to_ui("Board disconnected")


async def send_to_esp32(data_bytes):
    if not serial_board.is_connected():
        log_to_ui("Error: Serial port is not connected.")
        return False
    try:
        byte_str = ""
        for byte in data_bytes:
            byte_str += chr(byte)
        await serial_board.board.write(byte_str)
        log_to_ui(f"✓ Sent {len(data_bytes)} bytes")
        return True
    except Exception as e:
        log_to_ui(f"Write Error: {e}")
        return False


@when("click", ".btn-test:nth-of-type(1)")
async def on_ping(event):
    pkt = core.build_ping_packet()
    await send_to_esp32(pkt)


@when("click", ".btn-test:nth-of-type(2)")
async def on_beep(event):
    pkt = core.build_beep_packet()
    await send_to_esp32(pkt)


@when("click", ".btn-stop")
async def on_stop(event):
    pkt = core.build_stop_packet()
    await send_to_esp32(pkt)


# ── Templates ──────────────────────────────────────────────────────────────

TEMPLATES = {
    "beep_test": """\
from rcx_driver import rcx

# Quick beep — confirms IR is reaching the RCX
rcx.beep()
""",
    "move_forward": """\
from rcx_driver import rcx

# Drive forward 2 seconds at full speed, then stop
rcx.move(speed=7, duration=2.0)
rcx.beep()
""",
    "drive_pattern": """\
from rcx_driver import rcx

# Forward -> pivot left -> forward
rcx.move(speed=7, duration=2.0)
rcx.turn_left(duration=0.6)
rcx.move(speed=7, duration=2.0)
rcx.stop()
rcx.beep()
""",
    "motor_test": """\
from rcx_driver import rcx

# Test motors A and B individually
rcx.set_power(0, 5)
rcx.motor_on(0)
rcx.wait(1.5)
rcx.motor_off(0)

rcx.set_power(1, 5)
rcx.motor_on(1)
rcx.wait(1.5)
rcx.motor_off(1)

rcx.beep()
""",
    "spin_turn": """\
from rcx_driver import rcx

# Spin left then right
rcx.turn_left(speed=5, duration=1.0)
rcx.turn_right(speed=5, duration=1.0)
rcx.stop()
rcx.beep()
""",
}


@when("click", "#btn-load-template")
def on_load_template(event):
    sel = document.getElementById("template-select")
    key = sel.value if sel else ""
    if not key:
        log_to_ui("Select a template first.")
        return
    code = TEMPLATES.get(key)
    if not code:
        log_to_ui(f"Unknown template: {key}")
        return
    editor = document.getElementById("mpCode1")
    if editor:
        editor.code = code
        log_to_ui(f"Template loaded: {key}")
    else:
        log_to_ui("Editor not found.")


# File listing / load / flash handlers (moved from main)
list_code = """import os
result = os.listdir('/')
result
"""


@when("click", "#list-board-files-btn")
async def list_board_files(event):
    if not serial_board.is_connected():
        log_to_ui("Error: Not connected to ESP32")
        return
    log_to_ui("Fetching file list from ESP32...")
    try:
        files = await serial_board.board.eval(list_code, hidden=True)
        window.console.log('board.eval returned:', files)
        if files is None:
            log_to_ui('No file list returned from board (None)')
            return
        selector = document.querySelector("#file-selector")
        selector.innerHTML = '<option value="">-- Select a file --</option>'
        try:
            for f in files:
                log_to_ui(f"  📄 {f}")
                option = document.createElement('option')
                option.value = f
                option.text = f
                selector.appendChild(option)
        except Exception as e:
            window.console.error('Error iterating files:', e, files)
            log_to_ui(f'Error: returned file list is not iterable: {e}')
            return
    except Exception as e:
        log_to_ui(f"Error listing files: {e}")


@when("click", "#load-file-btn")
async def load_file(event):
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
        read_code = f"""with open('{filename}', 'r') as f:\n    content = f.read()\ncontent"""
        file_content = await serial_board.board.eval(read_code, hidden=True)
        if file_content:
            document.querySelector("#code-editor").value = file_content
            log_to_ui(f"✓ Loaded {filename} into editor")
        else:
            log_to_ui(f"File is empty or could not be read")
    except Exception as e:
        log_to_ui(f"Error loading file: {e}")


@when("click", "#flash-btn")
async def flash_code(event):
    if not serial_board.is_connected():
        log_to_ui("Connect ESP32 first!")
        return
    user_logic = document.querySelector("#code-editor").value
    try:
        import esp32_driver
        driver_code = esp32_driver.code
    except Exception as e:
        log_to_ui(f"Error: Could not import esp32_driver: {e}")
        return
    full_script = driver_code + "\n\n# --- User Logic ---\n" + user_logic
    log_to_ui("Flashing script to ESP32...")
    try:
        success = await serial_board.board.upload("main.py", full_script)
        if success:
            log_to_ui("✓ Script uploaded successfully to main.py")
            log_to_ui("Board will run this script on next reboot")
        else:
            log_to_ui("✗ Upload failed")
    except Exception as e:
        log_to_ui(f"Flash Error: {e}")
