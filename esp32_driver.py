# esp32_driver.py - This is the hidden code sent to the ESP32
import machine
import time

# 1. Setup 38kHz Carrier (Required for RCX to see IR)
ir_pwm = machine.PWM(machine.Pin(17))  # Adjust pin to your TX pin
ir_pwm.freq(38000)
ir_pwm.duty_u16(32768)  # 50% duty cycle

# 2. Setup UART for 2400 Baud Data
uart = machine.UART(1, baudrate=2400, tx=17)


class StandaloneRCX:
    def __init__(self):
        self.toggle = False
        # VM state for simple LASM-like scripts
        self.vars = {}
        self.timers = {}
        self.tasks = {}

    def _send(self, opcode, params=[]):
        tx_opcode = opcode | 0x08 if self.toggle else opcode
        self.toggle = not self.toggle

        # Build Packet
        packet = bytearray([0x55, 0xFF, 0x00, tx_opcode, tx_opcode ^ 0xFF])
        checksum = tx_opcode
        for p in params:
            packet.extend(bytearray([p, p ^ 0xFF]))
            checksum = (checksum + p) % 256
        packet.extend(bytearray([checksum, checksum ^ 0xFF]))

        uart.write(packet)
        time.sleep(0.1)

    def beep(self): self._send(0x51, [0x01])
    def motor_on(self, m): self._send(0x21, [0x80 | (1 << m)])
    def motor_off(self, m): self._send(0x21, [0x40 | (1 << m)])

    # High-level helper commands (mapping common LASM directives)
    def stop_all_tasks(self):
        """Send Stop All Tasks opcode"""
        self._send(0x50)

    def delete_task(self, tid):
        """Delete a stored task definition (no-op on RCX hardware)"""
        try:
            self.tasks.pop(int(tid), None)
        except Exception:
            pass

    def set_log_level(self, level):
        """Adjust logging verbosity for the interpreter (stored locally)."""
        try:
            self.vars['_logz'] = int(level)
        except Exception:
            self.vars['_logz'] = 0

    def tmrz(self, tindex):
        """Reset a timer index to zero (software timer)."""
        self.timers[int(tindex)] = 0

    def wait(self, a, b):
        """Simple wait: interpreted as seconds = b * 0.1 for LASM compatibility."""
        try:
            delay = float(b) * 0.1
        except Exception:
            delay = 0
        time.sleep(delay)

    def set_var(self, *args):
        """Store values in the VM 'vars' mapping. Usage: set idx, value [, ...]
        If called with multiple value pairs, it will write them accordingly.
        """
        if len(args) >= 2:
            try:
                idx = int(args[0])
                val = int(args[1])
                self.vars[idx] = val
            except Exception:
                pass

    def mulv(self, dst, src, mul):
        """Multiply var[src] by mul and store into var[dst]."""
        try:
            dst = int(dst); src = int(src); mul = int(mul)
            sval = int(self.vars.get(src, 0))
            self.vars[dst] = (sval * mul) & 0xFF
        except Exception:
            pass

    def out_port(self, port, value):
        """Drive outputs based on a numeric value. Each bit turns a motor on/off.
        This is a heuristic mapping: bit 0 -> motor 0, bit 1 -> motor 1, bit 2 -> motor 2.
        """
        try:
            v = int(value)
        except Exception:
            v = 0
        for m in range(3):
            if v & (1 << m):
                self.motor_on(m)
            else:
                self.motor_off(m)

    def run_lasm_script(self, script_text):
        """Parse and execute a small subset of LASM-style commands.

        Supported commands (best-effort semantics):
        - stop            : send Stop All Tasks
        - delt            : delete task definition
        - logz N          : set local log level
        - task N ... endt : define a task block (stored and executed)
        - wait A,B        : wait; interpreted as B * 0.1 seconds
        - tmrz N          : reset software timer N
        - set ...         : store values into internal vars
        - mulv D,S,M      : vars[D] = vars[S] * M
        - out P,V         : set outputs (heuristic motor control)

        Notes: This is an interpreter that runs on the ESP32 and uses the
        `motor_on`, `motor_off`, `beep`, and `_send` primitives to control RCX-compatible
        hardware. It does not implement every LASM feature; it implements a
        practical subset needed to run simple motor-driving programs.
        """
        lines = [l.strip() for l in script_text.splitlines()]
        cur_task = None
        for raw in lines:
            if not raw:
                continue
            parts = [p.strip() for p in raw.replace(',', ' ').split()]
            if not parts:
                continue
            cmd = parts[0].lower()
            args = parts[1:]

            if cmd == 'task':
                # begin recording a task
                try:
                    cur_task = int(args[0]) if args else 0
                    self.tasks[cur_task] = []
                except Exception:
                    cur_task = None
                continue
            if cmd == 'endt':
                cur_task = None
                continue

            # If inside a task definition, store the raw line
            if cur_task is not None:
                self.tasks[cur_task].append(raw)
                continue

            # Top-level commands executed immediately
            if cmd == 'stop':
                self.stop_all_tasks()
            elif cmd == 'delt':
                self.delete_task(args[0] if args else 0)
            elif cmd == 'logz':
                self.set_log_level(args[0] if args else 0)
            elif cmd == 'wait':
                # wait A,B -> use B as duration units
                if len(args) >= 2:
                    self.wait(args[0], args[1])
                elif len(args) == 1:
                    self.wait(0, args[0])
            elif cmd == 'tmrz':
                if args:
                    self.tmrz(args[0])
            elif cmd == 'set':
                # set idx, value  (we only use first pair)
                if len(args) >= 2:
                    self.set_var(args[0], args[1])
            elif cmd == 'mulv':
                if len(args) >= 3:
                    self.mulv(args[0], args[1], args[2])
            elif cmd == 'out':
                if len(args) >= 2:
                    self.out_port(args[0], args[1])
            elif cmd == 'run':
                # run a previously-defined task: `run N`
                if args:
                    tid = int(args[0])
                    self._run_task(tid)
            elif cmd == 'beep':
                self.beep()
            # Unknown commands are ignored for now

    def _run_task(self, tid):
        """Execute a stored task sequentially."""
        seq = self.tasks.get(int(tid), [])
        for line in seq:
            parts = [p.strip() for p in line.replace(',', ' ').split()]
            if not parts:
                continue
            cmd = parts[0].lower()
            args = parts[1:]
            if cmd == 'wait':
                if len(args) >= 2:
                    self.wait(args[0], args[1])
                elif len(args) == 1:
                    self.wait(0, args[0])
            elif cmd == 'set':
                if len(args) >= 2:
                    self.set_var(args[0], args[1])
            elif cmd == 'mulv':
                if len(args) >= 3:
                    self.mulv(args[0], args[1], args[2])
            elif cmd == 'out':
                if len(args) >= 2:
                    self.out_port(args[0], args[1])
            elif cmd == 'beep':
                self.beep()
            elif cmd == 'tmrz':
                if args:
                    self.tmrz(args[0])
            # other commands treated as no-op in task context


rcx = StandaloneRCX()
