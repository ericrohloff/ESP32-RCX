"""
usb_tower_driver.py

Python wrapper around window.usbTower (defined in index.html).

All WebUSB calls live in JavaScript on the main thread so there is no
worker-proxy chain to expire. Python makes exactly one JS call per
operation (connect, sendPacket, disconnect).

User code runs in the browser and uses async/await syntax:

    await rcx.move(speed=7, duration=2.0)
    await rcx.beep()
    await rcx.stop()
"""

import asyncio
from pyscript import window


class USBTower:

    @property
    def connected(self):
        return bool(window.usbTower.connected)

    async def connect(self):
        return await window.usbTower.connect()

    async def disconnect(self):
        await window.usbTower.disconnect()

    def _build_packet(self, opcode, params=None):
        if params is None:
            params = []
        tx_op = opcode | (0x08 if self._toggle else 0x00)
        self._toggle = not self._toggle
        pkt = [0x55, 0xFF, 0x00, tx_op, tx_op ^ 0xFF]
        ck = tx_op
        for p in params:
            pkt.append(p)
            pkt.append(p ^ 0xFF)
            ck = (ck + p) & 0xFF
        pkt.append(ck)
        pkt.append(ck ^ 0xFF)
        return pkt

    def __init__(self):
        self._toggle = False

    async def send_raw(self, packet_bytes):
        await window.usbTower.sendPacket(packet_bytes)

    async def _send(self, opcode, params=None):
        pkt = self._build_packet(opcode, params)
        await self.send_raw(pkt)
        await asyncio.sleep(0.1)

    # ── RCX direct commands ────────────────────────────────────────────────

    async def ping(self):
        await self._send(0x10)

    async def beep(self, sound=2):
        await self._send(0x51, [sound])

    async def motor_on(self, motor_id, direction=0):
        port = 1 << motor_id
        flag = 0x80 if direction == 0 else 0x40
        await self._send(0x21, [flag | port])

    async def motor_off(self, motor_id):
        port = 1 << motor_id
        await self._send(0x21, [0x40 | port])

    async def motor_brake(self, motor_id):
        port = 1 << motor_id
        await self._send(0x21, [0xC0 | port])

    async def set_power(self, motor_id, power):
        if 0 <= motor_id <= 2 and 0 <= power <= 7:
            await self._send(0x13, [motor_id, power])

    # ── High-level robot commands ──────────────────────────────────────────

    async def stop(self):
        await self.motor_off(0)
        await self.motor_off(1)
        await self.motor_off(2)

    async def brake(self):
        await self.motor_brake(0)
        await self.motor_brake(1)
        await self.motor_brake(2)

    async def move(self, speed=7, duration=None):
        await self.set_power(0, speed)
        await self.set_power(1, speed)
        await self.motor_on(0, direction=0)
        await self.motor_on(1, direction=0)
        if duration is not None:
            await asyncio.sleep(duration)
            await self.stop()

    async def backward(self, speed=7, duration=None):
        await self.set_power(0, speed)
        await self.set_power(1, speed)
        await self.motor_on(0, direction=1)
        await self.motor_on(1, direction=1)
        if duration is not None:
            await asyncio.sleep(duration)
            await self.stop()

    async def turn_left(self, speed=7, duration=None):
        await self.set_power(0, speed)
        await self.set_power(1, speed)
        await self.motor_on(0, direction=0)
        await self.motor_on(1, direction=1)
        if duration is not None:
            await asyncio.sleep(duration)
            await self.stop()

    async def turn_right(self, speed=7, duration=None):
        await self.set_power(0, speed)
        await self.set_power(1, speed)
        await self.motor_on(0, direction=1)
        await self.motor_on(1, direction=0)
        if duration is not None:
            await asyncio.sleep(duration)
            await self.stop()

    async def spin_left(self, speed=7, duration=None):
        await self.turn_left(speed=speed, duration=duration)

    async def spin_right(self, speed=7, duration=None):
        await self.turn_right(speed=speed, duration=duration)

    async def wait(self, seconds):
        await asyncio.sleep(seconds)

    async def set_all_power(self, power):
        await self.set_power(0, power)
        await self.set_power(1, power)
        await self.set_power(2, power)


rcx = USBTower()
