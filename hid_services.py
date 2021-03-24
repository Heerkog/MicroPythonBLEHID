from micropython import const
import struct
import bluetooth
from bluetooth import UUID

F_READ = bluetooth.FLAG_READ
F_WRITE = bluetooth.FLAG_WRITE
F_READ_WRITE = bluetooth.FLAG_READ | bluetooth.FLAG_WRITE
F_READ_NOTIFY = bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY

ATT_F_READ = 0x01
ATT_F_WRITE = 0x02

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

DEVICE_STOPPED = const(0)
DEVICE_IDLE = const(1)
DEVICE_ADVERTISING = const(2)
DEVICE_CONNECTED = const(3)

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

    # Init as generic HID device (960 = generic HID appearance value)
    def __init__(self, ble, services=[UUID(0x1812)], appearance=const(960), name="Generic HID Device"):
        self._ble = ble
        self._payload = self.advertising_payload(name=name, services=services, appearance=appearance)
        print(self._payload)
        print(self.decode_name(self._payload))
        print(self.decode_services(self._payload))
        self.advertising = False
        print("Advertiser created")

    # Start advertising at 100000 interval
    def start_advertising(self):
        if not self.advertising:
            self._ble.gap_advertise(100000, adv_data=self._payload)
            print("Started advertising")

    # Stop advertising by setting interval of 0
    def stop_advertising(self):
        if self.advertising:
            self._ble.gap_advertise(0, adv_data=self._payload)
            print("Stopped advertising")


# Class that represents a general HID device state
class HumanInterfaceDevice(object):

    def __init__(self, device_name="Generic HID Device"):
        self._ble = bluetooth.BLE()
        self.adv = None
        self.device_state = DEVICE_STOPPED
        self.conn_handle = None
        self.state_change_callback = None

        print("Server created")

        self.device_name = device_name
        self.service_uuids = [UUID(0x180A), UUID(0x180F), UUID(0x1812)]  # Service UUIDs: DIS, BAS, HIDS
        self.device_appearance = 960                                     # Generic HID Appearance
        self.battery_level = 100

        self.DIS = (                            # Device Information Service description
            UUID(0x180A),                       # Device Information
            (
                (UUID(0x2A50), F_READ),         # PnP ID
            ),
        )
        self.BAS = (                            # Battery Service description
            UUID(0x180F),                       # Device Information
            (
                (UUID(0x2A19), F_READ_NOTIFY),  # Battery level
            ),
        )

        self.services = [self.DIS, self.BAS]    # List of service descriptions, append HIDS

        self.HID_INPUT_REPORT = None

    def ble_irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            self.conn_handle, _, _ = data
            print("Central connected: ", self.conn_handle)
            self.set_state(DEVICE_CONNECTED)
        elif event == _IRQ_CENTRAL_DISCONNECT:
            self.conn_handle = None
            print("Central disconnected")
            self.set_state(DEVICE_IDLE)
        elif event == _IRQ_MTU_EXCHANGED:
            print("MTU exchanged")
        elif event == _IRQ_CONNECTION_UPDATE:
            self.conn_handle, _, _, _, _ = data
            print("Connection update")
        else:
            print("Unhandled IRQ event: ", event)

    def start(self):
        if self.device_state is DEVICE_STOPPED:
            self._ble.active(1)
            self._ble.irq(self.ble_irq)
            self._ble.config(gap_name=self.device_name)

            self.set_state(DEVICE_IDLE)
            print("BLE on")

    def write_service_characteristics(self, handles):
        print("Writing service characteristics")

        (h_pnp,) = handles[0]
        (self.h_bat,) = handles[1]

        # Write service data

        print("Writing device information service characteristics")
        # PnP id: source: BT, vendor: Microsoft, product id: 1, version 0.0.1
        # self._ble.gatts_write(h_pnp, b"\x01\xFE\xB2\x00\x01\x00\x01")
        self._ble.gatts_write(h_pnp, struct.pack("<6B", 0x01, 0xFEB2, 1, 0x01, 0x01))

        print("Writing battery service characteristics")
        # Battery level
        self._ble.gatts_write(self.h_bat, struct.pack("<B", self.battery_level))

    def stop(self):
        if self.device_state is not DEVICE_STOPPED:
            if self.device_state is DEVICE_ADVERTISING:
                self.adv.stop_advertising()
            self._ble.active(0)

            self.set_state(DEVICE_STOPPED)
            print("Server stopped")

    def is_running(self):
        return self.device_state is not DEVICE_STOPPED

    def is_connected(self):
        return self.device_state is DEVICE_CONNECTED

    def is_advertising(self):
        return self.device_state is DEVICE_ADVERTISING

    def set_state(self, state):
        self.device_state = state
        if self.state_change_callback is not None:
            self.state_change_callback()

    def get_state(self):
        return self.device_state

    def set_state_change_callback(self, callback):
        self.state_change_callback = callback

    def start_advertising(self):
        if self.device_state is not DEVICE_STOPPED and self.device_state is not DEVICE_ADVERTISING:
            self.adv.start_advertising()
            self.set_state(DEVICE_ADVERTISING)

    def stop_advertising(self):
        if self.device_state is not DEVICE_STOPPED:
            self.adv.stop_advertising()
            if self.device_state is not DEVICE_CONNECTED:
                self.set_state(DEVICE_IDLE)

    def get_device_name(self):
        return self.device_name

    def get_services_uuids(self):
        return self.service_uuids

    def get_appearance(self):
        return self.device_appearance

    def get_battery_level(self):
        return self.battery_level

    def set_battery_level(self, level):
        if level > 100:
            self.battery_level = 100
        elif level < 0:
            self.battery_level = 0
        else:
            self.battery_level = level

    def notify_battery_level(self):
        if self.is_connected():
            print("Notify battery level: ", self.battery_level)
            self._ble.gatts_notify(self.conn_handle, self.h_bat, struct.pack("<B", self.battery_level))

    def notify_hid_report(self):
        return

# Class that represents the Joystick state
class Joystick(HumanInterfaceDevice):
    def __init__(self, name="Bluetooth Joystick"):
        super(Joystick, self).__init__(name)
        self.device_appearance = 963  # Device appearance ID, 963 = joystick

        self.HIDS = (  # Service description: describes the service and how we communicate
            UUID(0x1812),  # Human Interface Device
            (
                (UUID(0x2A4A), F_READ),  # HID information
                (UUID(0x2A4B), F_READ),  # HID report map
                (UUID(0x2A4C), F_WRITE),  # HID control point
                (UUID(0x2A4D), F_READ_NOTIFY, ((UUID(0x2908), ATT_F_READ),)),  # HID report / reference
                (UUID(0x2A4E), F_READ_WRITE),  # HID protocol mode
            ),
        )

        # fmt: off
        self.HID_INPUT_REPORT = bytes([    # Report Description: describes what we communicate
            0x05, 0x01,                    # USAGE_PAGE (Generic Desktop)
            0x09, 0x04,                    # USAGE (Joystick)
            0xa1, 0x01,                    # COLLECTION (Application)
            0x85, 0x01,                    #   REPORT_ID (1)
            0xa1, 0x00,                    #   COLLECTION (Physical)
            0x09, 0x30,                    #     USAGE (X)
            0x09, 0x31,                    #     USAGE (Y)
            0x15, 0x81,                    #     LOGICAL_MINIMUM (-127)
            0x25, 0x7f,                    #     LOGICAL_MAXIMUM (127)
            0x75, 0x08,                    #     REPORT_SIZE (8)
            0x95, 0x02,                    #     REPORT_COUNT (2)
            0x81, 0x02,                    #     INPUT (Data,Var,Abs)
            0x05, 0x09,                    #     USAGE_PAGE (Button)
            0x29, 0x08,                    #     USAGE_MAXIMUM (Button 8)
            0x19, 0x01,                    #     USAGE_MINIMUM (Button 1)
            0x95, 0x08,                    #     REPORT_COUNT (8)
            0x75, 0x01,                    #     REPORT_SIZE (1)
            0x25, 0x01,                    #     LOGICAL_MAXIMUM (1)
            0x15, 0x00,                    #     LOGICAL_MINIMUM (0)
            0x81, 0x02,                    #     Input (Data, Variable, Absolute)
            0xc0,                          #   END_COLLECTION
            0xc0                           # END_COLLECTION
        ])
        # fmt: on

        # Define the initial joystick state
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

        self.services = [self.DIS, self.BAS, self.HIDS]  # List of service descriptions

    def start(self):
        super(Joystick, self).start()

        print("Registering services")
        # Register services and get read/write handles
        handles = self._ble.gatts_register_services(self.services)
        self.write_service_characteristics(handles)

        # self.adv = Advertiser(self._ble, self.SERVICE_UUIDS, self.DEV_APPEARANCE, self.DEV_NAME)
        self.adv = Advertiser(self._ble, [UUID(0x1812)], self.device_appearance, self.device_name)

        print("Server started")

    def write_service_characteristics(self, handles):
        super(Joystick, self).write_service_characteristics(handles)

        # Get the handles from the hids, the third service
        (h_info, h_hid, _, self.h_rep, h_d1, h_proto,) = handles[2]

        # Pack the initial joystick state as described by the input report
        b = self.button1 + self.button2 * 2 + self.button3 * 3 + self.button4 * 4
        state = struct.pack("bbB", self.x, self.y, b)

        print("Writing hid service characteristics")
        # Write service characteristics
        self._ble.gatts_write(h_info, b"\x01\x01\x00\x02")     # HID info: ver=1.1, country=0, flags=normal
        self._ble.gatts_write(h_hid, self.HID_INPUT_REPORT)    # HID input report map
        self._ble.gatts_write(self.h_rep, state)               # HID report
        self._ble.gatts_write(h_d1, struct.pack("<BB", 1, 1))  # HID reference: id=1, type=input
        self._ble.gatts_write(h_proto, b"\x01")                # HID protocol mode: report

    def notify_hid_report(self):
        if self.is_connected():
            # Pack the joystick state as described by the input report
            b = self.button1 + self.button2 * 2 + self.button3 * 4 + self.button4 * 8 + self.button5 * 16 + self.button6 * 32 + self.button7 * 64 + self.button8 * 128
            state = struct.pack("bbB", self.x, self.y, b)

            print("Notify with report: ", struct.unpack("bbB", state))

            self._ble.gatts_notify(self.conn_handle, self.h_rep, state)

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

    def set_buttons(self, b1=0, b2=0, b3=0, b4=0, b5=0, b6=0, b7=0, b8=0):
        self.button1 = b1
        self.button2 = b2
        self.button3 = b3
        self.button4 = b4
        self.button5 = b5
        self.button6 = b6
        self.button7 = b7
        self.button8 = b8


