# MicroPython Human Interface Device library
# Copyright (C) 2021 H. Groefsema
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


# Implements a BLE HID keyboard
import uasyncio as asyncio
from machine import SoftSPI, Pin
from hid_services import Keyboard

class Device:
    def __init__(self, name="Keyboard"):
        # Define state
        self.keys = []
        self.updated = False
        self.active = True

        # Define buttons
        self.pin_w = Pin(5, Pin.IN)
        self.pin_s = Pin(23, Pin.IN)
        self.pin_d = Pin(19, Pin.IN)
        self.pin_a = Pin(18, Pin.IN)

        # Create our device
        self.keyboard = Keyboard(name)
        # Set a callback function to catch changes of device state
        self.keyboard.set_state_change_callback(self.keyboard_state_callback)

    # Function that catches device status events
    def keyboard_state_callback(self):
        if self.keyboard.get_state() is Keyboard.DEVICE_IDLE:
            return
        elif self.keyboard.get_state() is Keyboard.DEVICE_ADVERTISING:
            return
        elif self.keyboard.get_state() is Keyboard.DEVICE_CONNECTED:
            return
        else:
            return

    def keyboard_event_callback(self, bytes):
        print("Keyboard state callback with bytes: ", bytes)

    def advertise(self):
        self.keyboard.start_advertising()

    def stop_advertise(self):
        self.keyboard.stop_advertising()

    async def advertise_for(self, seconds=30):
        self.advertise()

        while seconds > 0 and self.keyboard.get_state() is Keyboard.DEVICE_ADVERTISING:
            await asyncio.sleep(1)
            seconds -= 1

        if self.keyboard.get_state() is Keyboard.DEVICE_ADVERTISING:
            self.stop_advertise()

    # Input loop
    async def gather_input(self):
        while self.active:
            prevkeys = self.keys
            self.keys.clear()

            # Read pin values and update variables
            if self.pin_w.value():
                self.keys.append(0x1A)  # W
            else:
                self.keys.append(0x00)

            if self.pin_a.value():
                self.keys.append(0x04)  # A
            else:
                self.keys.append(0x00)

            if self.pin_s.value():
                self.keys.append(0x16)  # S
            else:
                self.keys.append(0x00)

            if self.pin_d.value():
                self.keys.append(0x07)  # D
            else:
                self.keys.append(0x00)

            self.updated = self.updated or not (prevkeys == self.keys)  # If updated is still True, we haven't notified yet
            await asyncio.sleep_ms(50)

    # Bluetooth device loop
    async def notify(self):
        while self.active:
            # If the variables changed do something depending on the device state
            if self.updated:
                # If connected, set keys and notify
                # If idle, start advertising for 30s or until connected
                if self.keyboard.get_state() is Keyboard.DEVICE_CONNECTED:
                    self.keyboard.set_keys(self.keys[0], self.keys[1], self.keys[2], self.keys[3])
                    self.keyboard.notify_hid_report()
                elif self.keyboard.get_state() is Keyboard.DEVICE_IDLE:
                    await self.advertise_for(30)
                self.updated = False

            if self.keyboard.get_state() is Keyboard.DEVICE_CONNECTED:
                await asyncio.sleep_ms(50)
            else:
                await asyncio.sleep(2)

    async def co_start(self):
        # Start our device
        if self.keyboard.get_state() is Keyboard.DEVICE_STOPPED:
            self.keyboard.start()
            self.active = True
            await asyncio.gather(self.advertise_for(30), self.gather_input(), self.notify())

    async def co_stop(self):
        self.active = False
        self.keyboard.stop()

    def start(self):
        asyncio.run(self.co_start())

    def stop(self):
        asyncio.run(self.co_stop())

    # Used with test
    def send_char(self, char):
        if char == " ":
            mod = 0
            code = 0x2C
        elif ord("a") <= ord(char) <= ord("z"):
            mod = 0
            code = 0x04 + ord(char) - ord("a")
        elif ord("A") <= ord(char) <= ord("Z"):
            mod = 1
            code = 0x04 + ord(char) - ord("A")
        else:
            assert 0

        self.keyboard.set_keys(code)
        self.keyboard.set_modifiers(left_shift=mod)
        self.keyboard.notify_hid_report()
        asyncio.sleep_ms(2)

        self.keyboard.set_keys()
        self.keyboard.set_modifiers()
        self.keyboard.notify_hid_report()
        asyncio.sleep_ms(2)

    # Used with test
    def send_string(self, st):
        for c in st:
            self.send_char(c)

    # Test routine
    async def test(self):
        while not self.keyboard.is_connected():
            await asyncio.sleep(5)

        await asyncio.sleep(5)
        self.keyboard.set_battery_level(50)
        self.keyboard.notify_battery_level()
        await asyncio.sleep_ms(500)

        # Press Shift+W
        self.keyboard.set_keys(0x1A)
        self.keyboard.set_modifiers(right_shift=1)
        self.keyboard.notify_hid_report()
        await asyncio.sleep_ms(2)

        # release
        self.keyboard.set_keys()
        self.keyboard.set_modifiers()
        self.keyboard.notify_hid_report()
        await asyncio.sleep_ms(500)

        # Press a
        self.keyboard.set_keys(0x04)
        self.keyboard.notify_hid_report()
        await asyncio.sleep_ms(2)

        # release
        self.keyboard.set_keys()
        self.keyboard.notify_hid_report()
        await asyncio.sleep_ms(500)

        # Press s
        self.keyboard.set_keys(0x16)
        self.keyboard.notify_hid_report()
        await asyncio.sleep_ms(2)

        # release
        self.keyboard.set_keys()
        self.keyboard.notify_hid_report()
        await asyncio.sleep_ms(500)

        # Press d
        self.keyboard.set_keys(0x07)
        self.keyboard.notify_hid_report()
        await asyncio.sleep_ms(2)

        # release
        self.keyboard.set_keys()
        self.keyboard.notify_hid_report()
        await asyncio.sleep_ms(500)

        self.send_string(" Hello World")
        await asyncio.sleep_ms(500)

        self.keyboard.set_battery_level(100)
        self.keyboard.notify_battery_level()

    async def co_start_test(self):
        self.keyboard.start()
        await asyncio.gather(self.advertise_for(30), self.test())

    # start test
    def start_test(self):
        asyncio.run(self.co_start_test())

if __name__ == "__main__":
    d = Device()
    d.start()
