# Implements a BLE HID joystick

import bluetooth
import time
from hid_devices import Joystick, Mouse
from hid_services import Server

ble = bluetooth.BLE()

server = Server(ble)
joystick = Joystick("test1")

server.start(joystick)
server.start_advertising()

while not server.is_connected():
    time.sleep(1)

time.sleep(5)

i = 0

while i < 15:
    joystick.set_axes(100,100)
    joystick.set_buttons(1)
    server.send_report(joystick.get_state())
    time.sleep(1)

    joystick.set_axes(0,0)
    joystick.set_buttons(b2=1)
    server.send_report(joystick.get_state())
    time.sleep(1)

    joystick.set_axes(100,-100)
    joystick.set_buttons(b3=1)
    server.send_report(joystick.get_state())
    time.sleep(1)

    joystick.set_axes(0,0)
    joystick.set_buttons()
    server.send_report(joystick.get_state())
    time.sleep(1)

    i += 1

server.stop_advertising()
server.stop()
