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

# Implements a BLE HID mouse on the TinyPICO
import uasyncio as asyncio
from machine import SoftSPI, SoftI2C, Pin
import tinypico as TinyPICO
from dotstar import DotStar
from hid_services import Mouse
from trackball import Trackball
from trill import Square
from touch import Touches2D

class Device:
    def __init__(self, name="TinyPICO touchpad", sensitivity=50, press_sensitivity=2000):
        self.sensitivity = sensitivity
        self.press_sensitivity = press_sensitivity

        self.active = False

        # Create a DotStar instance
        spi = SoftSPI(sck=Pin( TinyPICO.DOTSTAR_CLK ), mosi=Pin( TinyPICO.DOTSTAR_DATA ), miso=Pin( TinyPICO.SPI_MISO) )
        self.dotstar = DotStar(spi, 1, brightness = 0.5 )  # Just one DotStar, half brightness

        # Turn on the power to the DotStar
        TinyPICO.set_dotstar_power( True )
        self.dotstar[0] = (0, 0, 0, 0.5)

        # Define state
        self.mousestate = MouseState()
        self.touchstate = TouchState(self.press_sensitivity)

        # I2C input sensors
        i2c = SoftI2C(scl=Pin(TinyPICO.I2C_SCL), sda=Pin(TinyPICO.I2C_SDA), freq=400000)
        self.touchpad = Square(i2c)
        self.trackball = Trackball(i2c)
        self.trackball.set_color(0, 0, 0, 0)

        # Create our device
        self.mouse = Mouse(name)
        # Set a callback function to catch changes of device state
        self.mouse.set_state_change_callback(self.mouse_state_callback)

    # Function that catches device status events
    def mouse_state_callback(self):
        if self.mouse.get_state() is Mouse.DEVICE_ADVERTISING:
            self.dotstar[0] = (0, 0, 255, 0.5)
            self.trackball.set_color(0, 0, 255, 0)
        else:
            self.set_battery_level()

    def advertise(self):
        self.mouse.start_advertising()

    def stop_advertise(self):
        self.mouse.stop_advertising()

    async def advertise_for(self, seconds=30):
        self.advertise()

        while seconds > 0 and self.mouse.get_state() is Mouse.DEVICE_ADVERTISING:
            await asyncio.sleep(1)
            seconds -= 1

        if self.mouse.get_state() is Mouse.DEVICE_ADVERTISING:
            self.stop_advertise()

    # Input loop
    async def gather_input(self):
        while self.active:
            # Read and update touchstate using touchpad
            touches = Touches2D(self.touchpad.read())

            wasTouched = self.touchstate.is_touched()
            self.touchstate.update_touches(touches)

            if self.touchstate.is_touched() or wasTouched:
                (x, y) = self.touchstate.get_touch()
                (h, v) = self.touchpad.get_size()

                (sx, sy) = (int(x * self.sensitivity/h), int(y * self.sensitivity/v))
                self.mousestate.set_axes_absolute(sx, sy)

            # Read and update touchstate using trackball
            left, right, up, down, switch, switch_state = self.trackball.get_state()

            self.mousestate.set_axes_relative(right - left, down - up)
            self.mousestate.set_button(0, switch_state or self.touchstate.get_press())

            await asyncio.sleep_ms(20)

    # Bluetooth device loop
    async def notify(self):
        while self.active:
            # If connected, set axes and notify
            # If idle, start advertising for 30s or until connected
            if (not self.mousestate.is_centered()) or self.mousestate.is_updated():
                if self.mouse.get_state() is Mouse.DEVICE_CONNECTED:
                    axes = self.mousestate.get_axes()
                    buttons = self.mousestate.get_buttons()
                    self.mouse.set_axes(axes[0], axes[1])
                    self.mouse.set_buttons(b1=buttons[0])
                    self.mouse.notify_hid_report()
                elif self.mouse.get_state() is Mouse.DEVICE_IDLE:
                    await self.advertise_for(30)
                self.mousestate.notified()

            if self.mouse.get_state() is Mouse.DEVICE_CONNECTED:
                await asyncio.sleep_ms(20)
            else:
                await asyncio.sleep(2)

    async def battery_input(self):
        while self.active:
            self.set_battery_level()
            await asyncio.sleep(60)

    async def co_start(self):
        # Start our device
        if self.mouse.get_state() is Mouse.DEVICE_STOPPED:
            self.mouse.start()
            self.active = True
            await asyncio.gather(self.battery_input(), self.gather_input(), self.notify(), self.advertise_for(30))

    async def co_stop(self):
        self.active = False
        self.mouse.stop()

    def set_battery_level(self):
        v = TinyPICO.get_battery_voltage()

        if 3.7 == v or 4.2 <= v or TinyPICO.get_battery_charging():
            self.mouse.set_battery_level(100)
            self.dotstar[0] = (0, 255, 0, 0.5)
            self.trackball.set_color(0, 255, 0, 0)
        elif 4.1 <= v < 4.2:
            self.mouse.set_battery_level(90)
            self.dotstar[0] = (64, 255, 0, 0.5)
            self.trackball.set_color(64, 255, 0, 0)
        elif 4.0 <= v < 4.1:
            self.mouse.set_battery_level(80)
            self.dotstar[0] = (192, 255, 0, 0.5)
            self.trackball.set_color(192, 255, 0, 0)
        elif 3.9 <= v < 4.0:
            self.mouse.set_battery_level(60)
            self.trackball.set_color(255, 255, 0, 0)
        elif 3.8 <= v < 3.9:
            self.mouse.set_battery_level(40)
            self.dotstar[0] = (255, 192, 0, 0.5)
            self.trackball.set_color(255, 192, 0, 0)
        elif 3.7 <= v < 3.8:
            self.mouse.set_battery_level(20)
            self.dotstar[0] = (255, 64, 0, 0.5)
            self.trackball.set_color(255, 64, 0, 0)
        else:
            self.mouse.set_battery_level(0)
            self.dotstar[0] = (255, 0, 0, 0.5)
            self.trackball.set_color(255, 0, 0, 0)

        if self.mouse.get_state() is self.mouse.DEVICE_CONNECTED:
            self.mouse.notify_battery_level()

    def start(self):
        asyncio.run(self.co_start())

    def stop(self):
        asyncio.run(self.co_stop())


class MouseState:

    def __init__(self):
        self.axes = [0, 0]
        self.buttons = [False] * 6
        self.updated = False

    def set_axes_absolute(self, x, y):
        self.updated = x != 0 or y != 0 or self.axes[0] != 0 or self.axes[1] != 0
        self.set_axes(x, y)

    def set_axes_relative(self, x, y):
        self.set_axes(self.axes[0] + x, self.axes[1] + y)
        self.updated = self.updated or x != 0 or y != 0

    def set_axes(self, x, y):
        self.axes[0] = x if -127 <= x <= 127 else (-127 if x < -127 else 127)
        self.axes[1] = y if -127 <= y <= 127 else (-127 if y < -127 else 127)

    def set_button(self, index, press):
        self.updated = self.updated or press is not self.buttons[index]

        self.buttons[index] = press

    def get_axes(self):
        return self.axes

    def get_buttons(self):
        return self.buttons

    def is_centered(self):
        return self.axes[0] is 0 and self.axes[1] is 0

    def is_updated(self):
        return self.updated

    def notified(self):
        self.updated = False


class TouchState:

    def __init__(self, press=4000):
        self.press=press
        self.initial = None
        self.current = None
        self.pressed = False

    def update_touches(self, touches):
        if touches.is_empty():
            self.initial = None
            self.current = None
            self.pressed = False
        else:
            if self.initial is None:
                self.initial = touches.get_touch(0)
            else:
                self.current = touches.get_touch(0)

        if self.current is not None:
            self.pressed = self.current[2] + self.current[3] > self.press

    def get_touch(self):
        if self.initial is None or self.current is None:
            touch = (0, 0)
        else:
            touch = (self.current[0] - self.initial[0], self.initial[1] - self.current[1])
        return touch

    def get_press(self):
        return self.pressed

    def is_touched(self):
        return self.current is not None


if __name__ == "__main__":
    d = Device()
    d.start()
