import asyncio
from pyscript import when, document, window
from pyscript.js_modules.micro_repl import default as Board
import json
import main as core
import usb_tower_driver


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


@when("click", ".btn-clear")
def on_clear_visualizer(event):
    """Clear the packet stream visualizer."""
    stream_div = document.querySelector("#packet-stream")
    if stream_div:
        stream_div.innerHTML = ""
        log_to_ui("Packet visualizer cleared")


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
rcx.spin_left(speed=5, duration=1.0)
rcx.spin_right(speed=5, duration=1.0)
rcx.stop()
rcx.beep()
""",
    "square_pattern": """\
from rcx_driver import rcx

# Drive in a square pattern
for i in range(4):
    rcx.move(speed=5, duration=1.5)
    rcx.turn_right(speed=4, duration=0.5)

rcx.stop()
rcx.beep(sound=3)
""",
    "acceleration": """\
from rcx_driver import rcx

# Test speeds 2-7
for speed in [2, 3, 4, 5, 6, 7]:
    rcx.move(speed=speed, duration=0.8)
    rcx.wait(0.3)

rcx.stop()
rcx.beep(sound=2)
""",
}


@when("click", "#btn-load-template")
def on_load_template(event):
    """Load template code into the editor without flashing."""
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
        log_to_ui(f"✓ Template loaded: {key}")
        log_to_ui("→ Review code in editor, then connect to ESP32 and flash when ready")
        # Show expected packets for this template
        core.display_template_packets(key)
    else:
        log_to_ui("Error: Editor not found")


@when("change", "#template-select")
def on_template_selected(event):
    """Show packet preview when template is selected."""
    sel = document.getElementById("template-select")
    key = sel.value if sel else ""
    if key:
        core.display_template_packets(key)
        log_to_ui(f"Showing packets for: {key}")


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

    editor = document.getElementById("mpCode1")
    if not editor:
        log_to_ui("Error: Editor not found")
        return

    code = editor.code
    if not code or not code.strip():
        log_to_ui("Editor is empty — load a template first")
        return

    try:
        log_to_ui("Running on ESP32...")
        await serial_board.board.eval(code, hidden=False)
        log_to_ui("✓ Done")
    except Exception as e:
        log_to_ui(f"Error: {e}")


# ── USB Tower ───────────────────────────────────────────────────────────────

_tower = usb_tower_driver.rcx

TOWER_TEMPLATES = {
    "tower_beep": """\
# USB Tower: Quick beep — confirms IR is reaching the RCX
await rcx.beep()
""",
    "tower_move_forward": """\
# USB Tower: Drive forward 2 seconds at full speed, then stop
await rcx.move(speed=7, duration=2.0)
await rcx.beep()
""",
    "tower_drive_pattern": """\
# USB Tower: Forward -> pivot left -> forward
await rcx.move(speed=7, duration=2.0)
await rcx.turn_left(speed=5, duration=0.6)
await rcx.move(speed=7, duration=2.0)
await rcx.stop()
await rcx.beep()
""",
    "tower_motor_test": """\
# USB Tower: Test motors A and B individually
await rcx.set_power(0, 5)
await rcx.motor_on(0)
await rcx.wait(1.5)
await rcx.motor_off(0)

await rcx.set_power(1, 5)
await rcx.motor_on(1)
await rcx.wait(1.5)
await rcx.motor_off(1)

await rcx.beep()
""",
    "tower_spin_turn": """\
# USB Tower: Spin left then right
await rcx.spin_left(speed=5, duration=1.0)
await rcx.spin_right(speed=5, duration=1.0)
await rcx.stop()
await rcx.beep()
""",
    "tower_square_pattern": """\
# USB Tower: Drive in a square pattern
for i in range(4):
    await rcx.move(speed=5, duration=1.5)
    await rcx.turn_right(speed=4, duration=0.5)

await rcx.stop()
await rcx.beep(sound=3)
""",
    "tower_acceleration": """\
# USB Tower: Ramp speed from 2 to 7
for speed in [2, 3, 4, 5, 6, 7]:
    await rcx.move(speed=speed, duration=0.8)
    await rcx.wait(0.3)

await rcx.stop()
await rcx.beep()
""",
}


def usb_log(message):
    log_div = document.querySelector("#usb-log")
    if not log_div:
        return
    entry = document.createElement("div")
    entry.innerText = f"> {message}"
    log_div.appendChild(entry)
    log_div.scrollTop = log_div.scrollHeight


def _update_usb_status(connected):
    status = document.querySelector("#usb-status")
    btn = document.querySelector("#usb-connect-btn")
    if status:
        status.innerText = "Connected" if connected else "Not Connected"
        status.style.color = "#10b981" if connected else "#e74c3c"
    if btn:
        btn.innerText = "Disconnect" if connected else "Connect Tower"


@when("click", "#usb-connect-btn")
async def usb_connect(_event):
    if _tower.connected:
        await _tower.disconnect()
        _update_usb_status(False)
        usb_log("Tower disconnected")
        return
    try:
        usb_log("Opening USB device picker...")
        info = await _tower.connect()
        _update_usb_status(True)
        usb_log(f"USB Tower connected ({info})")
    except Exception as e:
        usb_log(f"Connection error: {e}")
        _update_usb_status(False)


@when("click", "#usb-ping-btn")
async def usb_ping(event):
    if not _tower.connected:
        usb_log("Not connected")
        return
    try:
        await _tower.ping()
        usb_log("Ping sent")
    except Exception as e:
        usb_log(f"Error: {e}")


@when("click", "#usb-beep-btn")
async def usb_beep(event):
    if not _tower.connected:
        usb_log("Not connected")
        return
    try:
        await _tower.beep()
        usb_log("Beep sent")
    except Exception as e:
        usb_log(f"Error: {e}")


@when("click", "#usb-stop-btn")
async def usb_stop_all(event):
    if not _tower.connected:
        usb_log("Not connected")
        return
    try:
        await _tower.stop()
        usb_log("Stop sent")
    except Exception as e:
        usb_log(f"Error: {e}")


@when("click", "#btn-load-tower-template")
def load_tower_template(event):
    sel = document.getElementById("tower-template-select")
    key = sel.value if sel else ""
    if not key:
        usb_log("Select a template first.")
        return
    code = TOWER_TEMPLATES.get(key)
    if not code:
        usb_log(f"Unknown template: {key}")
        return
    editor = document.getElementById("mpCode1")
    if editor:
        editor.code = code
        usb_log(f"✓ Template loaded: {key}")
    else:
        usb_log("Error: Editor not found")


@when("click", "#usb-run-btn")
async def usb_run(event):
    if not _tower.connected:
        usb_log("Connect USB Tower first!")
        return

    editor = document.getElementById("mpCode1")
    if not editor:
        usb_log("Error: Editor not found")
        return

    code = editor.code
    if not code or not code.strip():
        usb_log("Editor is empty — load a template first")
        return

    # Wrap user code in an async function so top-level `await` works.
    # `pass` ensures the body is valid even if code is comment-only.
    indented = "\n".join("    " + line for line in code.split("\n"))
    wrapper = f"async def _user_main(rcx, asyncio):\n    pass\n{indented}\n"

    try:
        namespace = {}
        exec(compile(wrapper, "<user_code>", "exec"), namespace)
        usb_log("Running...")
        await namespace["_user_main"](_tower, asyncio)
        usb_log("✓ Done")
    except Exception as e:
        usb_log(f"Error: {e}")
