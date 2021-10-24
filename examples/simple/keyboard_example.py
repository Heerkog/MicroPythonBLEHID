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
import time
from machine import SoftSPI, Pin
from hid_services import Keyboard

class Device:
    def __init__(self):
        # Define state
        self.key0 = 0x00
        self.key1 = 0x00
        self.key2 = 0x00
        self.key3 = 0x00

        # Define buttons
        self.pin_forward = Pin(5, Pin.IN)
        self.pin_reverse = Pin(23, Pin.IN)
        self.pin_right = Pin(19, Pin.IN)
        self.pin_left = Pin(18, Pin.IN)

        # Create our device
        self.keyboard = Keyboard("Keyboard")
        # Set a callback function to catch changes of device state
        self.keyboard.set_state_change_callback(self.keyboard_state_callback)
        # Start our device
        self.keyboard.start()

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

    # Main loop
    def start(self):
        while True:
            # Read pin values and update variables
            if self.pin_forward.value():
                self.key0 = 0x1A  # W
            else:
                self.key0 = 0x00

            if self.pin_left.value():
                self.key1 = 0x04  # A
            else:
                self.key1 = 0x00

            if self.pin_reverse.value():
                self.key2 = 0x16  # S
            else:
                self.key2 = 0x00

            if self.pin_right.value():
                self.key3 = 0x07  # D
            else:
                self.key3 = 0x00

            # If the variables changed do something depending on the device state
            if (self.key0 != 0x00) or (self.key1 != 0x00) or (self.key2 != 0x00) or (self.key3 != 0x00):
                # If connected set keys and notify
                # If idle start advertising for 30s or until connected
                if self.keyboard.get_state() is Keyboard.DEVICE_CONNECTED:
                    self.keyboard.set_keys(self.key0, self.key1, self.key2, self.key3)
                    self.keyboard.notify_hid_report()
                elif self.keyboard.get_state() is Keyboard.DEVICE_IDLE:
                    self.keyboard.start_advertising()
                    i = 10
                    while i > 0 and self.keyboard.get_state() is Keyboard.DEVICE_ADVERTISING:
                        time.sleep(3)
                        i -= 1
                    if self.keyboard.get_state() is Keyboard.DEVICE_ADVERTISING:
                        self.keyboard.stop_advertising()

            if self.keyboard.get_state() is Keyboard.DEVICE_CONNECTED:
                time.sleep_ms(20)
            else:
                time.sleep(2)

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
        time.sleep_ms(2)

        self.keyboard.set_keys()
        self.keyboard.set_modifiers()
        self.keyboard.notify_hid_report()
        time.sleep_ms(2)


    def send_string(self, st):
        for c in st:
            self.send_char(c)

    # Only for test
    def stop(self):
        self.keyboard.stop()

    # Test routine
    def test(self):
        time.sleep(5)
        self.keyboard.set_battery_level(50)
        self.keyboard.notify_battery_level()
        time.sleep_ms(2)

        # Press Shift+W
        self.keyboard.set_keys(0x1A)
        self.keyboard.set_modifiers(right_shift=1)
        self.keyboard.notify_hid_report()

        # release
        self.keyboard.set_keys()
        self.keyboard.set_modifiers()
        self.keyboard.notify_hid_report()
        time.sleep_ms(500)

        # Press a
        self.keyboard.set_keys(0x04)
        self.keyboard.notify_hid_report()

        # release
        self.keyboard.set_keys()
        self.keyboard.notify_hid_report()
        time.sleep_ms(500)

        # Press s
        self.keyboard.set_keys(0x16)
        self.keyboard.notify_hid_report()

        # release
        self.keyboard.set_keys()
        self.keyboard.notify_hid_report()
        time.sleep_ms(500)

        # Press d
        self.keyboard.set_keys(0x07)
        self.keyboard.notify_hid_report()

        # release
        self.keyboard.set_keys()
        self.keyboard.notify_hid_report()
        time.sleep_ms(500)

        self.send_string(" Hello World")

        self.keyboard.set_battery_level(100)
        self.keyboard.notify_battery_level()

if __name__ == "__main__":
    d = Device()
    d.start()
