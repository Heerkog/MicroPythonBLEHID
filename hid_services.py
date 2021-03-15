from micropython import const
import struct
import bluetooth
from bluetooth import UUID

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

    # Start advertising at 500000 interval
    def start_advertising(self):
        if not self.advertising:
            self._ble.gap_advertise(500000, adv_data=self._payload)
            self.advertising = True
            print("Started advertising")

    # Start advertising by setting interval of 0
    def stop_advertising(self):
        if self.advertising:
            self._ble.gap_advertise(0, adv_data=self._payload)
            self.advertising = False
            print("Stopped advertising")

    # Are we advertising
    def is_advertising(self):
        return self.advertising


class Server:

    def ble_irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            self.conn_handle, _, _ = data
            print("Central connected: ", self.conn_handle)
            if self.connect_callback is not None:
                self.connect_callback()
        elif event == _IRQ_CENTRAL_DISCONNECT:
            self.conn_handle = None
            print("Central disconnected")
            if self.disconnect_callback is not None:
                self.disconnect_callback()
        elif event == _IRQ_MTU_EXCHANGED:
            print("MTU exchanged")
        elif event == _IRQ_CONNECTION_UPDATE:
            self.conn_handle, _, _, _, _ = data
            print("Connection update")
        else:
            print("Unhandled IRQ event: ", event)

    def is_connected(self):
        return self.conn_handle is not None

    def __init__(self, _ble):
        self.conn_handle = None
        self._ble = _ble
        self.started = False
        self.handles = None
        self.adv = None

        self.connect_callback = None
        self.disconnect_callback = None

        print("Server created")

    def start(self, hid_device):
        if not self.started:
            self._ble.active(1)
            self._ble.irq(self.ble_irq)
            self._ble.config(gap_name=hid_device.get_name())

            print("BLE on")

            self.handles = self._ble.gatts_register_services((hid_device.get_service_report(),))
            print("Registered services")

            h_info, h_hid, _, self.h_rep, h_d1, h_proto = self.handles[0]
            print("Obtained service handles: ", self.handles[0])

            handles_data = hid_device.get_service_report_data()

            for h, d in zip(self.handles[0], handles_data):
                if d is not None:
                    self._ble.gatts_write(h, d)

            print("Wrote service handles: ", handles_data)

            self.adv = Advertiser(self._ble, [hid_device.get_uuid()], hid_device.get_appearance(), hid_device.get_name())

            self.started = True
            print("Server started")

    def stop(self):
        if self.started:
            if self.adv.advertising:
                self.adv.stop_advertising()
            self._ble.active(0)
            self.handles = None
            self.h_rep = None
            self.adv = None
            self.started = False
            print("Server stopped")

    def is_running(self):
        return self.started

    def start_advertising(self):
        if self.started:
            self.adv.start_advertising()

    def stop_advertising(self):
        if self.started:
            self.adv.stop_advertising()

    # Are we advertising
    def is_advertising(self):
        return self.adv.is_advertising()

    def send_report(self, report):
        if self.started and self.is_connected():
            self._ble.gatts_notify(self.conn_handle, self.h_rep, report)
            print("Sent report: ", struct.unpack("<Bbb", report), " to conn: ", self.conn_handle, " on response handle: ", self.h_rep)

    def set_connect_callback(self, callback):
        self.connect_callback = callback

    def set_disconnect_callback(self, callback):
        self.disconnect_callback = callback

