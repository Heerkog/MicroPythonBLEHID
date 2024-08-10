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


from micropython import const
import struct
import bluetooth
import json
import binascii
from bluetooth import UUID

F_READ = bluetooth.FLAG_READ
F_WRITE = bluetooth.FLAG_WRITE
F_READ_WRITE = bluetooth.FLAG_READ | bluetooth.FLAG_WRITE
F_READ_NOTIFY = bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY
F_READ_WRITE_NORESPONSE = bluetooth.FLAG_READ | bluetooth.FLAG_WRITE | bluetooth.FLAG_WRITE_NO_RESPONSE

ATT_F_READ = 0x01
ATT_F_WRITE = 0x02
ATT_F_READ_WRITE = ATT_F_READ | ATT_F_WRITE

# Advertising payloads are repeated packets of the following form:
#   1 byte data length (N + 1)
#   1 byte type (see constants below)
#   N bytes type-specific data
_ADV_TYPE_FLAGS = const(0x01)
_ADV_TYPE_NAME = const(0x09)
_ADV_TYPE_UUID16_COMPLETE = const(0x3)
_ADV_TYPE_UUID32_COMPLETE = const(0x5)
_ADV_TYPE_UUID128_COMPLETE = const(0x7)
_ADV_TYPE_UUID16_MORE = const(0x2)
_ADV_TYPE_UUID32_MORE = const(0x4)
_ADV_TYPE_UUID128_MORE = const(0x6)
_ADV_TYPE_APPEARANCE = const(0x19)

# IRQ peripheral role event codes
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_IRQ_GATTS_READ_REQUEST = const(4)
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE = const(12)
_IRQ_GATTC_DESCRIPTOR_RESULT = const(13)
_IRQ_GATTC_DESCRIPTOR_DONE = const(14)
_IRQ_GATTC_READ_RESULT = const(15)
_IRQ_GATTC_READ_DONE = const(16)
_IRQ_GATTC_WRITE_DONE = const(17)
_IRQ_GATTC_NOTIFY = const(18)
_IRQ_GATTC_INDICATE = const(19)
_IRQ_GATTS_INDICATE_DONE = const(20)
_IRQ_MTU_EXCHANGED = const(21)
_IRQ_L2CAP_ACCEPT = const(22)
_IRQ_L2CAP_CONNECT = const(23)
_IRQ_L2CAP_DISCONNECT = const(24)
_IRQ_L2CAP_RECV = const(25)
_IRQ_L2CAP_SEND_READY = const(26)
_IRQ_CONNECTION_UPDATE = const(27)
_IRQ_ENCRYPTION_UPDATE = const(28)
_IRQ_GET_SECRET = const(29)
_IRQ_SET_SECRET = const(30)
_IRQ_PASSKEY_ACTION = const(31)

_IO_CAPABILITY_DISPLAY_ONLY = const(0)
_IO_CAPABILITY_DISPLAY_YESNO = const(1)
_IO_CAPABILITY_KEYBOARD_ONLY = const(2)
_IO_CAPABILITY_NO_INPUT_OUTPUT = const(3)
_IO_CAPABILITY_KEYBOARD_DISPLAY = const(4)

_PASSKEY_ACTION_INPUT = const(2)
_PASSKEY_ACTION_DISP = const(3)
_PASSKEY_ACTION_NUMCMP = const(4)

_GATTS_NO_ERROR = const(0x00)
_GATTS_ERROR_READ_NOT_PERMITTED = const(0x02)
_GATTS_ERROR_WRITE_NOT_PERMITTED = const(0x03)
_GATTS_ERROR_INSUFFICIENT_AUTHENTICATION = const(0x05)
_GATTS_ERROR_INSUFFICIENT_AUTHORIZATION = const(0x08)
_GATTS_ERROR_INSUFFICIENT_ENCRYPTION = const(0x0f)

class Advertiser:

    # Generate a payload to be passed to gap_advertise(adv_data=...).
    def advertising_payload(self, limited_disc=False, br_edr=False, name=None, services=None, appearance=0):
        payload = bytearray()

        def _append(adv_type, value):
            nonlocal payload
            payload += struct.pack("BB", len(value) + 1, adv_type) + value

        _append(
            _ADV_TYPE_FLAGS,
            struct.pack("B", (0x01 if limited_disc else 0x02) + (0x18 if br_edr else 0x04)),
        )

        if name:
            _append(_ADV_TYPE_NAME, name)

        if services:
            for uuid in services:
                b = bytes(uuid)
                if len(b) == 2:
                    _append(_ADV_TYPE_UUID16_COMPLETE, b)
                elif len(b) == 4:
                    _append(_ADV_TYPE_UUID32_COMPLETE, b)
                elif len(b) == 16:
                    _append(_ADV_TYPE_UUID128_COMPLETE, b)

        # See org.bluetooth.characteristic.gap.appearance.xml
        if appearance:
            _append(_ADV_TYPE_APPEARANCE, struct.pack("<h", appearance))

        return payload


    def decode_field(self, payload, adv_type):
        i = 0
        result = []
        while i + 1 < len(payload):
            if payload[i + 1] == adv_type:
                result.append(payload[i + 2 : i + payload[i] + 1])
            i += 1 + payload[i]
        return result


    def decode_name(self, payload):
        n = self.decode_field(payload, _ADV_TYPE_NAME)
        return str(n[0], "utf-8") if n else ""


    def decode_services(self, payload):
        services = []
        for u in self.decode_field(payload, _ADV_TYPE_UUID16_COMPLETE):
            services.append(bluetooth.UUID(struct.unpack("<h", u)[0]))
        for u in self.decode_field(payload, _ADV_TYPE_UUID32_COMPLETE):
            services.append(bluetooth.UUID(struct.unpack("<d", u)[0]))
        for u in self.decode_field(payload, _ADV_TYPE_UUID128_COMPLETE):
            services.append(bluetooth.UUID(u))
        return services

    # Init as generic HID device (960 = generic HID appearance value).
    def __init__(self, ble, services=[UUID(0x1812)], appearance=const(960), name="Generic HID Device"):
        self._ble = ble
        self._payload = self.advertising_payload(name=name, services=services, appearance=appearance)

        self.advertising = False
        print("Advertiser created: ", self.decode_name(self._payload), " with services: ", self.decode_services(self._payload))

    # Start advertising at 100000 interval.
    def start_advertising(self):
        if not self.advertising:
            self._ble.gap_advertise(100000, adv_data=self._payload)
            print("Started advertising")

    # Stop advertising by setting interval of 0.
    def stop_advertising(self):
        if self.advertising:
            self._ble.gap_advertise(0, adv_data=self._payload)
            print("Stopped advertising")


# Class that represents a general HID device services.
class HumanInterfaceDevice(object):
    # Define device states
    DEVICE_STOPPED = const(0)
    DEVICE_IDLE = const(1)
    DEVICE_ADVERTISING = const(2)
    DEVICE_CONNECTED = const(3)

    def __init__(self, device_name="Generic HID Device"):
        self._ble = bluetooth.BLE()                                                                                     # The BLE.
        self.adv = None                                                                                                 # The advertiser.
        self.device_state = HumanInterfaceDevice.DEVICE_STOPPED                                                         # The initial device state.
        self.conn_handle = None                                                                                         # The handle of the connected client. HID devices can only have a single connection.
        self.state_change_callback = None                                                                               # The user defined callback function which gets called when the device state changes.
        self.io_capability = _IO_CAPABILITY_NO_INPUT_OUTPUT                                                             # The IO capability of the device. This is used to allow for different ways of identification during pairing.
        self.bond = True                                                                                                # Do we wish to bond with connecting clients? Normally True. Not supported by older Micropython versions.
        self.le_secure = True                                                                                           # Do we wish to use a secure connection? Normally True. Not supported by older Micropython versions.

        self.encrypted = False                                                                                          # Is our connection encrypted?
        self.authenticated = False                                                                                      # Is the connected client authenticated?
        self.bonded = False                                                                                             # Are we bonded with the connected client?
        self.key_size = 0                                                                                               # The encryption key size.

        self.passkey = 1234                                                                                             # The standard passkey for pairing. Only used when io capability allows so. Use the set_passkey(passkey) function to overwrite.
        self.keys = {}                                                                                                  # The key store for bonding

        self.load_secrets()                                                                                             # Call the function to load the known keys for bonding into the key store.

        # General characteristics.
        self.device_name = device_name                                                                                  # The device name.
        self.service_uuids = [UUID(0x180A), UUID(0x180F), UUID(0x1812)]                                                 # Service UUIDs: DIS, BAS, HIDS (Device Information Service, BAttery Service, Human Interface Device Service). These are required for a HID.
        self.device_appearance = 960                                                                                    # The device appearance: 960 = Generic HID.

        # Device Information Service (DIS) characteristics.
        self.model_number = "1"                                                                                         # The model number characteristic.
        self.serial_number = "1"                                                                                        # The serial number characteristic.
        self.firmware_revision = "1"                                                                                    # The firmware revision characteristic.
        self.hardware_revision = "1"                                                                                    # The hardware revision characteristic.
        self.software_revision = "2"                                                                                    # The software revision characteristic.
        self.manufacture_name = "Homebrew"                                                                              # The manufacturer name characteristic.

        # DIS plug and play (PnP) characteristics.
        self.pnp_manufacturer_source = 0x01                                                                             # The manufacturer source. 0x01 = Bluetooth uuid list.
        self.pnp_manufacturer_uuid = 0xFE61                                                                             # The manufacturer id, e.g., 0xFEB2 for Microsoft, 0xFE61 for Logitech, 0xFD65 for Razer.
        self.pnp_product_id = 0x01                                                                                      # The product id. 0x01 = 1.
        self.pnp_product_version = 0x0123                                                                               # The product version. 0x0123 = 1.2.3.

        # BAttery Service (BAS) characteristics.
        self.battery_level = 100                                                                                        # The battery level characteristic (percentages).

        # Device Information Service (DIS) description.
        self.DIS = (
            UUID(0x180A),                                                                                               # 0x180A = Device Information.
            (
                (UUID(0x2A24), F_READ),                                                                                 # 0x2A24 = Model number string, to be read by client.
                (UUID(0x2A25), F_READ),                                                                                 # 0x2A25 = Serial number string, to be read by client.
                (UUID(0x2A26), F_READ),                                                                                 # 0x2A26 = Firmware revision string, to be read by client.
                (UUID(0x2A27), F_READ),                                                                                 # 0x2A27 = Hardware revision string, to be read by client.
                (UUID(0x2A28), F_READ),                                                                                 # 0x2A28 = Software revision string, to be read by client.
                (UUID(0x2A29), F_READ),                                                                                 # 0x2A29 = Manufacturer name string, to be read by client.
                (UUID(0x2A50), F_READ),                                                                                 # 0x2A50 = PnP ID, to be read by client.
            ),
        )

        # Battery Service (BAS) description.
        self.BAS = (
            UUID(0x180F),                                                                                               # 0x180F = Battery Information.
            (
                (UUID(0x2A19), F_READ_NOTIFY, (                                                                        # 0x2A19 = Battery level, to be read by client after being notified of change.
                    (UUID(0x2902), ATT_F_READ_WRITE),                                                                   # 0x2902 = Client Characteristic Configuration.
                    (UUID(0x2904), ATT_F_READ),                                                                         # 0x2904 = Characteristic Presentation Format.
                )),
            ),
        )

        self.services = [self.DIS, self.BAS]                                                                            # List of service descriptions. We will append HIDS in their respective subclasses.

        self.HID_INPUT_REPORT = None                                                                                    # The HID USB input report. We will specify thesein their respective subclasses.

        print("Server created")

    # Interrupt request callback function.
    def ble_irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:                                                                               # Central connected.
            self.conn_handle, _, _ = data                                                                               # Save the handle. HIDS specification only allow one central to be connected.
            self.set_state(HumanInterfaceDevice.DEVICE_CONNECTED)                                                       # Set the device state to connected.
            print("Central connected: ", self.conn_handle)
        elif event == _IRQ_CENTRAL_DISCONNECT:                                                                          # Central disconnected.
            conn_handle, addr_type, addr = data
            self.conn_handle = None                                                                                     # Discard old handle.
            self.set_state(HumanInterfaceDevice.DEVICE_IDLE)
            self.encrypted = False
            self.authenticated = False
            self.bonded = False
            print("Central disconnected: ", conn_handle)
        elif event == _IRQ_GATTS_READ_REQUEST:                                                                          # Read request from client.
            conn_handle, attr_handle = data
            print("Read request: ", attr_handle)
            if conn_handle != self.conn_handle:                                                                         # If different connection, return no permission.
                return _GATTS_ERROR_READ_NOT_PERMITTED
            elif self.bond and not self.bonded:                                                                         # If we wish to bond but are not bonded, return insufficient authorization.
                return _GATTS_ERROR_INSUFFICIENT_AUTHORIZATION
            elif self.io_capability > _IO_CAPABILITY_NO_INPUT_OUTPUT and not self.authenticated:                        # If we can authenticate but the client hasn't authenticated, return insufficient authentication.
                return _GATTS_ERROR_INSUFFICIENT_AUTHENTICATION
            elif self.le_secure and (not self.encrypted or self.key_size < 16):                                         # If we wish for a secure connection but it is unencrypted or not strong enough, return insufficient encryption.
                return _GATTS_ERROR_INSUFFICIENT_ENCRYPTION
            else:                                                                                                       # Otherwise, return no error.
                return _GATTS_NO_ERROR
        elif event == _IRQ_GATTS_INDICATE_DONE:                                                                         # A sent indication was done. (We don't use indications currently. If needed, define a callback function and override this function.)
            conn_handle, value_handle, status = data
            print("Indicate done: ", data)
        elif event == _IRQ_MTU_EXCHANGED:                                                                               # MTU was exchanged, set it.
            conn_handle, mtu = data
            self._ble.config(mtu=mtu)
            print("MTU exchanged: ", mtu)
        elif event == _IRQ_CONNECTION_UPDATE:                                                                           # Connection parameters were updated.
            self.conn_handle, conn_interval, conn_latency, supervision_timeout, status = data                           # The new parameters.
            print("Connection update. Interval=", conn_interval, " latency=", conn_latency, " timeout=", supervision_timeout, " status=", status)
            return None                                                                                                 # Return an empty packet.
        elif event == _IRQ_ENCRYPTION_UPDATE:                                                                           # Encryption was updated.
            conn_handle, self.encrypted, self.authenticated, self.bonded, self.key_size = data                          # Update the values.
            print("encryption update", conn_handle, self.encrypted, self.authenticated, self.bonded, self.key_size)
        elif event == _IRQ_PASSKEY_ACTION:                                                                              # Passkey actions: accept connection or show/enter passkey.
            conn_handle, action, passkey = data
            print("passkey action", conn_handle, action, passkey)
            if action == _PASSKEY_ACTION_NUMCMP:                                                                        # Do we accept this connection?
                accept = False
                if self.passkey_callback is not None:                                                                   # Is callback function set?
                    accept = self.passkey_callback()                                                                    # Call callback for input.
                self._ble.gap_passkey(conn_handle, action, accept)
            elif action == _PASSKEY_ACTION_DISP:                                                                        # Show our passkey.
                print("displaying passkey")
                self._ble.gap_passkey(conn_handle, action, self.passkey)
            elif action == _PASSKEY_ACTION_INPUT:                                                                       # Enter passkey.
                print("prompting for passkey")
                pk = None
                if self.passkey_callback is not None:                                                                   # Is callback function set?
                    pk = self.passkey_callback()                                                                        # Call callback for input.
                self._ble.gap_passkey(conn_handle, action, pk)
            else:
                print("Unknown passkey action")
        elif event == _IRQ_SET_SECRET:                                                                                  # Set secret for bonding.
            sec_type, key, value = data
            key = sec_type, bytes(key)
            value = bytes(value) if value else None
            print("set secret: ", key, value)
            if value is None:                                                                                           # If value is empty, and
                if key in self.keys:                                                                                    # If key is known then
                    del self.keys[key]                                                                                  # Forget key
                    self.save_secrets()                                                                                 # Save bonding information
                    return True
                else:
                    return False
            else:
                self.keys[key] = value                                                                                  # Remember key/value
                self.save_secrets()                                                                                     # Save bonding information
            return True
        elif event == _IRQ_GET_SECRET:                                                                                  # Get secret for bonding
            sec_type, index, key = data
            print("get secret: ", sec_type, index, bytes(key) if key else None)
            if key is None:
                i = 0
                for (t, _key), value in self.keys.items():
                    if t == sec_type:
                        if i == index:
                            return value
                        i += 1
                return None
            else:
                key = sec_type, bytes(key)
                return self.keys.get(key, None)
        else:
            print("Unhandled IRQ event: ", event)

    # Start the service.
    # Must be overwritten by subclass, and called in
    # the overwritten function by using super(Subclass, self).start().
    def start(self):
        if self.device_state is HumanInterfaceDevice.DEVICE_STOPPED:
            self._ble.irq(self.ble_irq)                                                                                 # Set interrupt request callback function.
            self._ble.active(1)                                                                                         # Turn on BLE radio.

            # Configure BLE interface
            self._ble.config(gap_name=self.device_name)                                                                 # Set GAP device name.
            self._ble.config(mtu=23)                                                                                    # Configure MTU.
            self._ble.config(bond=self.bond)                                                                            # Allow bonding.
            self._ble.config(le_secure=self.le_secure)                                                                  # Require secure pairing.
            self._ble.config(mitm=self.le_secure)                                                                       # Require man in the middle protection.
            self._ble.config(io=self.io_capability)                                                                     # Set our input/output capabilities. Determines whether and how passkeys are used.

            self.set_state(HumanInterfaceDevice.DEVICE_IDLE)                                                            # Update the device state.
            print("BLE on")

    # After registering the DIS and BAS services, write their characteristic values.
    # Must be overwritten by subclass, and called in
    # the overwritten function by using
    # super(Subclass, self).write_service_characteristics(handles).
    def write_service_characteristics(self, handles):
        print("Writing service characteristics")

        (h_mod, h_ser, h_fwr, h_hwr, h_swr, h_man, h_pnp) = handles[0]                                                  # Get handles to DIS service characteristics. These correspond directly to its definition in self.DIS. Position 0 because of the order of self.services.
        (self.h_bat, h_ccc, h_bfmt,) = handles[1]                                                                       # Get handles to BAS service characteristics. These correspond directly to its definition in self.BAS. Position 1 because of the order of self.services.

        print("h_mod =", h_mod, "h_ser =", h_ser, "h_fwr =", h_fwr, "h_hwr =", h_hwr, "h_swr =", h_swr, "h_man =", h_man, "h_pnp =", h_pnp)
        print("h_bat =", self.h_bat)

        # Simplify packing strings into byte arrays.
        def string_pack(in_str, nr_bytes):
            return struct.pack(str(nr_bytes)+"s", in_str.encode('UTF-8'))

        print("Writing device information service characteristics")
        # Write DIS characteristics.
        self._ble.gatts_write(h_mod, string_pack(self.model_number, 24))
        self._ble.gatts_write(h_ser, string_pack(self.serial_number, 16))
        self._ble.gatts_write(h_fwr, string_pack(self.firmware_revision, 8))
        self._ble.gatts_write(h_hwr, string_pack(self.hardware_revision, 16))
        self._ble.gatts_write(h_swr, string_pack(self.software_revision, 8))
        self._ble.gatts_write(h_man, string_pack(self.manufacture_name, 36))
        self._ble.gatts_write(h_pnp, struct.pack("<BHHH", self.pnp_manufacturer_source, self.pnp_manufacturer_uuid, self.pnp_product_id, self.pnp_product_version))

        print("Writing battery service characteristics")
        # Write BAS characteristics.
        self._ble.gatts_write(self.h_bat, struct.pack("<B", self.battery_level))
        self._ble.gatts_write(h_bfmt, b'\x04\x00\xad\x27\x01\x00\x00')
        self._ble.gatts_write(h_ccc, b'\x00\x00')


    # Stop the service.
    def stop(self):
        if self.device_state is not HumanInterfaceDevice.DEVICE_STOPPED:
            if self.device_state is HumanInterfaceDevice.DEVICE_ADVERTISING:
                self.adv.stop_advertising()

            if self.conn_handle is not None:
                self._ble.gap_disconnect(self.conn_handle)
                self.conn_handle = None

            self._ble.active(0)

            self.set_state(HumanInterfaceDevice.DEVICE_STOPPED)
            print("Server stopped")

    # Load bonding keys from json file.
    def load_secrets(self):
        try:
            with open("keys.json", "r") as file:
                entries = json.load(file)
                for sec_type, key, value in entries:
                    self.keys[sec_type, binascii.a2b_base64(key)] = binascii.a2b_base64(value)
        except:
            print("no secrets available")

    # Save bonding keys to json file.
    def save_secrets(self):
        try:
            with open("keys.json", "w") as file:
                json_secrets = [
                    (sec_type, binascii.b2a_base64(key), binascii.b2a_base64(value))
                    for (sec_type, key), value in self.keys.items()
                ]
                json.dump(json_secrets, file)
        except:
            print("failed to save secrets")

    # Returns whether the device is not stopped.
    def is_running(self):
        return self.device_state is not HumanInterfaceDevice.DEVICE_STOPPED

    # Returns whether the device is connected with a client.
    def is_connected(self):
        return self.device_state is HumanInterfaceDevice.DEVICE_CONNECTED

    # Returns whether the device services are being advertised.
    def is_advertising(self):
        return self.device_state is HumanInterfaceDevice.DEVICE_ADVERTISING

    # Set a new state and notify the user's callback function.
    def set_state(self, state):
        self.device_state = state
        if self.state_change_callback is not None:
            self.state_change_callback()

    # Returns the state of the device, i.e.
    # - DEVICE_STOPPED,
    # - DEVICE_IDLE,
    # - DEVICE_ADVERTISING, or
    # - DEVICE_CONNECTED.
    def get_state(self):
        return self.device_state

    # Set a callback function to get notifications of state changes, i.e.
    # - DEVICE_STOPPED,
    # - DEVICE_IDLE,
    # - DEVICE_ADVERTISING, or
    # - DEVICE_CONNECTED.
    def set_state_change_callback(self, callback):
        self.state_change_callback = callback

    # Begin advertising the device services.
    def start_advertising(self):
        if self.device_state is not HumanInterfaceDevice.DEVICE_STOPPED and self.device_state is not HumanInterfaceDevice.DEVICE_ADVERTISING:
            self.adv.start_advertising()
            self.set_state(HumanInterfaceDevice.DEVICE_ADVERTISING)

    # Stop advertising the device services.
    def stop_advertising(self):
        if self.device_state is not HumanInterfaceDevice.DEVICE_STOPPED:
            self.adv.stop_advertising()
            if self.device_state is not HumanInterfaceDevice.DEVICE_CONNECTED:
                self.set_state(HumanInterfaceDevice.DEVICE_IDLE)

    # Returns the device name.
    def get_device_name(self):
        return self.device_name

    # Returns the service id's.
    def get_services_uuids(self):
        return self.service_uuids

    # Returns the device appearance.
    def get_appearance(self):
        return self.device_appearance

    # Returns the battery level (percentage).
    def get_battery_level(self):
        return self.battery_level

    # Sets the value for the battery level (percentage).
    def set_battery_level(self, level):
        if level > 100:
            self.battery_level = 100
        elif level < 0:
            self.battery_level = 0
        else:
            self.battery_level = level

    # Set device information.
    # Must be called before calling Start().
    # Variables must be Strings.
    def set_device_information(self, manufacture_name="Homebrew", model_number="1", serial_number="1"):
        self.manufacture_name = manufacture_name
        self.model_number = model_number
        self.serial_number = serial_number

    # Set device revision.
    # Must be called before calling Start().
    # Variables must be Strings.
    def set_device_revision(self, firmware_revision="1", hardware_revision="1", software_revision="1"):
        self.firmware_revision = firmware_revision
        self.hardware_revision = hardware_revision
        self.software_revision = software_revision

    # Set device pnp information.
    # Must be called before calling Start().
    # Must use the following format:
    #   pnp_manufacturer_source: 0x01 for manufacturers uuid from the Bluetooth uuid list OR 0x02 from the USBs id list.
    #   pnp_manufacturer_uuid: 0xFEB2 for Microsoft, 0xFE61 for Logitech, 0xFD65 for Razer with source 0x01.
    #   pnp_product_id: One byte, user defined.
    #   pnp_product_version: Two bytes, user defined, format as 0xJJMN which corresponds to version JJ.M.N.
    def set_device_pnp_information(self, pnp_manufacturer_source=0x01, pnp_manufacturer_uuid=0xFE61, pnp_product_id=0x01, pnp_product_version=0x0123):
        self.pnp_manufacturer_source = pnp_manufacturer_source
        self.pnp_manufacturer_uuid = pnp_manufacturer_uuid
        self.pnp_product_id = pnp_product_id
        self.pnp_product_version = pnp_product_version

    # Set whether to use Bluetooth bonding.
    def set_bonding(self, bond=True):
        self.bond = bond

    # Set whether to use LE secure pairing.
    def set_le_secure(self, le_secure=True):
        self.le_secure = le_secure

    # Set input/output capability of this device.
    # Determines the pairing procedure, e.g., accept connection/passkey entry/just works.
    # Must be called before calling Start().
    # Must use the following values:
    #   _IO_CAPABILITY_DISPLAY_ONLY,
    #   _IO_CAPABILITY_DISPLAY_YESNO,
    #   _IO_CAPABILITY_KEYBOARD_ONLY,
    #   _IO_CAPABILITY_NO_INPUT_OUTPUT, or
    #   _IO_CAPABILITY_KEYBOARD_DISPLAY.
    def set_io_capability(self, io_capability):
        self.io_capability = io_capability

    # Set callback function for pairing events.
    # Depending on the I/O capability used, the callback function should return either a
    # - boolean to accept or deny a connection, or a
    # - passkey that was displayed by the main.
    def set_passkey_callback(self, passkey_callback):
        self.passkey_callback = passkey_callback

    # Set the passkey used during pairing when entering a passkey at the main.
    def set_passkey(self, passkey):
        self.passkey = passkey

    # Notifies the client by writing to the battery level handle.
    def notify_battery_level(self):
        if self.is_connected():
            print("Notify battery level: ", self.battery_level)
            self._ble.gatts_notify(self.conn_handle, self.h_bat, struct.pack("<B", self.battery_level))

    # Notifies the client of the HID state.
    # Must be overwritten by subclass.
    def notify_hid_report(self):
        return

# Class that represents the Joystick service.
class Joystick(HumanInterfaceDevice):
    def __init__(self, name="Bluetooth Joystick"):
        super(Joystick, self).__init__(name)                                                                            # Set up the general HID services in super.
        self.device_appearance = 963                                                                                    # Overwrite the device appearance ID, 963 = joystick.

        self.HIDS = (                                                                                                   # HID service description: describes the service and how we communicate
            UUID(0x1812),                                                                                               # 0x1812 = Human Interface Device
            (
                (UUID(0x2A4A), F_READ),                                                                                 # 0x2A4A = HID information characteristic, to be read by client.
                (UUID(0x2A4B), F_READ),                                                                                 # 0x2A4B = HID USB report map, to be read by client.
                (UUID(0x2A4C), F_READ_WRITE_NORESPONSE),                                                                # 0x2A4C = HID control point, to be written by client.
                (UUID(0x2A4D), F_READ_NOTIFY, (                                                                         # 0x2A4D = HID report, to be read by client after notification.
                    (UUID(0x2902), ATT_F_READ_WRITE),                                                                   # 0x2902 = Client Characteristic Configuration.
                    (UUID(0x2908), F_READ_WRITE_NORESPONSE),                                                            # 0x2908 = HID reference, to be read by client (allow write because MicroPython v1.20+ bug).
                )),
                (UUID(0x2A4E), F_READ_WRITE_NORESPONSE),                                                                # 0x2A4E = HID protocol mode, to be written & read by client.
            ),
        )

        # fmt: off
        self.HID_INPUT_REPORT = bytes([                                                                                 # USB Report Description: describes what we communicate.
            0x05, 0x01,                                                                                                 # USAGE_PAGE (Generic Desktop)
            0x09, 0x04,                                                                                                 # USAGE (Joystick)
            0xa1, 0x01,                                                                                                 # COLLECTION (Application)
            0x85, 0x01,                                                                                                 #   REPORT_ID (1)
            0xa1, 0x00,                                                                                                 #   COLLECTION (Physical)
            0x09, 0x30,                                                                                                 #     USAGE (X)
            0x09, 0x31,                                                                                                 #     USAGE (Y)
            0x15, 0x81,                                                                                                 #     LOGICAL_MINIMUM (-127)
            0x25, 0x7f,                                                                                                 #     LOGICAL_MAXIMUM (127)
            0x75, 0x08,                                                                                                 #     REPORT_SIZE (8)
            0x95, 0x02,                                                                                                 #     REPORT_COUNT (2)
            0x81, 0x02,                                                                                                 #     INPUT (Data,Var,Abs)
            0x05, 0x09,                                                                                                 #     USAGE_PAGE (Button)
            0x29, 0x08,                                                                                                 #     USAGE_MAXIMUM (Button 8)
            0x19, 0x01,                                                                                                 #     USAGE_MINIMUM (Button 1)
            0x95, 0x08,                                                                                                 #     REPORT_COUNT (8)
            0x75, 0x01,                                                                                                 #     REPORT_SIZE (1)
            0x25, 0x01,                                                                                                 #     LOGICAL_MAXIMUM (1)
            0x15, 0x00,                                                                                                 #     LOGICAL_MINIMUM (0)
            0x81, 0x02,                                                                                                 #     Input (Data, Variable, Absolute)
            0xc0,                                                                                                       #   END_COLLECTION
            0xc0                                                                                                        # END_COLLECTION
        ])
        # fmt: on

        # Define the initial joystick state.
        self.x = 0
        self.y = 0

        self.button1 = 0
        self.button2 = 0
        self.button3 = 0
        self.button4 = 0
        self.button5 = 0
        self.button6 = 0
        self.button7 = 0
        self.button8 = 0

        self.services = [self.DIS, self.BAS, self.HIDS]                                                                 # Overwrite list of service descriptions.

    # Overwrite super to register HID specific service.
    def start(self):
        super(Joystick, self).start()                                                                                   # Start super to register DIS and BAS services.

        print("Registering services")
        handles = self._ble.gatts_register_services(self.services)                                                      # Register services and get read/write handles for all services.
        self.write_service_characteristics(handles)                                                                     # Write the values for the characteristics.
        self.adv = Advertiser(self._ble, [UUID(0x1812)], self.device_appearance, self.device_name)                      # Create an Advertiser. Only advertise the top level service, i.e., the HIDS.
        print("Server started")

    # Overwrite super to write HID specific characteristics.
    def write_service_characteristics(self, handles):
        super(Joystick, self).write_service_characteristics(handles)                                                    # Call super to write DIS and BAS characteristics.

        (h_info, h_hid, _, self.h_rep, _, h_d1, h_proto) = handles[2]                                                   # Get the handles for the HIDS characteristics. These correspond directly to self.HIDS. Position 2 because of the order of self.services.

        b = self.button1 + self.button2 * 2 + self.button3 * 4 + self.button4 * 8 + self.button5 * 16 + self.button6 * 32 + self.button7 * 64 + self.button8 * 128
        state = struct.pack("bbB", self.x, self.y, b)                                                                   # Pack the initial joystick state as described by the input report.

        print("Writing hid service characteristics")
        # Write service characteristics
        self._ble.gatts_write(h_info, b"\x01\x01\x00\x02")                                                              # HID info: ver=1.1, country=0, flags=normal.
        self._ble.gatts_write(h_hid, self.HID_INPUT_REPORT)                                                             # HID input report map.
        self._ble.gatts_write(self.h_rep, state)                                                                        # HID report.
        self._ble.gatts_write(h_d1, struct.pack("<BB", 1, 1))                                                           # HID reference: id=1, type=input.
        self._ble.gatts_write(h_proto, b"\x01")                                                                         # HID protocol mode: report.

    # Overwrite super to notify central of a hid report.
    def notify_hid_report(self):
        if self.is_connected():
            b = self.button1 + self.button2 * 2 + self.button3 * 4 + self.button4 * 8 + self.button5 * 16 + self.button6 * 32 + self.button7 * 64 + self.button8 * 128
            state = struct.pack("bbB", self.x, self.y, b)                                                               # Pack the joystick state as described by the input report.
            self._ble.gatts_notify(self.conn_handle, self.h_rep, state)                                                 # Notify client by writing to the report handle.
            print("Notify with report: ", struct.unpack("bbB", state))

    # Set the joystick axes values.
    def set_axes(self, x=0, y=0):
        if x > 127:
            x = 127
        elif x < -127:
            x = -127

        if y > 127:
            y = 127
        elif y < -127:
            y = -127

        self.x = x
        self.y = y

    # Set the joystick button values.
    def set_buttons(self, b1=0, b2=0, b3=0, b4=0, b5=0, b6=0, b7=0, b8=0):
        self.button1 = b1
        self.button2 = b2
        self.button3 = b3
        self.button4 = b4
        self.button5 = b5
        self.button6 = b6
        self.button7 = b7
        self.button8 = b8

# Class that represents the Mouse service.
class Mouse(HumanInterfaceDevice):
    def __init__(self, name="Bluetooth Mouse"):
        super(Mouse, self).__init__(name)                                                                               # Set up the general HID services in super.
        self.device_appearance = 962                                                                                    # Device appearance ID, 962 = mouse.

        self.HIDS = (                                                                                                   # Service description: describes the service and how we communicate.
            UUID(0x1812),                                                                                               # 0x1812 = Human Interface Device.
            (
                (UUID(0x2A4A), F_READ),                                                                                 # 0x2A4A = HID information, to be read by client.
                (UUID(0x2A4B), F_READ),                                                                                 # 0x2A4B = HID report map, to be read by client.
                (UUID(0x2A4C), F_READ_WRITE_NORESPONSE),                                                                # 0x2A4C = HID control point, to be written by client.
                (UUID(0x2A4D), F_READ_NOTIFY, (                                                                         # 0x2A4D = HID report, to be read by client after notification.
                    (UUID(0x2902), ATT_F_READ_WRITE),                                                                   # 0x2902 = Client Characteristic Configuration.
                    (UUID(0x2908), F_READ_WRITE_NORESPONSE),                                                            # 0x2908 = HID reference, to be read by client (allow write because MicroPython v1.20+ bug).
                )),
                (UUID(0x2A4E), F_READ_WRITE_NORESPONSE),                                                                # 0x2A4E = HID protocol mode, to be written & read by client.
            ),
        )

        # fmt: off
        self.HID_INPUT_REPORT = bytes([                                                                                 # Report Description: describes what we communicate.
            0x05, 0x01,                                                                                                 # USAGE_PAGE (Generic Desktop)
            0x09, 0x02,                                                                                                 # USAGE (Mouse)
            0xa1, 0x01,                                                                                                 # COLLECTION (Application)
            0x85, 0x01,                                                                                                 #   REPORT_ID (1)
            0x09, 0x01,                                                                                                 #   USAGE (Pointer)
            0xa1, 0x00,                                                                                                 #   COLLECTION (Physical)
            0x05, 0x09,                                                                                                 #         Usage Page (Buttons)
            0x19, 0x01,                                                                                                 #         Usage Minimum (1)
            0x29, 0x03,                                                                                                 #         Usage Maximum (3)
            0x15, 0x00,                                                                                                 #         Logical Minimum (0)
            0x25, 0x01,                                                                                                 #         Logical Maximum (1)
            0x95, 0x03,                                                                                                 #         Report Count (3)
            0x75, 0x01,                                                                                                 #         Report Size (1)
            0x81, 0x02,                                                                                                 #         Input(Data, Variable, Absolute); 3 button bits
            0x95, 0x01,                                                                                                 #         Report Count(1)
            0x75, 0x05,                                                                                                 #         Report Size(5)
            0x81, 0x03,                                                                                                 #         Input(Constant);                 5 bit padding
            0x05, 0x01,                                                                                                 #         Usage Page (Generic Desktop)
            0x09, 0x30,                                                                                                 #         Usage (X)
            0x09, 0x31,                                                                                                 #         Usage (Y)
            0x09, 0x38,                                                                                                 #         Usage (Wheel)
            0x15, 0x81,                                                                                                 #         Logical Minimum (-127)
            0x25, 0x7F,                                                                                                 #         Logical Maximum (127)
            0x75, 0x08,                                                                                                 #         Report Size (8)
            0x95, 0x03,                                                                                                 #         Report Count (3)
            0x81, 0x06,                                                                                                 #         Input(Data, Variable, Relative); 3 position bytes (X,Y,Wheel)
            0xc0,                                                                                                       #   END_COLLECTION
            0xc0                                                                                                        # END_COLLECTION
        ])
        # fmt: on

        # Define the initial mouse state.
        self.x = 0
        self.y = 0
        self.w = 0

        self.button1 = 0
        self.button2 = 0
        self.button3 = 0

        self.services = [self.DIS, self.BAS, self.HIDS]                                                                 # Override list of service descriptions.

    # Overwrite super to register HID specific service.
    def start(self):
        super(Mouse, self).start()                                                                                      # Call super to register DIS and BAS services.

        print("Registering services")
        handles = self._ble.gatts_register_services(self.services)                                                      # Register services and get read/write handles for all services.
        self.write_service_characteristics(handles)                                                                     # Write the values for the characteristics.
        self.adv = Advertiser(self._ble, [UUID(0x1812)], self.device_appearance, self.device_name)                      # Create an Advertiser. Only advertise the top level service, i.e., the HIDS.

        print("Server started")

    # Overwrite super to write HID specific characteristics.
    def write_service_characteristics(self, handles):
        super(Mouse, self).write_service_characteristics(handles)                                                       # Call super to write DIS and BAS characteristics.

        (h_info, h_hid, h_ctrl, self.h_rep, _, h_d1, h_proto) = handles[2]                                              # Get the handles for the HIDS characteristics. These correspond directly to self.HIDS. Position 2 because of the order of self.services.
        print("h_info =", h_info, "h_hid =", h_hid, "h_ctrl =", h_ctrl, "h_rep =", self.h_rep, "h_d1ref =", h_d1, "h_proto =", h_proto)

        b = self.button1 + self.button2 * 2 + self.button3 * 4
        state = struct.pack("Bbbb", b, self.x, self.y, self.w)                                                          # Pack the initial mouse state as described by the input report.

        print("Writing hid service characteristics")
        # Write service characteristics.
        self._ble.gatts_write(h_info, b"\x01\x01\x00\x02")                                                              # HID info: ver=1.1, country=0, flags=normal.
        self._ble.gatts_write(h_hid, self.HID_INPUT_REPORT)                                                             # HID input report map.
        self._ble.gatts_write(self.h_rep, state)                                                                        # HID report.
        self._ble.gatts_write(h_d1, struct.pack("<BB", 1, 1))                                                           # HID reference: id=1, type=input.
        self._ble.gatts_write(h_proto, b"\x01")                                                                         # HID protocol mode: report.

    # Overwrite super to notify central of a hid report
    def notify_hid_report(self):
        if self.is_connected():
            b = self.button1 + self.button2 * 2 + self.button3
            state = struct.pack("Bbbb", b, self.x, self.y, self.w)                                                      # Pack the mouse state as described by the input report.
            self._ble.gatts_notify(self.conn_handle, self.h_rep, state)                                                 # Notify central by writing to the report handle.
            print("Notify with report: ", struct.unpack("Bbbb", state))

    # Set the mouse axes values.
    def set_axes(self, x=0, y=0):
        if x > 127:
            x = 127
        elif x < -127:
            x = -127

        if y > 127:
            y = 127
        elif y < -127:
            y = -127

        self.x = x
        self.y = y

    # Set the mouse scroll wheel value.
    def set_wheel(self, w=0):
        if w > 127:
            w = 127
        elif w < -127:
            w = -127

        self.w = w

    # Set the mouse button values.
    def set_buttons(self, b1=0, b2=0, b3=0):
        self.button1 = b1
        self.button2 = b2
        self.button3 = b3

# Class that represents the Keyboard service.
class Keyboard(HumanInterfaceDevice):
    def __init__(self, name="Bluetooth Keyboard"):
        super(Keyboard, self).__init__(name)                                                                            # Set up the general HID services in super.
        self.device_appearance = 961                                                                                    # Device appearance ID, 961 = keyboard.

        self.HIDS = (                                                                                                   # Service description: describes the service and how we communicate.
            UUID(0x1812),                                                                                               # Human Interface Device.
            (
                (UUID(0x2A4A), F_READ),                                                                                 # 0x2A4A = HID information, to be read by client.
                (UUID(0x2A4B), F_READ),                                                                                 # 0x2A4B = HID report map, to be read by client.
                (UUID(0x2A4C), F_READ_WRITE_NORESPONSE),                                                                # 0x2A4C = HID control point, to be written by client.
                (UUID(0x2A4D), F_READ_NOTIFY, (                                                                         # 0x2A4D = HID report, to be read by client after notification.
                    (UUID(0x2902), ATT_F_READ_WRITE),                                                                   # 0x2902 = Client Characteristic Configuration.
                    (UUID(0x2908), F_READ_WRITE_NORESPONSE),                                                            # 0x2908 = HID reference, to be read by client (allow write because MicroPython v1.20+ bug).
                )),
                (UUID(0x2A4D), F_READ_WRITE, ((UUID(0x2908), F_READ),)),                                                # 0x2A4D = HID report / 0x2908 = reference, to be read & written by client / to be read by client.
                (UUID(0x2A4E), F_READ_WRITE_NORESPONSE),                                                                # 0x2A4E = HID protocol mode, to be written & read by client.
            ),
        )

        # fmt: off
        self.HID_INPUT_REPORT = bytes([                                                                                 # Report Description: describes what we communicate.
            0x05, 0x01,                                                                                                 # USAGE_PAGE (Generic Desktop)
            0x09, 0x06,                                                                                                 # USAGE (Keyboard)
            0xa1, 0x01,                                                                                                 # COLLECTION (Application)
            0x85, 0x01,                                                                                                 #     REPORT_ID (1)
            0x75, 0x01,                                                                                                 #     Report Size (1)
            0x95, 0x08,                                                                                                 #     Report Count (8)
            0x05, 0x07,                                                                                                 #     Usage Page (Key Codes)
            0x19, 0xE0,                                                                                                 #     Usage Minimum (224)
            0x29, 0xE7,                                                                                                 #     Usage Maximum (231)
            0x15, 0x00,                                                                                                 #     Logical Minimum (0)
            0x25, 0x01,                                                                                                 #     Logical Maximum (1)
            0x81, 0x02,                                                                                                 #     Input (Data, Variable, Absolute); Modifier byte
            0x95, 0x01,                                                                                                 #     Report Count (1)
            0x75, 0x08,                                                                                                 #     Report Size (8)
            0x81, 0x01,                                                                                                 #     Input (Constant); Reserved byte
            0x95, 0x05,                                                                                                 #     Report Count (5)
            0x75, 0x01,                                                                                                 #     Report Size (1)
            0x05, 0x08,                                                                                                 #     Usage Page (LEDs)
            0x19, 0x01,                                                                                                 #     Usage Minimum (1)
            0x29, 0x05,                                                                                                 #     Usage Maximum (5)
            0x91, 0x02,                                                                                                 #     Output (Data, Variable, Absolute); LED report
            0x95, 0x01,                                                                                                 #     Report Count (1)
            0x75, 0x03,                                                                                                 #     Report Size (3)
            0x91, 0x01,                                                                                                 #     Output (Constant); LED report padding
            0x95, 0x06,                                                                                                 #     Report Count (6)
            0x75, 0x08,                                                                                                 #     Report Size (8)
            0x15, 0x00,                                                                                                 #     Logical Minimum (0)
            0x25, 0x65,                                                                                                 #     Logical Maximum (101)
            0x05, 0x07,                                                                                                 #     Usage Page (Key Codes)
            0x19, 0x00,                                                                                                 #     Usage Minimum (0)
            0x29, 0x65,                                                                                                 #     Usage Maximum (101)
            0x81, 0x00,                                                                                                 #     Input (Data, Array); Key array (6 bytes)
            0xc0                                                                                                        # END_COLLECTION
        ])
        # fmt: on

        # Define the initial keyboard state.
        self.modifiers = 0                                                                                              # 8 bits signifying Right GUI(Win/Command), Right ALT/Option, Right Shift, Right Control, Left GUI, Left ALT, Left Shift, Left Control.
        self.keypresses = [0x00] * 6                                                                                    # 6 keys to hold.

        self.kb_callback = None                                                                                         # Callback function for keyboard messages from client.

        self.services = [self.DIS, self.BAS, self.HIDS]                                                                 # Override list of service descriptions.

    # Interrupt request callback function
    # Overwrite super to catch keyboard report write events by the central.
    def ble_irq(self, event, data):
        if event == _IRQ_GATTS_WRITE:                                                                                   # If a client has written to a characteristic or descriptor.
            print("Keyboard changed by Central")
            conn_handle, attr_handle = data                                                                             # Get the handle to the characteristic that was written.
            report = self._ble.gatts_read(attr_handle)                                                                  # Read the report.
            bytes = struct.unpack("B", report)                                                                          # Unpack the report.
            if self.kb_callback is not None:                                                                            # Call the callback function.
                self.kb_callback(bytes)
        else:                                                                                                           # Else let super handle the event.
            super(Keyboard, self).ble_irq(event, data)

    # Overwrite super to register HID specific service.
    def start(self):
        super(Keyboard, self).start()                                                                                   # Call super to register DIS and BAS services.

        print("Registering services")
        handles = self._ble.gatts_register_services(self.services)                                                      # Register services and get read/write handles for all services.
        self.write_service_characteristics(handles)                                                                     # Write the values for the characteristics.
        self.adv = Advertiser(self._ble, [UUID(0x1812)], self.device_appearance, self.device_name)                      # Create an Advertiser. Only advertise the top level service, i.e., the HIDS.
        print("Server started")

    # Overwrite super to write HID specific characteristics.
    def write_service_characteristics(self, handles):
        super(Keyboard, self).write_service_characteristics(handles)                                                    # Call super to write DIS and BAS characteristics.

        (h_info, h_hid, _, self.h_rep, _, h_d1, self.h_repout, h_d2, h_proto) = handles[2]                              # Get the handles for the HIDS characteristics. These correspond directly to self.HIDS. Position 2 because of the order of self.services.

        print("Writing hid service characteristics")
        # Write service characteristics
        self._ble.gatts_write(h_info, b"\x01\x01\x00\x02")                                                              # HID info: ver=1.1, country=0, flags=normal.
        self._ble.gatts_write(h_hid, self.HID_INPUT_REPORT)                                                             # HID input report map.
        self._ble.gatts_write(h_d1, struct.pack("<BB", 1, 1))                                                           # HID reference: id=1, type=input.
        self._ble.gatts_write(h_d2, struct.pack("<BB", 1, 2))                                                           # HID reference: id=1, type=output.
        self._ble.gatts_write(h_proto, b"\x01")                                                                         # HID protocol mode: report.

    # Overwrite super to notify central of a hid report.
    def notify_hid_report(self):
        if self.is_connected():
            # Pack the Keyboard state as described by the input report.
            state = struct.pack("8B", self.modifiers, 0, self.keypresses[0], self.keypresses[1], self.keypresses[2], self.keypresses[3], self.keypresses[4], self.keypresses[5])
            self._ble.gatts_notify(self.conn_handle, self.h_rep, state)                                                 # Notify central by writing to the report handle.
            print("Notify with report: ", struct.unpack("8B", state))

    # Set the modifier bits, notify to send the modifiers to central.
    def set_modifiers(self, right_gui=0, right_alt=0, right_shift=0, right_control=0, left_gui=0, left_alt=0, left_shift=0, left_control=0):
        self.modifiers = (right_gui << 7) + (right_alt << 6) + (right_shift << 5) + (right_control << 4) + (left_gui << 3) + (left_alt << 2) + (left_shift << 1) + left_control

    # Press keys, notify to send the keys to central.
    # This will hold down the keys, call set_keys() without arguments and notify again to release.
    def set_keys(self, k0=0x00, k1=0x00, k2=0x00, k3=0x00, k4=0x00, k5=0x00):
        self.keypresses = [k0, k1, k2, k3, k4, k5]

    # Set a callback function that gets notified on keyboard changes.
    # Should take a tuple with the report bytes.
    def set_kb_callback(self, kb_callback):
        self.kb_callback = kb_callback
