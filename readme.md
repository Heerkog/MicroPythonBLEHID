<div id="top"></div>


<!-- PROJECT SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![GPL License][license-shield]][license-url]
[![Website][website-shield]][website-url]


<!-- PROJECT HEADER -->
<br />
<div align="center">
<h3 align="center">MicroPython Human Interface Device library</h3>

  <p align="center">
    A library that offers implementations of Human Interface Devices (HID) over Bluetooth Low Energy (BLE) GATT for MicroPython.
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a></li>
    <li><a href="#getting-started">Getting Started</a></li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project
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

<p align="right">(<a href="#top">back to top</a>)</p>


<!-- GETTING STARTED -->
## Getting Started

To get a local copy simply clone this repository.

   ```sh
   git clone https://github.com/heerkog/MicroPythonBLEHID.git
   ```

The repository is structured as followed:

* `examples/` directory containing some examples.
  * `async/` directory containing asynchronous examples.
    * `joystick_example.py`
    * `keyboard_example.py`
    * `mouse_example.py`
  * `simple/` directory containing simple examples.
    * `joystick_example.py`
    * `keyboard_example.py`
    * `mouse_example.py`
  * `tinypico/` directory containing TinyPICO specific examples. These are mostly personal projects.
* `hid_services.py` the library.
* `LICENSE` the license.
* `readme.md`

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

The library offers functionality for creating HID services, advertising them, and setting and notifying the central of HID events.
The library does not offer functionality to, for example, send a string of characters to the central using the keyboard service (eventhough this is included in the keyboard example).
The reason for this is that such functionality is entirely dependent on the intended use of the services and should be kept outside of this library.

The library consists of five classes with the following functions:

* `HumanInterfaceDevice` (superclass for the HID service classes, implements the Device Information and Battery services, and sets up BLE and advertisement)
  * `__init__(device_name)` (Initialize the superclass)
  * `ble_irq(event, data)` (Internal callback function that catches BLE interrupt requests)
  * `start()` (Starts Device Information and Battery services)
  * `stop()` (Stops Device Information and Battery services)
  * `write_service_characteristics(handles)` (Writes Device Information and Battery service characteristics)
  * `load_secrets()` (Loads stored secrets for Bluetooth bonding)
  * `save_secrets()` (Saves secrets for Bluetooth bonding)
  * `start_advertising()` (Starts Bluetooth advertisement)
  * `stop_advertising()` (Stops Bluetooth advertisement)
  * `is_running()` (Returns `True` if services are running, otherwise `False`)
  * `is_connected()` (Returns `True` if a central is connected, otherwise `False`)
  * `is_advertising()` (Returns `True` if advertising, otherwise `False`)
  * `set_state(state)` (Sets one of the `HumanInterfaceDevice` constants `DEVICE_STOPPED`, `DEVICE_IDLE`, `DEVICE_ADVERTISING`, or `DEVICE_CONNECTED`. Doesn't change the actual function. Used internally)
  * `get_state()` (Returns one of the `HumanInterfaceDevice` constants `DEVICE_STOPPED`, `DEVICE_IDLE`, `DEVICE_ADVERTISING`, or `DEVICE_CONNECTED`)
  * `set_state_change_callback(callback)` (Sets a callback function that is called when the `HumanInterfaceDevice` state changes between constants `DEVICE_STOPPED`, `DEVICE_IDLE`, `DEVICE_ADVERTISING`, or `DEVICE_CONNECTED`))
  * `get_device_name()` (Returns the device name)
  * `get_services_uuids()` (Returns the service UUIDs)
  * `get_appearance()` (Returns the device appearance id)
  * `get_battery_level()` (Returns the battery level)
  * `set_device_information(manufacture_name, model_number, serial_number)` (Sets the basic Device Information characteristics. Must be called before calling `start()`)
  * `set_device_revision(firmware_revision, hardware_revision, software_revision)` (Sets the Device Information revision characteristics. Must be called before calling `start()`)
  * `set_device_pnp_information(pnp_manufacturer_source, pnp_manufacturer_uuid, pnp_product_id, pnp_product_version)` (Sets the Device Information PnP characteristics. Must be called before calling `start()`)
  * `set_bonding(bond)` (Set whether to use Bluetooth bonding)
  * `set_le_secure(le_secure)` (Set whether to use LE secure pairing)
  * `set_io_capability(io_capability)` (Set input/output capability of this device Determines the pairing procedure, e.g., accept connection/passkey entry/just works. Must be called before calling `start()`)
  * `set_passkey_callback(passkey_callback)` (Set callback function for pairing events. Callback function should return boolean to accept connection or passkey depending on I/O capability used)
  * `set_passkey(passkey)` (Set the passkey to use for pairing)
  * `set_battery_level(level)` (Sets the battery level internally)
  * `notify_battery_level()` (Notifies the central of the current battery level. Call after setting battery level)
  * `notify_hid_report()` (Function for subclasses to override)

* `Joystick` (subclass of `HumanInterfaceDevice`, implements joystick service)
  * `__init__(name)` (Initialize the joystick)
  * `start()` (Starts the HID service using joystick characteristics. Calls `HumanInterfaceDevice.start()`)
  * `write_service_characteristics(handles)` (Writes the joystick HID service characteristics.  Calls `HumanInterfaceDevice.write_service_characteristics(handles)`)
  * `notify_hid_report()` (Notifies the central of the internal HID joystick status)
  * `set_axes(x, y)` (Sets the joystick axes internally)
  * `set_buttons(b1, b2, b3, b4, b5, b6, b7, b8)` (Sets the joystick buttons internally)

* `Mouse` (subclass of `HumanInterfaceDevice`, implements mouse service)
  * `__init__(name)` (Initialize the mouse)
  * `start()` (Starts the HID service using mouse characteristics. Calls `HumanInterfaceDevice.start()`)
  * `write_service_characteristics(handles)` (Writes the mouse HID service characteristics.  Calls `HumanInterfaceDevice.write_service_characteristics(handles)`)
  * `notify_hid_report()` (Notifies the central of the internal HID mouse status)
  * `set_axes(x, y)` (Sets the mouse axes movement internally)
  * `set_wheel(w)` (Sets the mouse wheel movement internally)
  * `set_buttons(b1, b2, b3)` (Sets the mouse buttons internally)

* `Keyboard` (subclass of `HumanInterfaceDevice`, implements keyboard service)
  * `__init__(name)`  (Initialize the keyboard)
  * `start()` (Starts the HID service using keyboard characteristics. Calls `HumanInterfaceDevice.start()`)
  * `write_service_characteristics(handles)` (Writes the keyboard HID service characteristics.  Calls `HumanInterfaceDevice.write_service_characteristics(handles)`)
  * `notify_hid_report()` (Notifies the central of the internal HID keyboard status)
  * `set_modifiers(right_gui, right_alt, right_shift, right_control, left_gui, left_alt, left_shift, left_control)` (Sets the keyboard modifier keys internally)
  * `set_keys(k0, k1, k2, k3, k4, k5)` (Sets a list of key codes to press internally. Call without keys to release.)
  * `ble_irq(event, data)` (Internal callback function that catches BLE keyboard interrupt requests)
  * `set_kb_callback(kb_callback)` (Sets a callback function that is called on a keyboard event)

* `Advertiser` (from the [MicroPython Bluetooth examples](https://github.com/micropython/micropython), used internally by `HumanInterfaceDevice` class)
  * `__init__(ble, services, appearance, name)`
  * `advertising_payload(limited_disc, br_edr, name, services, appearance)`
  * `decode_field(payload, adv_type)`
  * `decode_name(payload)`
  * `decode_services(payload)`
  * `start_advertising()` (Used internally)
  * `stop_advertising()` (Used internally)


<p align="right">(<a href="#top">back to top</a>)</p>


<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- LICENSE -->
## License

Distributed under the GNU General Public License. See `LICENSE` for more information.

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

Heerko Groefsema - [@HeerkoG](https://twitter.com/heerkog) - [hgroefsema.nl](https://hgroefsema.nl)

Project Link: [https://github.com/heerkog/MicroPythonBLEHID](https://github.com/heerkog/MicroPythonBLEHID)

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- ACKNOWLEDGMENTS -->
## Acknowledgments
The following resources were of interest during development:

* Bluetooth HID
  * [Bluetooth Low Energy Specifications](https://www.bluetooth.com/specifications/specs/)
  * [Bluetooth assigned numbers list](https://www.bluetooth.com/specifications/assigned-numbers/)
  * [Bluetooth device class list](http://domoticx.com/bluetooth-class-of-device-lijst-cod/)
* USB HID
  * [USB HID specification](https://www.usb.org/document-library/device-class-definition-hid-111)
  * [USB report descriptor tool](https://www.usb.org/document-library/hid-descriptor-tool)
  * [USB HID report descriptor tutorial](https://eleccelerator.com/tutorial-about-usb-hid-report-descriptors/)
* Micropython
  * [Bluetooth examples](https://github.com/micropython/micropython/tree/master/examples/bluetooth)
  * [BLE HID examples](https://github.com/micropython/micropython/pull/6559)

<p align="right">(<a href="#top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/heerkog/MicroPythonBLEHID.svg?style=for-the-badge
[contributors-url]: https://github.com/heerkog/MicroPythonBLEHID/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/heerkog/MicroPythonBLEHID.svg?style=for-the-badge
[forks-url]: https://github.com/heerkog/MicroPythonBLEHID/network/members
[stars-shield]: https://img.shields.io/github/stars/heerkog/MicroPythonBLEHID.svg?style=for-the-badge
[stars-url]: https://github.com/heerkog/MicroPythonBLEHID/stargazers
[issues-shield]: https://img.shields.io/github/issues/heerkog/MicroPythonBLEHID.svg?style=for-the-badge
[issues-url]: https://github.com/heerkog/MicroPythonBLEHID/issues
[license-shield]: https://img.shields.io/github/license/heerkog/MicroPythonBLEHID.svg?style=for-the-badge
[license-url]: https://github.com/heerkog/MicroPythonBLEHID/blob/master/LICENSE.txt

[website-shield]: https://img.shields.io/badge/Website-H-black.svg?style=for-the-badge&colorB=2A638C
[website-url]: https://hgroefsema.nl
