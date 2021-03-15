import struct
import bluetooth
from bluetooth import UUID

F_READ = bluetooth.FLAG_READ
F_WRITE = bluetooth.FLAG_WRITE
F_READ_WRITE = bluetooth.FLAG_READ | bluetooth.FLAG_WRITE
F_READ_NOTIFY = bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY

ATT_F_READ = 0x01
ATT_F_WRITE = 0x02

# Class that represents a general HID device state
class HumanInterfaceDevice(object):

    def __init__(self):
        self.DEV_NAME = "Generic HID Device"
        self.DEV_UUID = UUID(0x1812)  #Generic HID UUID
        self.DEV_APPEARANCE = 960     #Generic HID Appearance

        self.HID_SERVICE_REPORT = None
        self.HID_SERVICE_REPORT_DATA = None
        self.HID_INPUT_REPORT = None

        self.state = bytearray()

    def initiate_report(self, _ble, handles):
        return

    def get_state(self):
        return self.state

    def get_name(self):
        return self.DEV_NAME

    def get_uuid(self):
        return self.DEV_UUID

    def get_appearance(self):
        return self.DEV_APPEARANCE

    def get_service_report(self):
        return self.HID_SERVICE_REPORT

    def get_service_report_data(self):
        return self.HID_SERVICE_REPORT_DATA

    def get_input_report(self):
        return self.HID_INPUT_REPORT


# Class that represents the Joystick state
class Joystick(HumanInterfaceDevice):
    def __init__(self, name="Bluetooth Joystick"):
        super(Joystick, self).__init__()

        self.DEV_NAME = name  # Device name
        self.DEV_APPEARANCE = 963  # Device appearance ID, 963 = joystick

        self.HID_SERVICE_REPORT = (  # Service description: describes the service and how we communicate
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
            0x09, 0x01,                    #   USAGE (Pointer)
            0xa1, 0x00,                    #   COLLECTION (Physical)
            0x05, 0x09,                    #     USAGE_PAGE (Button)
            0x19, 0x01,                    #     USAGE_MINIMUM (Button 1)
            0x29, 0x04,                    #     USAGE_MAXIMUM (Button 4)
            0x15, 0x00,                    #     LOGICAL_MINIMUM (0)
            0x25, 0x01,                    #     LOGICAL_MAXIMUM (1)
            0x95, 0x04,                    #     REPORT_COUNT (4)
            0x75, 0x01,                    #     REPORT_SIZE (1)
            0x81, 0x02,                    #     INPUT (Data,Var,Abs)
            0x95, 0x01,                    #     REPORT_COUNT (1)
            0x75, 0x04,                    #     REPORT_SIZE (4)
            0x81, 0x03,                    #     INPUT (Cnst,Var,Abs)
            0x05, 0x01,                    #     USAGE_PAGE (Generic Desktop)
            0x09, 0x30,                    #     USAGE (X)
            0x09, 0x31,                    #     USAGE (Y)
            0x15, 0x81,                    #     LOGICAL_MINIMUM (-127)
            0x25, 0x7f,                    #     LOGICAL_MAXIMUM (127)
            0x75, 0x08,                    #     REPORT_SIZE (8)
            0x95, 0x02,                    #     REPORT_COUNT (2)
            0x81, 0x02,                    #     INPUT (Data,Var,Abs)
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

        # Pack the initial joystick state as described by the input report
        b = self.button1 + self.button2 * 2 + self.button3 * 3 + self.button4 * 4
        self.state = struct.pack("<3B", b, self.x, self.y)

        # Define initial service report data with indices
        # 0 = HID info: ver=1.1, country=0, flags=normal
        # 1 = HID input report map
        # 2 = HID control point
        # 3 = HID report /
        # 4 = HID reference: id=1, type=input
        # 5 = HID protocol mode: report
        self.HID_SERVICE_REPORT_DATA = (b"\x01\x01\x00\x02", self.HID_INPUT_REPORT, None, self.state, struct.pack("<BB", 1, 1), b"\x01")

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

    def set_buttons(self, b1=0, b2=0, b3=0, b4=0):
        self.button1 = b1
        self.button2 = b2
        self.button3 = b3
        self.button4 = b4

    def get_state(self):
        b = self.button1 + self.button2 * 2 + self.button3 * 3 + self.button4 * 4
        self.state = struct.pack("<Bbb", b, self.x, self.y)
        return self.state


# Class that represents the Mouse state
class Mouse(HumanInterfaceDevice):
    def __init__(self, name="Bluetooth Mouse"):
        super(Mouse, self).__init__()

        self.DEV_NAME = name  # Device name
        self.DEV_APPEARANCE = 962  # Device appearance ID, 962 = mouse

        self.HID_SERVICE_REPORT = (  # Service description: describes the service and how we communicate
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
            0x05, 0x01,     # Usage Page (Generic Desktop)
            0x09, 0x02,     # Usage (Mouse)
            0xA1, 0x01,     # Collection (Application)
            0x09, 0x01,     #     Usage (Pointer)
            0xA1, 0x00,     #     Collection (Physical)
            0x85, 0x01,     #         Report ID (1)
            0x95, 0x03,     #         Report Count (3)
            0x75, 0x01,     #         Report Size (1)
            0x05, 0x09,     #         Usage Page (Buttons)
            0x19, 0x01,     #         Usage Minimum (1)
            0x29, 0x03,     #         Usage Maximum (3)
            0x15, 0x00,     #         Logical Minimum (0)
            0x25, 0x01,     #         Logical Maximum (1)
            0x81, 0x02,     #         Input(Data, Variable, Absolute); 3 button bits
            0x95, 0x01,     #         Report Count(1)
            0x75, 0x05,     #         Report Size(5)
            0x81, 0x01,     #         Input(Constant);                 5 bit padding
            0x75, 0x08,     #         Report Size (8)
            0x95, 0x02,     #         Report Count (3)
            0x05, 0x01,     #         Usage Page (Generic Desktop)
            0x09, 0x30,     #         Usage (X)
            0x09, 0x31,     #         Usage (Y)
            0x09, 0x38,     #         Usage (Wheel)
            0x15, 0x81,     #         Logical Minimum (-127)
            0x25, 0x7F,     #         Logical Maximum (127)
            0x81, 0x06,     #         Input(Data, Variable, Relative); 3 position bytes (X,Y,Wheel)
            0xC0,           #     End Collection
            0xC0,           # End Collection
        ])
        # fmt: on

        # Define the initial mouse state
        self.x = 0
        self.y = 0
        self.w = 0

        self.button1 = 0
        self.button2 = 0
        self.button3 = 0

        # Pack the initial joystick state as described by the input report
        b = self.button1 + self.button2 * 2 + self.button3 * 3
        self.state = struct.pack("4B", b, self.x, self.y, self.w)

        # Define initial service report data with indices
        # 0 = HID info: ver=1.1, country=0, flags=normal
        # 1 = HID input report map
        # 2 = HID control point
        # 3 = HID report /
        # 4 = HID reference: id=1, type=input
        # 5 = HID protocol mode: report
        self.HID_SERVICE_REPORT_DATA = (b"\x01\x01\x00\x02", self.HID_INPUT_REPORT, None, self.state, struct.pack("<BB", 1, 1), b"\x01")

    def set_axes(self, x=0, y=0, w=0):
        if x > 127:
            x = 127
        elif x < -127:
            x = -127

        if y > 127:
            y = 127
        elif y < -127:
            y = -127

        if w > 127:
            w = 127
        elif w < -127:
            w = -127

        self.x = x
        self.y = y
        self.w = w

    def set_buttons(self, b1=0, b2=0, b3=0):
        self.button1 = b1
        self.button2 = b2
        self.button3 = b3

    def get_state(self):
        b = self.button1 + self.button2 * 2 + self.button3 * 3
        self.state = struct.pack("4B", b, self.x, self.y, self.w)
        return self.state
