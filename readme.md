## MicroPython Human Interface Device library (WIP)
This library offers implementations of Human Interface Devices (HID) over Bluetooth Low Energy (BLE) GATT for MicroPython.
The library has been tested using an ESP32 development board ([TinyPICO](https://tinypico.com)) as the peripheral and Windows 10 as the central.
Examples and basic implementations of HID devices are available for 

- Keyboard, 
- Mouse, and
- Joystick.

This library is NOT intended to offer functionality for every possible HID device configuration.
Instead, the library is designed to offer basic well-documented classes that you can extend to fit your HID device needs.
For example, the Mouse class offers a three button mouse with vertical scroll wheel.
If you plan on developing a gaming mouse with eight buttons and both vertical and horizontal wheels, you will need to extend the Mouse class and overwrite the required functions to include a new HID report descriptor.  

### Library structure
The library is structured as followed:

* examples
    * joystick_example.py
    * keyboard_example.py
    * mouse_example.py
* hid_services.py
* readme.md

### Library functionality
The library offers functionality for creating HID services, advertising them, and setting and notifying the central of HID events.
The library does not offer functionality to, for example, send a string of characters to the central using the keyboard service (eventhough this is included in the keyboard example).
The reason for this is that such functionality is entirely dependent on the intended use of the services and should be kept outside of this library.

The library consists of five classes with the following functions:

* Advertiser (from the [MicroPython Bluetooth examples](https://github.com/micropython/micropython), used internally by HumanInterfaceDevice class)
* HumanInterfaceDevice (superclass for the HID service classes, implements the Device Information and Battery services, and sets up BLE and advertisement)
* Joystick (subclass of HumanInterfaceDevice, implements joystick service)
* Mouse (subclass of HumanInterfaceDevice, implements mouse service)
* Keyboard (subclass of HumanInterfaceDevice, implements keyboard service)