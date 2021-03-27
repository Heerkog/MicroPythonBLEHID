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


# Class that represents a general HID device services
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

    # Interrupt request callback function
    def ble_irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:        # Central connected
            self.conn_handle, _, _ = data        # Save the handle
            print("Central connected: ", self.conn_handle)
            self.set_state(DEVICE_CONNECTED)     # (HIDS specification only allow one central to be connected)
        elif event == _IRQ_CENTRAL_DISCONNECT:   # Central disconnected
            self.conn_handle = None              # Discard old handle
            print("Central disconnected")
            self.set_state(DEVICE_IDLE)
        elif event == _IRQ_MTU_EXCHANGED:        # MTU was set
            print("MTU exchanged")
        elif event == _IRQ_CONNECTION_UPDATE:    # Connection parameters were updated
            self.conn_handle, _, _, _, _ = data  # The new parameters
            print("Connection update")
        else:
            print("Unhandled IRQ event: ", event)

    # Start the service
    # Must be overwritten by subclass, and called in
    # the overwritten function by using super(Subclass, self).start()
    def start(self):
        if self.device_state is DEVICE_STOPPED:
            # Turn on BLE radio
            self._ble.active(1)
            # Set interrupt request callback function
            self._ble.irq(self.ble_irq)
            # Set GAP device name
            self._ble.config(gap_name=self.device_name)

            self.set_state(DEVICE_IDLE)
            print("BLE on")

    # After registering the DIS and BAS services, write their characteristic values
    # Must be overwritten by subclass, and called in
    # the overwritten function by using
    # super(Subclass, self).write_service_characteristics(handles)
    def write_service_characteristics(self, handles):
        print("Writing service characteristics")

        # Get handles to service characteristics
        # These correspond directly to self.DIS and sel.BAS
        (h_pnp,) = handles[0]
        (self.h_bat,) = handles[1]

        # Write service characteristics
        print("Writing device information service characteristics")
        # PnP id: source: BT, vendor: Microsoft, product id: 1, version 0.0.1
        self._ble.gatts_write(h_pnp, struct.pack("<6B", 0x01, 0xFEB2, 1, 0x01, 0x01))

        print("Writing battery service characteristics")
        # Battery level
        self._ble.gatts_write(self.h_bat, struct.pack("<B", self.battery_level))

    # Stop the service
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

    # Set a new state and notify the user's callback function
    def set_state(self, state):
        self.device_state = state
        if self.state_change_callback is not None:
            self.state_change_callback()

    def get_state(self):
        return self.device_state

    # Set a callback function to get notifications of state changes, i.e.
    # - Device stopped
    # - Device idle
    # - Device advertising
    # - Device connected
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

    # Sets the value for the battery level
    def set_battery_level(self, level):
        if level > 100:
            self.battery_level = 100
        elif level < 0:
            self.battery_level = 0
        else:
            self.battery_level = level

    # Notifies the central by writing to the battery level handle
    def notify_battery_level(self):
        if self.is_connected():
            print("Notify battery level: ", self.battery_level)
            self._ble.gatts_notify(self.conn_handle, self.h_bat, struct.pack("<B", self.battery_level))

    # Notifies the central of the HID state
    # Must be overwritten by subclass
    def notify_hid_report(self):
        return

# Class that represents the Joystick service
class Joystick(HumanInterfaceDevice):
    def __init__(self, name="Bluetooth Joystick"):
        super(Joystick, self).__init__(name)  # Set up the general HID services in super
        self.device_appearance = 963          # Device appearance ID, 963 = joystick

        self.HIDS = (                         # Service description: describes the service and how we communicate
            UUID(0x1812),                     # Human Interface Device
            (
                (UUID(0x2A4A), F_READ),       # HID information
                (UUID(0x2A4B), F_READ),       # HID report map
                (UUID(0x2A4C), F_WRITE),      # HID control point
                (UUID(0x2A4D), F_READ_NOTIFY, ((UUID(0x2908), ATT_F_READ),)),  # HID report / reference
                (UUID(0x2A4E), F_READ_WRITE), # HID protocol mode
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

    # Overwrite super to register HID specific service
    # Call super to register DIS and BAS services
    def start(self):
        super(Joystick, self).start()  # Start super

        print("Registering services")
        # Register services and get read/write handles for all services
        handles = self._ble.gatts_register_services(self.services)
        # Write the values for the characteristics
        self.write_service_characteristics(handles)

        # Create an Advertiser
        # Only advertise the top level service, i.e., the HIDS
        self.adv = Advertiser(self._ble, [UUID(0x1812)], self.device_appearance, self.device_name)

        print("Server started")

    # Overwrite super to write HID specific characteristics
    # Call super to write DIS and BAS characteristics
    def write_service_characteristics(self, handles):
        super(Joystick, self).write_service_characteristics(handles)

        # Get the handles from the hids, the third service after DIS and BAS
        # These correspond directly to self.HIDS
        (h_info, h_hid, _, self.h_rep, h_d1, h_proto,) = handles[2]

        # Pack the initial joystick state as described by the input report
        b = self.button1 + self.button2 * 2 + self.button3 * 4 + self.button4 * 8 + self.button5 * 16 + self.button6 * 32 + self.button7 * 64 + self.button8 * 128
        state = struct.pack("bbB", self.x, self.y, b)

        print("Writing hid service characteristics")
        # Write service characteristics
        self._ble.gatts_write(h_info, b"\x01\x01\x00\x02")     # HID info: ver=1.1, country=0, flags=normal
        self._ble.gatts_write(h_hid, self.HID_INPUT_REPORT)    # HID input report map
        self._ble.gatts_write(self.h_rep, state)               # HID report
        self._ble.gatts_write(h_d1, struct.pack("<BB", 1, 1))  # HID reference: id=1, type=input
        self._ble.gatts_write(h_proto, b"\x01")                # HID protocol mode: report

    # Overwrite super to notify central of a hid report
    def notify_hid_report(self):
        if self.is_connected():
            # Pack the joystick state as described by the input report
            b = self.button1 + self.button2 * 2 + self.button3 * 4 + self.button4 * 8 + self.button5 * 16 + self.button6 * 32 + self.button7 * 64 + self.button8 * 128
            state = struct.pack("bbB", self.x, self.y, b)

            print("Notify with report: ", struct.unpack("bbB", state))
            # Notify central by writing to the report handle
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

# Class that represents the Mouse service
class Mouse(HumanInterfaceDevice):
    def __init__(self, name="Bluetooth Mouse"):
        super(Mouse, self).__init__(name)     # Set up the general HID services in super
        self.device_appearance = 962          # Device appearance ID, 962 = mouse

        self.HIDS = (                         # Service description: describes the service and how we communicate
            UUID(0x1812),                     # Human Interface Device
            (
                (UUID(0x2A4A), F_READ),       # HID information
                (UUID(0x2A4B), F_READ),       # HID report map
                (UUID(0x2A4C), F_WRITE),      # HID control point
                (UUID(0x2A4D), F_READ_NOTIFY, ((UUID(0x2908), ATT_F_READ),)),  # HID report / reference
                (UUID(0x2A4E), F_READ_WRITE), # HID protocol mode
            ),
        )

        # fmt: off
        self.HID_INPUT_REPORT = bytes([    # Report Description: describes what we communicate
            0x05, 0x01,                    # USAGE_PAGE (Generic Desktop)
            0x09, 0x02,                    # USAGE (Mouse)
            0xa1, 0x01,                    # COLLECTION (Application)
            0x85, 0x01,                    #   REPORT_ID (1)
            0xa1, 0x00,                    #   COLLECTION (Physical)
            0x95, 0x03,                    #         Report Count (3)
            0x75, 0x01,                    #         Report Size (1)
            0x05, 0x09,                    #         Usage Page (Buttons)
            0x19, 0x01,                    #         Usage Minimum (1)
            0x29, 0x03,                    #         Usage Maximum (3)
            0x15, 0x00,                    #         Logical Minimum (0)
            0x25, 0x01,                    #         Logical Maximum (1)
            0x81, 0x02,                    #         Input(Data, Variable, Absolute); 3 button bits
            0x95, 0x01,                    #         Report Count(1)
            0x75, 0x05,                    #         Report Size(5)
            0x81, 0x01,                    #         Input(Constant);                 5 bit padding
            0x75, 0x08,                    #         Report Size (8)
            0x95, 0x02,                    #         Report Count (3)
            0x05, 0x01,                    #         Usage Page (Generic Desktop)
            0x09, 0x30,                    #         Usage (X)
            0x09, 0x31,                    #         Usage (Y)
            0x09, 0x38,                    #         Usage (Wheel)
            0x15, 0x81,                    #         Logical Minimum (-127)
            0x25, 0x7F,                    #         Logical Maximum (127)
            0x81, 0x06,                    #         Input(Data, Variable, Relative); 3 position bytes (X,Y,Wheel)
            0xc0,                          #   END_COLLECTION
            0xc0                           # END_COLLECTION
        ])
        # fmt: on

        # Define the initial mouse state
        self.x = 0
        self.y = 0
        self.w = 0

        self.button1 = 0
        self.button2 = 0
        self.button3 = 0

        self.services = [self.DIS, self.BAS, self.HIDS]  # List of service descriptions

    # Overwrite super to register HID specific service
    # Call super to register DIS and BAS services
    def start(self):
        super(Mouse, self).start()  # Start super

        print("Registering services")
        # Register services and get read/write handles for all services
        handles = self._ble.gatts_register_services(self.services)
        # Write the values for the characteristics
        self.write_service_characteristics(handles)

        # Create an Advertiser
        # Only advertise the top level service, i.e., the HIDS
        self.adv = Advertiser(self._ble, [UUID(0x1812)], self.device_appearance, self.device_name)

        print("Server started")

    # Overwrite super to write HID specific characteristics
    # Call super to write DIS and BAS characteristics
    def write_service_characteristics(self, handles):
        super(Mouse, self).write_service_characteristics(handles)

        # Get the handles from the hids, the third service after DIS and BAS
        # These correspond directly to self.HIDS
        (h_info, h_hid, _, self.h_rep, h_d1, h_proto,) = handles[2]

        # Pack the initial mouse state as described by the input report
        b = self.button1 + self.button2 * 2 + self.button3
        state = struct.pack("Bbbb", b, self.x, self.y, self.w)

        print("Writing hid service characteristics")
        # Write service characteristics
        self._ble.gatts_write(h_info, b"\x01\x01\x00\x02")     # HID info: ver=1.1, country=0, flags=normal
        self._ble.gatts_write(h_hid, self.HID_INPUT_REPORT)    # HID input report map
        self._ble.gatts_write(self.h_rep, state)               # HID report
        self._ble.gatts_write(h_d1, struct.pack("<BB", 1, 1))  # HID reference: id=1, type=input
        self._ble.gatts_write(h_proto, b"\x01")                # HID protocol mode: report

    # Overwrite super to notify central of a hid report
    def notify_hid_report(self):
        if self.is_connected():
            # Pack the mouse state as described by the input report
            b = self.button1 + self.button2 * 2 + self.button3
            state = struct.pack("Bbbb", b, self.x, self.y, self.w)

            print("Notify with report: ", struct.unpack("Bbbb", state))
            # Notify central by writing to the report handle
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

    def set_wheel(self, w=0):
        if w > 127:
            w = 127
        elif w < -127:
            w = -127

        self.w = w

    def set_buttons(self, b1=0, b2=0, b3=0):
        self.button1 = b1
        self.button2 = b2
        self.button3 = b3

# Class that represents the Keyboard service
class Keyboard(HumanInterfaceDevice):
    def __init__(self, name="Bluetooth Keyboard"):
        super(Keyboard, self).__init__(name)  # Set up the general HID services in super
        self.device_appearance = 961          # Device appearance ID, 961 = keyboard

        self.HIDS = (                         # Service description: describes the service and how we communicate
            UUID(0x1812),                     # Human Interface Device
            (
                (UUID(0x2A4A), F_READ),       # HID information
                (UUID(0x2A4B), F_READ),       # HID report map
                (UUID(0x2A4C), F_WRITE),      # HID control point
                (UUID(0x2A4D), F_READ_NOTIFY, ((UUID(0x2908), ATT_F_READ),)),  # HID report / reference
                (UUID(0x2A4D), F_READ_WRITE, ((UUID(0x2908), ATT_F_READ),)),  # HID report / reference
                (UUID(0x2A4E), F_READ_WRITE), # HID protocol mode
            ),
        )

        # fmt: off
        self.HID_INPUT_REPORT = bytes([    # Report Description: describes what we communicate
            0x05, 0x01,                    # USAGE_PAGE (Generic Desktop)
            0x09, 0x06,                    # USAGE (Keyboard)
            0xa1, 0x01,                    # COLLECTION (Application)
            0x85, 0x01,                    #   REPORT_ID (1)
            0x75, 0x01,                    #     Report Size (1)
            0x95, 0x08,                    #     Report Count (8)
            0x05, 0x07,                    #     Usage Page (Key Codes)
            0x19, 0xE0,                    #     Usage Minimum (224)
            0x29, 0xE7,                    #     Usage Maximum (231)
            0x15, 0x00,                    #     Logical Minimum (0)
            0x25, 0x01,                    #     Logical Maximum (1)
            0x81, 0x02,                    #     Input (Data, Variable, Absolute); Modifier byte
            0x95, 0x01,                    #     Report Count (1)
            0x75, 0x08,                    #     Report Size (8)
            0x81, 0x01,                    #     Input (Constant); Reserved byte
            0x95, 0x05,                    #     Report Count (5)
            0x75, 0x01,                    #     Report Size (1)
            0x05, 0x08,                    #     Usage Page (LEDs)
            0x19, 0x01,                    #     Usage Minimum (1)
            0x29, 0x05,                    #     Usage Maximum (5)
            0x91, 0x02,                    #     Output (Data, Variable, Absolute); LED report
            0x95, 0x01,                    #     Report Count (1)
            0x75, 0x03,                    #     Report Size (3)
            0x91, 0x01,                    #     Output (Constant); LED report padding
            0x95, 0x06,                    #     Report Count (6)
            0x75, 0x08,                    #     Report Size (8)
            0x15, 0x00,                    #     Logical Minimum (0)
            0x25, 0x65,                    #     Logical Maximum (101)
            0x05, 0x07,                    #     Usage Page (Key Codes)
            0x19, 0x00,                    #     Usage Minimum (0)
            0x29, 0x65,                    #     Usage Maximum (101)
            0x81, 0x00,                    #     Input (Data, Array); Key array (6 bytes)
            0xc0                           # END_COLLECTION
        ])
        # fmt: on

        # Define the initial keyboard state
        self.modifiers = 0       # 8 bits signifying Right GUI(Win/Command), Right ALT/Option, Right Shift, Right Control, Left GUI, Left ALT, Left Shift, Left Control
        self.leds = 0            # Led status lights
        self.keys = [0x00] * 6   # 6 keys to hold

        # Callback function for keyboard messages from central
        self.kb_callback = None

        self.services = [self.DIS, self.BAS, self.HIDS]  # List of service descriptions

    # Interrupt request callback function
    # Overwrite super to catch keyboard report write events by the central
    def ble_irq(self, event, data):
        if event == _IRQ_GATTS_WRITE:               # If a client has written to a characteristic or descriptor.
            print("Keyboard changed by Central")
            conn_handle, attr_handle = data         # Get the handle to the characteristic that was written
            (self.modifiers, _, self.leds, key0, key1, key2, key3, key4, key5) = struct.unpack("9B", self._ble.gatts_read(attr_handle))  # Unpack the report
            if self.kb_callback is not None:        # Call the callback function
                self.kb_callback(self.modifiers, self.leds, key0, key1, key2, key3, key4, key5)
        else:                                       # Else let super handle the event
            super(Keyboard, self).ble_irq(event, data)

    # Overwrite super to register HID specific service
    # Call super to register DIS and BAS services
    def start(self):
        super(Keyboard, self).start()  # Start super

        print("Registering services")
        # Register services and get read/write handles for all services
        handles = self._ble.gatts_register_services(self.services)
        # Write the values for the characteristics
        self.write_service_characteristics(handles)

        # Create an Advertiser
        # Only advertise the top level service, i.e., the HIDS
        self.adv = Advertiser(self._ble, [UUID(0x1812)], self.device_appearance, self.device_name)

        print("Server started")

    # Overwrite super to write HID specific characteristics
    # Call super to write DIS and BAS characteristics
    def write_service_characteristics(self, handles):
        super(Keyboard, self).write_service_characteristics(handles)

        # Get the handles from the hids, the third service after DIS and BAS
        # These correspond directly to self.HIDS
        (h_info, h_hid, _, self.h_rep, h_d1, self.h_repout, h_d2, h_proto,) = handles[2]

        print("Writing hid service characteristics")
        # Write service characteristics
        self._ble.gatts_write(h_info, b"\x01\x01\x00\x02")     # HID info: ver=1.1, country=0, flags=normal
        self._ble.gatts_write(h_hid, self.HID_INPUT_REPORT)    # HID input report map
        self._ble.gatts_write(h_d1, struct.pack("<BB", 1, 1))  # HID reference: id=1, type=input
        self._ble.gatts_write(h_d2, struct.pack("<BB", 1, 2))  # HID reference: id=1, type=output
        self._ble.gatts_write(h_proto, b"\x01")                # HID protocol mode: report

    # Overwrite super to notify central of a hid report
    def notify_hid_report(self):
        if self.is_connected():
            # Pack the Keyboard state as described by the input report
            state = struct.pack("9B", self.modifiers, 0, self.leds, self.keys[:6])

            print("Notify with report: ", struct.unpack("9B", state))
            # Notify central by writing to the report handle
            self._ble.gatts_notify(self.conn_handle, self.h_rep, state)

    # Set the modifier bits, notify to send the modifiers to central
    def set_modifiers(self, right_gui=0, right_alt=0, right_shift=0, right_control=0, left_gui=0, left_alt=0, left_shift=0, left_control=0):
        self.modifiers = right_gui << 7 + right_alt << 6 + right_shift << 5 + right_control << 4 + left_gui << 3 + left_alt << 2 + left_shift << 1 + left_control

    # Set the leds, notify to send the leds to central
    def set_leds(self, l0=0, l1=0, l2=0, l3=0, l4=0):
        self.leds = l0 + l1 << 1 + l2 << 2 + l3 << 3 + l4 << 4

    # Press keys, notify to send the keys to central
    # This will hold down the keys, call set_keys() without arguments and notify again to release
    def set_keys(self, k0=0x00, k1=0x00, k2=0x00, k3=0x00, k4=0x00, k5=0x00):
        self.keys = [k0, k1, k2, k3, k4, k5]

    # Set a callback function that gets notified on keyboard changes
    # Should take 8 arguments: modifiers, leds, key0, key1, key2, key3, key4, key5
    def set_kb_callback(self, kb_callback):
        self.kb_callback = kb_callback
