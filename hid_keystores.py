import esp32
import json
import binascii

# Class that represents a generic keystore
class KeyStore(object):

    def __init__(self):
        self.secrets = {}

    def add_secret(self, type, key, value):
        _key = (type, bytes(key))
        self.secrets[_key] = bytes(value)

    def get_secret(self, type, index, key):
        _key = (type, bytes(key) if key else None)
        value = None

        if key is None:
            i = 0
            for (t, _k), _val in self.secrets.items():
                if t == type:
                    if i == index:
                        value = _val
                    i += 1
        else:
            value = self.secrets.get(_key, None)

        return value

    def remove_secret(self, type, key):
        _key = (type, bytes(key))
        del self.secrets[_key]

    def has_secret(self, type, key):
        _key = (type, bytes(key))
        return _key in self.secrets

    def json_dump(self):
        json_secrets = [
            (sec_type, binascii.b2a_base64(key, newline=False), binascii.b2a_base64(value, newline=False))
            for (sec_type, key), value in self.secrets.items()
        ]
        return json_secrets

    def add_json_entries(self, entries):
        for sec_type, key, value in entries:
            self.secrets[sec_type, binascii.a2b_base64(key)] = binascii.a2b_base64(value)

    def load_secrets(self):
        return

    def save_secrets(self):
        return


# Class that uses a JSON file as keystore
class JSONKeyStore(KeyStore):

    def __init__(self):
        super(JSONKeyStore, self).__init__()

    def load_secrets(self):
        try:
            with open("keys.json", "r") as file:
                self.add_json_entries(json.load(file))
        except:
            print("No secrets available")

    def save_secrets(self):
        try:
            with open("keys.json", "w") as file:
                json.dump(self.json_dump(), file)
        except:
            print("Failed to save secrets")


# Class that uses non-volatile storage as keystore
class NVSKeyStore(KeyStore):

    def __init__(self):
        super(NVSKeyStore, self).__init__()
        self.nvsdata = esp32.NVS("BLE")

    # Load bonding keys from non-volatile storage.
    def load_secrets(self):
        data = bytearray()
        num_bytes = 0

        try:
            num_bytes = self.nvsdata.get_blob("Keys", data)
            data = bytearray(num_bytes)
            self.nvsdata.get_blob("Keys", data)
        except:
            print("Failed to read NVS")

        if num_bytes > 0:
            s = str(data, 'utf-8')
            try:
                entries = json.loads(s)
                self.add_json_entries(entries)
            except:
                print("Failed to load secrets")
        else:
            print("No secrets available")

    # Save bonding keys to non-volatile storage.
    def save_secrets(self):
        try:
            self.nvsdata.set_blob("Keys", json.dumps(self.json_dump()))
            self.nvsdata.commit()
        except:
            print("Failed to save secrets")

