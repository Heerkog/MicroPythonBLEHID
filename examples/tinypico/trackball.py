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

# Implements an I2C pimoroni trackball
import struct

I2C_ADDRESS = 0x0A

REG_LED_RED = 0x00
REG_LED_GRN = 0x01
REG_LED_BLU = 0x02
REG_LED_WHT = 0x03

REG_LEFT = 0x04
REG_RIGHT = 0x05
REG_UP = 0x06
REG_DOWN = 0x07
REG_SWITCH = 0x08

MSK_SWITCH_STATE = 0b10000000

class Trackball(object):
    def __init__(self, i2c, address=I2C_ADDRESS, speed_modifier=1):
        self.address = address
        self.speed_modifier = speed_modifier
        self.i2c = i2c

    def set_color(self, red=0, green=0, blue=0, white=0):
        self.i2c.writeto_mem(self.address, REG_LED_RED, struct.pack("4B", red, green, blue, white))

    def get_color(self):
        red, green, blue, white = struct.unpack("4B", self.i2c.readfrom_mem(self.address, REG_LED_RED, 4))
        return red, green, blue, white

    def get_state(self):
        left, right, up, down, switch = struct.unpack("5B", self.i2c.readfrom_mem(self.address, REG_LEFT, 5))
        left, right, up, down = left * self.speed_modifier, right * self.speed_modifier, up * self.speed_modifier, down * self.speed_modifier
        switch, switch_state = switch & ~MSK_SWITCH_STATE, (switch & MSK_SWITCH_STATE) > 0
        return left, right, up, down, switch, switch_state
