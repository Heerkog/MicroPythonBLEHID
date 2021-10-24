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

# Implements a BLE HID trackball on the TinyPICO
import uasyncio as asyncio
from machine import SoftSPI, SoftI2C, Pin
from hid_services import Mouse
from trackball import Trackball
import tinypico as TinyPICO
from dotstar import DotStar

class Device:
    def __init__(self, name="TinyPICO trackball"):
        # Create a DotStar instance
        spi = SoftSPI(sck=Pin( TinyPICO.DOTSTAR_CLK ), mosi=Pin( TinyPICO.DOTSTAR_DATA ), miso=Pin( TinyPICO.SPI_MISO) )
        self.dotstar = DotStar(spi, 1, brightness = 0.5 )  # Just one DotStar, half brightness

        # Turn on the power to the DotStar
        TinyPICO.set_dotstar_power( True )
        self.dotstar[0] = (255, 0, 0, 0.5)

        # Define state
        self.axes = (0, 0)
        self.button = 0
        self.updated = False
        self.active = True

        # Read I2C input
        self.i2c = SoftI2C(scl=Pin(TinyPICO.I2C_SCL), sda=Pin(TinyPICO.I2C_SDA), freq=400000)
        self.trackball = Trackball(self.i2c, speed_modifier=1)
        self.trackball.set_color(255, 0, 0, 0)

        # Create our device
        self.mouse = Mouse(name)
        # Set a callback function to catch changes of device state
        self.mouse.set_state_change_callback(self.mouse_state_callback)

    # Function that catches device status events
    def mouse_state_callback(self):
        if self.mouse.get_state() is Mouse.DEVICE_IDLE:
            self.dotstar[0] = (255, 140, 0, 0.5)
            self.trackball.set_color(255, 140, 0, 0)
        elif self.mouse.get_state() is Mouse.DEVICE_ADVERTISING:
            self.dotstar[0] = (255, 255, 0, 0.5)
            self.trackball.set_color(255, 255, 0, 0)
        elif self.mouse.get_state() is Mouse.DEVICE_CONNECTED:
            self.dotstar[0] = (0, 255, 0, 0.5)
            self.trackball.set_color(0, 255, 0, 0)
        else:
            self.dotstar[0] = (255, 0, 0, 0.5)
            self.trackball.set_color(255, 0, 0, 0)

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
            left, right, up, down, but1, but1_state = self.trackball.get_state()

            prevaxes = self.axes
            prevbutton = self.button

            self.axes = (self.clamp(self.axes[0] + left - right), self.clamp(self.axes[1] + up - down))
            self.button = 1 if but1 > 0 else 0

            self.updated = self.updated or not (prevaxes == self.axes) or not (prevbutton == self.button)  # If updated is still True, we haven't notified yet
            await asyncio.sleep_ms(20)

    def clamp(self, n, minimum=-127, maximum=127):
        return max(min(maximum, n), minimum)

    # Bluetooth device loop
    async def notify(self):
        while self.active:
            # If connected, set axes and notify
            # If idle, start advertising for 30s or until connected
            if self.updated:
                if self.mouse.get_state() is Mouse.DEVICE_CONNECTED:
                    self.mouse.set_axes(self.axes[0], self.axes[1])
                    self.mouse.set_buttons(b1=self.button)
                    self.mouse.notify_hid_report()
                elif self.mouse.get_state() is Mouse.DEVICE_IDLE:
                    await self.advertise_for(30)
                self.updated = False

            if self.mouse.get_state() is Mouse.DEVICE_CONNECTED:
                await asyncio.sleep_ms(20)
            else:
                await asyncio.sleep(2)

    async def co_start(self):
        # Start our device
        if self.mouse.get_state() is Mouse.DEVICE_STOPPED:
            self.mouse.start()
            self.active = True
            await asyncio.gather(self.advertise_for(30), self.gather_input(), self.notify())

    async def co_stop(self):
        self.active = False
        self.mouse.stop()

    def start(self):
        asyncio.run(self.co_start())

    def stop(self):
        asyncio.run(self.co_stop())


if __name__ == "__main__":
    d = Device()
    d.start()
