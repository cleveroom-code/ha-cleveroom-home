from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
import time

class Instruction:

    def __init__(self, inst):
        self.b = []

        if isinstance(inst, str):
            bytes_list = inst.split(',')
        else:
            bytes_list = inst

        num = 0
        for i in range(7):
            cmd = int(bytes_list[i])
            num += cmd * (8 - i)
            self.b.append(cmd)

        check = num % 256
        self.b.append(check)

    def get_d1(self):
        return self.b[0]

    def get_d2(self):
        return self.b[1]

    def get_d3(self):
        return self.b[2]

    def get_d4(self):
        return self.b[3]

    def get_d5(self):
        return self.b[4]

    def get_d6(self):
        return self.b[5]

    def get_d7(self):
        return self.b[6]

    def get_d8(self):
        return self.b[7]

    def get_inst(self):
        return self.b

    def __str__(self):
        hex_str = ""
        for v in self.b:
            hex_str += str(v) + ' '
        return hex_str.strip()


class CRMDevice:
    def __init__(self, uid, inst: Instruction):
        self.uid = uid
        self.inst = inst

    def get_inst(self):
        return self.inst

    def get_uid(self):
        return self.uid

    def set_uid(self, uid):
        self.uid = uid

    def __str__(self):
        return f"uid={self.uid},{self.inst}"


class DeviceBuffer:

    def __init__(self, buf_type):
        self.buffer_type = buf_type
        self.devices = {}
        self.listeners = {}
        self.antishakes  = {}

    def create_index(self, ins, idx):
        b = ins.get_inst()
        uid = ''
        for i in range(len(idx)):
            if i == 0:
                uid += str(b[idx[i]])
            else:
                uid += '-' + str(b[idx[i]])
        return uid

    def add(self, ins, idx, trigger_add_no_cache=None, trigger_update_no_cache=None):
        self._add2buffer(ins, idx, trigger_add_no_cache, trigger_update_no_cache)

    def add_with_ignore(self, ins, idx, ignore):
        self._add2buffer_with_ignore(ins, idx, ignore)

    def add_with_uid(self, ins, uid):
        existing_device = self.devices.get(uid)
        # Create new device instance
        new_device = CRMDevice(uid, ins)
        if not existing_device:
            # If the device does not exist, add a new device
            self.devices[uid] = new_device
            self._trigger_event('add', new_device)
        else:
            # If the device already exists, check if it is the same
            if not self._is_same_device(existing_device, new_device):
                # If the device changes, update the device
                self.devices[uid] = new_device
                self._trigger_event('change', new_device)
            else:
                # If the device is the same, trigger the cover event
                self._trigger_event('cover', new_device)

    def _add2buffer(self, ins, idx, trigger_add_no_cache, trigger_update_no_cache):
        uid = self.create_index(ins, idx)
        o = self.devices.get(uid)
        if not o:
            device = CRMDevice(uid, ins)
            if not trigger_add_no_cache:
                self.devices[uid] = device
            self._trigger_event('add', device)
        else:
            device = CRMDevice(uid, ins)
            if not self._is_same_device(o, device):
                if not trigger_update_no_cache:
                    self.devices[uid] = device
                self._trigger_event('change', device)

    def _add2buffer_with_ignore(self, ins, idx, ignore):
        uid = self.create_index(ins, idx)
        o = self.devices.get(uid)
        if not o:
            device = CRMDevice(uid, ins)
            self.devices[uid] = device
            self._trigger_event('add', device)
        else:
            device = CRMDevice(uid, ins)
            if not self._is_same_ignore_device(o, device, ignore):
                self.devices[uid] = device
                self._trigger_event('change', device)

    def _is_same_ignore_device(self, dev1, dev2, ignore):
        ins1, ins2 = dev1.get_inst(), dev2.get_inst()
        b1, b2 = ins1.get_inst(), ins2.get_inst()

        for i in range(len(b1)):
            if i in ignore:
                continue
            if b1[i] != b2[i]:
                return False
        return True

    def _is_same_device(self, dev1, dev2):
        ins1, ins2 = dev1.get_inst(), dev2.get_inst()
        b1, b2 = ins1.get_inst(), ins2.get_inst()

        for i in range(len(b1)):
            if b1[i] != b2[i]:
                return False
        return True

    def _trigger_event(self, event, device):
        for key in self.listeners:
            listener = self.listeners[key]
            try:
                if event == 'add':
                    if listener and 'on_add' in listener:
                        listener['on_add'](device, self.buffer_type)
                else:
                    if listener and 'on_change' in listener:
                        listener['on_change'](device, self.buffer_type)
            except Exception as e:
                print(f"Error triggering event: {e}")

    def add_listener(self, key, listener):
        self.listeners[key] = listener

    def remove_listener(self, key):
        if key in self.listeners:
            del self.listeners[key]

    def clear(self):
        self.devices = {}

    def get_device_by_id(self, uid):
        return self.devices.get(uid)

    def remove_device_by_id(self, uid):
        if uid in self.devices:
            del self.devices[uid]

    def get_device_list(self):
        return list(self.devices.values())

    def just_trigger_event(self, ins):
        uid = self.create_index(ins, [0, 1, 2, 3, 4, 5, 6])
        alarm = CRMDevice(uid, ins)
        self._trigger_event('add', alarm)

    def just_trigger_event_delay(self, ins, delay=0.25):
        uid = self.create_index(ins, [0, 1, 2, 3, 4, 5, 6])
        now = time.time()
        lasttime = self.antishakes.get(uid)
        # freeze in 250ms
        if lasttime and (now - lasttime)<delay:
            return
        # update last time
        self.antishakes[uid] = now
        event = CRMDevice(uid, ins)
        self._trigger_event('add', event)

####The following are common methods
def ascii_to_hex(paswd):
    b = []
    if paswd:
        for v in paswd:
            b.append(ord(v) - 48)
    return b


def byte2bits(dx):
    binstr = bin(int(dx))[2:]
    if len(binstr) < 8:
        binstr = '0' * (8 - len(binstr)) + binstr
    b = list(binstr[::-1])
    return [int(v) for v in b]


def short2bits(short):
    high = (short & 0xff00) >> 8
    low = short & 0x00ff
    bits = byte2bits(low)
    return bits + byte2bits(high)


def bit2byte(dx, start, end):
    bits = byte2bits(dx)
    newbits = bits[start:end + 1]
    return int(''.join(map(str, newbits[::-1])), 2)


def bit2short(dx, start, end):
    bits = short2bits(dx)
    newbits = bits[start:end + 1]
    return int(''.join(map(str, newbits[::-1])), 2)


def bitarray2short(bits):
    newbits = bits[:]
    return int(''.join(map(str, newbits[::-1])), 2)


def uint8array_to_string(data):
    data_string = ""
    for d in data:
        data_string += chr(d)
    return data_string


def byte2hex(byte):
    hex_str = hex(byte)[2:].upper()
    return hex_str if byte >= 16 else '0' + hex_str


def get_random_code(length):
    import random
    code = [random.randint(0, 255) for _ in range(length)]
    return code

def get_current_time():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

def safe_merge_objects(ori_obj, change_obj):
    """
    Safely merge two objects, handle None values, and perform a deep copy
    """
    result = {}
    # Safely handle the original object
    if ori_obj is not None:
        try:
            result.update(deepcopy(ori_obj))
        except (TypeError, AttributeError) as e:
            print(f"Warning: Failed to copy ori_obj: {e}")
            result.update({} if ori_obj is None else dict(ori_obj))

    # Safely handle the changed object
    if change_obj is not None:
        try:
            result.update(deepcopy(change_obj))
        except (TypeError, AttributeError) as e:
            print(f"Warning: Failed to copy change_obj: {e}")
            result.update({} if change_obj is None else dict(change_obj))

    return result


def has_method(obj: Any, method_name: str) -> bool:
    try:
        attr = getattr(obj, method_name, None)
        return attr is not None and callable(attr)
    except Exception:
        return False
