from typing import Dict, List, Any, Callable
from .klw_common import byte2bits, bit2byte
from .klw_type import BufferType
from .klw_type import DeviceType
from .klw_nameprovider import *

from . import utils

import aiofiles
import json


class BucketDataManager:
    """Manages loading and saving DeviceBucket data asynchronously."""

    def __init__(self, file_path: str):
        """Initialize with the file path for the bucket data."""
        self.file_path = file_path

    async def async_load_data(self) -> dict:
        """Asynchronously load bucket data from the file."""
        try:
            async with aiofiles.open(self.file_path, mode='r') as f:
                content = await f.read()
                return json.loads(content)
        except FileNotFoundError:
            print(f"File not found: {self.file_path}")
            return {}
        except json.JSONDecodeError:
            print(f"Invalid JSON format in: {self.file_path}")
            return {}
        except Exception as e:
            print(f"Error loading bucket data from {self.file_path}: {e}")
            return {}

    async def async_save_data(self, data: dict):
        """Asynchronously save bucket data to the file."""
        try:
            async with aiofiles.open(self.file_path, mode='w') as f:
                await f.write(json.dumps(data))
        except Exception as e:
            print(f"Error saving bucket data to {self.file_path}: {e}")


class DeviceBucket:

    def __init__(self, client_id: str, persistence: bool = False, language: str = 'zh-Hans', bucket_manager=None,
                 data_changed_callback: Callable[[], None] = None):
        self.persistence = persistence
        self._client_id = client_id
        self._language = language
        self._bucket = {}
        self._bucket_data_manager = bucket_manager
        self._data_changed_callback = data_changed_callback

    def get_bucket(self):
        return self._bucket

    def get_bucket_keys(self):
        return list(self._bucket.keys())

    def get_bucket_values(self):
        return list(self._bucket.values())

    def clear_bucket(self):
        self._bucket.clear()
        if self.persistence:
            if self._bucket_data_manager:
                if self._data_changed_callback:
                    self._data_changed_callback()

    def get_device_by_dsid(self, ds_id):
        devices = []
        for key in self._bucket:
            if key.startswith(ds_id):
                devices.append(self._bucket[key])
        return devices

    def del_device_by_dsid(self, ds_id):
        for key in self._bucket:
            if key.startswith(ds_id):
                del self._bucket[key]

    def get_data_from_database(self, key: str):
        device = self.get_device_from_database(key)
        if device:
            return device.get('data')
        return None

    def get_detail_from_database(self, key):
        raw = self.get_device_from_database(key)
        if raw:
            return raw.get('detail')
        return None

    def get_device_from_database(self, key):
        if key in self._bucket:
            return self._bucket[key]
        return None

    def save_device_to_database(self, key, value, persistence: bool = False):
        self._bucket[key] = value
        if self.persistence and persistence:
            if self._bucket_data_manager:
                if self._data_changed_callback:
                    self._data_changed_callback()

    def remove_device_from_database(self, key, persistence: bool = False):
        if key in self._bucket:
            del self._bucket[key]
        if self.persistence and persistence:
            if self._bucket_data_manager:
                if self._data_changed_callback:
                    self._data_changed_callback()

    async def async_load_data(self):
        """Asynchronously load data using BucketDataManager."""
        if self._bucket_data_manager:
            self._bucket = await self._bucket_data_manager.async_load_data()

    async def async_save_data(self):
        """Asynchronously save data using BucketDataManager."""
        if self._bucket_data_manager:
            await self._bucket_data_manager.async_save_data(self._bucket)

    def is_toggle_light(self, d5: int) -> bool:
        if d5 in [17, 24, 25]:
            return True
        if 30 <= d5 <= 33:
            return True
        if 61 <= d5 <= 80:
            return True
        if 90 <= d5 <= 98:
            return True
        if 201 <= d5 <= 227:
            return True
        if 239 <= d5 <= 241:
            return True
        return False

    def create_object_detail(self, ds_id: str, inst: List[int], buffer_type: int, uid: str):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst

        cache_object = self.get_detail_from_database(f"{ds_id}.{uid}.{buffer_type}")
        ori_obj = cache_object

        if buffer_type in [BufferType.DEVICEBUFFER, BufferType.VOLBUFFER, BufferType.FMBUFFER, BufferType.RGBBUFFER,
                           BufferType.CACHEBUFFER]:
            db7 = byte2bits(D7)

            if D1 == 250:
                key250 = f"{ds_id}.{uid}.3"
                o250 = self.get_detail_from_database(key250)

                if o250:
                    change_obj = {}
                    if o250.get('category') == DeviceType.WARM_LIGHT and buffer_type == BufferType.RGBBUFFER:
                        change_obj['warm'] = D5
                        return {
                            'oriObj': o250,
                            'changeObj': change_obj
                        }
                    if o250.get('category') == DeviceType.RGB_LIGHT and buffer_type == BufferType.RGBBUFFER:
                        self.init_rgb_light(change_obj, inst)
                        return {
                            'oriObj': o250,
                            'changeObj': change_obj
                        }

            if D1 == 243 and D2==204 and (D5 == 4 or D5 == 191 or D5 == 192 or (81 <= D5 <= 89)):

                o = {
                    "uid": uid,
                    "category": DeviceType.AIR_CONDITION
                }
                self.init_toggle_device(o, inst)
                self.init_ac_device(ds_id, o, inst)
                return {
                    'oriObj': ori_obj,
                    'changeObj': o
                }

            elif D1 == 243 and (D5 == 15 or D5 == 28 or (101 <= D5 <= 119)):
                o = {
                    "uid": uid,
                    "category": DeviceType.CURTAIN
                }
                self.init_toggle_device(o, inst)
                self.init_adjust_curtain(o, inst)
                return {
                    'oriObj': ori_obj,
                    'changeObj': o
                }

            elif D1 == 243 and D5 == 20:
                o = {
                    "uid": uid,
                    "category": DeviceType.FRESH_AIR
                }
                self.init_toggle_device(o, inst)
                self.init_fresh_air(o, inst)
                return {
                    'oriObj': ori_obj,
                    'changeObj': o
                }
            elif D1 == 243 and D5 == 16:
                o = {
                    "uid": uid,
                    "category": DeviceType.FLOOR_HEATING
                }
                self.init_toggle_device(o, inst)
                self.init_warmer(ds_id, o, inst)
                return {
                    'oriObj': ori_obj,
                    'changeObj': o
                }

            elif D1 == 243 and D5 == 3:
                o = {
                    "uid": uid,
                    "category": DeviceType.MUSIC_PLAYER
                }
                if buffer_type == BufferType.VOLBUFFER:
                    if o:
                        o['highVol'] = D6
                        o['lowVol'] = D7
                else:
                    self.init_toggle_device(o, inst)
                    self.init_music_player(ds_id, o, inst)
                    if inst:
                        D6 = inst[5]
                        db6 = byte2bits(D6)
                        o['on'] = db6[7] > 0
                return {
                    'oriObj': ori_obj,
                    'changeObj': o
                }

            else:
                if D2 == 199 and db7[2] == 1 and db7[5] == 0 and db7[7] == 0:
                    o = {
                        "uid": uid,
                        "category": DeviceType.ADJUST_LIGHT
                    }
                    self.init_toggle_device(o, inst)
                    self.init_adjust_device(o, inst)
                    return {
                        'oriObj': ori_obj,
                        'changeObj': o
                    }

                elif D2 == 199 and db7[2] == 1 and db7[5] == 0 and db7[7] == 1:
                    o = {
                        "uid": uid,
                        "category": DeviceType.RGB_LIGHT
                    }
                    self.init_toggle_device(o, inst)
                    self.init_adjust_device(o, inst)
                    return {
                        'oriObj': ori_obj,
                        'changeObj': o
                    }

                elif D2 == 199 and db7[2] == 1 and db7[5] == 1 and db7[7] == 0:
                    o = {
                        "uid": uid,
                        "category": DeviceType.WARM_LIGHT
                    }
                    self.init_toggle_device(o, inst)
                    self.init_adjust_device(o, inst)
                    return {
                        'oriObj': ori_obj,
                        'changeObj': o
                    }

                elif D2 == 199 and db7[2] == 0:
                    if self.is_toggle_light(D5):
                        o = {
                            "uid": uid,
                            "category": DeviceType.TOGGLE_LIGHT
                        }
                    else:
                        o = {
                            "uid": uid,
                            "category": DeviceType.TOGGLE
                        }
                    self.init_toggle_device(o, inst)
                    return {
                        'oriObj': ori_obj,
                        'changeObj': o
                    }

        elif buffer_type == BufferType.SCENEBUFFER:
            o = {
                "uid": uid,
                "category": DeviceType.SCENE
            }
            sensor_d6_bits = byte2bits(D6)
            o['on'] = sensor_d6_bits[7] > 0
            self.init_scene(o, inst)
            return {
                'oriObj': ori_obj,
                'changeObj': o
            }

        elif buffer_type == BufferType.SENSORBUFFER:
            if D2 not in [194, 195, 196, 197]:
                o = {
                    "uid": uid,
                    "category": DeviceType.SENSOR,
                    "twoside": False
                }
                self.init_sensor(o, inst)
                return {
                    'oriObj': ori_obj,
                    'changeObj': o
                }
            elif D2 in [194, 195, 196, 197]:
                o = {
                    "uid": uid,
                    "category": DeviceType.SENSOR,
                    "twoside": True
                }
                self.init_sensor_name(o, inst)
                o['value'] = 1 if D5 == 255 else 0
                o['did'] = D2
                sensor_state = get_local_string("sensor_state", self._language)
                if D2 == 194:
                    name = sensor_state["door_sensor"]
                    on = sensor_state["door_open"]
                    off = sensor_state["door_close"]
                    o['dName'] = f"{D7}#{name}" if D7 >= 0 else name
                    o['vName'] = on if o['value'] > 0 else off
                elif D2 == 195:
                    name = sensor_state["occupancy_sensor"]
                    on = sensor_state["occupancy"]
                    off = sensor_state["occupancy_clear"]
                    o['dName'] = f"{D7}#{name}" if D7 >= 0 else name
                    o['vName'] = on if o['value'] > 0 else off
                elif D2 == 196:
                    name = sensor_state["smoke_sensor"]
                    on = sensor_state["smoke"]
                    off = sensor_state["smoke_clear"]
                    o['dName'] = f"{D7}#{name}" if D7 >= 0 else name
                    o['vName'] = on if o['value'] > 0 else off
                elif D2 == 197:
                    name = sensor_state["gas_sensor"]
                    on = sensor_state["gas"]
                    off = sensor_state["gas_clear"]
                    o['dName'] = f"{D7}#{name}" if D7 >= 0 else name
                    o['vName'] = on if o['value'] > 0 else off

                return {
                    'oriObj': ori_obj,
                    'changeObj': o
                }

        elif buffer_type == BufferType.SENSOREXBUFFER:
            if D2 in [198, 98]:
                o = {
                    "uid": uid,
                    "category": DeviceType.DRY,
                    "twoside": True
                }
                self.init_dry_sensor(o, inst)
                self.init_dry_sensor_name(o, inst)
                return {
                    'oriObj': ori_obj,
                    'changeObj': o
                }

        elif buffer_type == BufferType.SECURITYBUFFER:
            o = {
                "uid": uid,
                "category": DeviceType.SECURITY
            }
            self.init_security(o, inst)
            return {
                'oriObj': ori_obj,
                'changeObj': o
            }
        elif buffer_type == BufferType.EVENTBUFFER:
            o = {
                "uid": uid,
                "category": DeviceType.EVENT
            }
            self.init_event(o,inst)
            return {
                'oriObj': None,
                'changeObj': o
            }

        return None

    def init_device(self, device, inst):
        """初始化基本设备信息"""
        D1, D2, D3, D4, D5, D6, D7, D8 = inst

        device['fid'] = D3
        device['rid'] = D4
        device['did'] = D5

        default_floor_name = get_default_floor_name(D3, self._language)
        default_room_name = get_default_room_name(D4, self._language)
        default_device_name = get_default_device_name(D5, self._language)

        device['fName'] = default_floor_name
        device['rName'] = default_room_name
        device['dName'] = default_device_name

    def init_scene(self, device: Dict[str, Any], inst: List[int]):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst
        device['fid'] = D3
        device['rid'] = D4
        device['did'] = D5
        default_floor_name = get_default_floor_name(D3, self._language)
        default_room_name = get_default_room_name(D4, self._language)
        default_device_name = get_default_scene_name(D5, self._language)
        device['fName'] = default_floor_name
        device['rName'] = default_room_name
        device['dName'] = default_device_name

    def init_toggle_device(self, device, inst):
        self.init_device(device, inst)
        D7 = inst[6]
        db7 = byte2bits(D7)
        device['on'] = db7[0] > 0

    def init_adjust_device(self, device, inst):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst
        gear = D6 * 100 / 15
        device['gear'] = int(gear)

    def init_rgb_light(self, rgb_light, inst):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst
        R = hex(D5)[2:].zfill(2)
        G = hex(D6)[2:].zfill(2)
        B = hex(D7)[2:].zfill(2)
        rgb_light['rgb'] = f"#{R}{G}{B}"

    def init_ac_device(self, ds_id, ac, inst):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst
        b = byte2bits(D7)

        ac_ctrl = get_local_string("ac_ctrl", self._language)

        ac['temp'] = D6
        ac['tempZH'] = f"{D6}℃"
        ac['ctrl'] = b[3]
        ac['ctrlZH'] = ac_ctrl["auto"] if b[3] == 1 else ac_ctrl["manual"]

        if not b[4] and not b[5]:
            ac['model'] = 0
            ac['modelZH'] = ac_ctrl["heat"]
        elif b[4] and not b[5]:
            ac['model'] = 1
            ac['modelZH'] = ac_ctrl["cool"]
        elif not b[4] and b[5]:
            ac['model'] = 2
            ac['modelZH'] = ac_ctrl["dry"]
        elif b[4] and b[5]:
            ac['model'] = 3
            ac['modelZH'] = ac_ctrl["fan"]

        if not b[7] and not b[6]:
            ac['speed'] = 0
            ac['speedZH'] = ac_ctrl["low"]
        elif not b[7] and b[6]:
            ac['speed'] = 1
            ac['speedZH'] = ac_ctrl["mid"]
        elif b[7] and not b[6]:
            ac['speed'] = 2
            ac['speedZH'] = ac_ctrl["high"]
        # ambient temp D3,D4,D5
        ambient_temp_key = f"{ds_id}.243-198-{D3}-{D4}-20.7"
        ambient_temp_detai = self.get_detail_from_database(ambient_temp_key)
        if ambient_temp_detai:
            ac['ambient_temp'] = ambient_temp_detai["value"]
        # ambient humidity
        ambient_hum_key = f"{ds_id}.243-198-{D3}-{D4}-22.7"
        ambient_hum_detai = self.get_detail_from_database(ambient_hum_key)
        if ambient_hum_detai:
            ac['ambient_hum'] = ambient_hum_detai["value"]

    def init_music_player(self, ds_id: str, music: Dict[str, Any], inst: List[int]):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst
        music['vol'] = bit2byte(D6, 0, 4)
        music['chl'] = D7

        channel_names = {
            1: 'AU1',
            2: 'TF',
            3: 'AU2',
            4: 'FM'
        }
        music['chlZH'] = channel_names.get(D7, '')

        key = f"{ds_id}/243-102-{D3}-{D4}-{D5}"
        DX = self.get_data_from_database(key)
        if DX:
            music['highVol'] = DX[5] - 7
            music['lowVol'] = DX[6] - 7

        fm_key = f"{ds_id}/243-202"
        fm_DX = self.get_data_from_database(fm_key)
        if not fm_DX:
            fm_key2 = f"{ds_id}/243-202-{D3}-{D4}-{D5}"
            fm_DX = self.get_data_from_database(fm_key2)

        if fm_DX:
            fm_d6 = fm_DX[5]
            fm_d7 = fm_DX[6]
            music['fm'] = ((32.768 * (fm_d6 * 256 + fm_d7) - 950) / 4000)

    def init_warmer(self, ds_id, warmer: Dict[str, Any], inst: List[int]):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst

        b = byte2bits(D7)
        warmer['temp'] = D6 + 15
        warmer['ctrl'] = b[6]
        warmer['tempZH'] = f"{warmer['temp']}℃"
        ac_ctrl = get_local_string("ac_ctrl", self._language)
        warmer['ctrlZH'] = ac_ctrl["auto"] if b[6] == 0 else ac_ctrl["manual"]

        # ambient temp D3,D4,D5
        ambient_temp_key = f"{ds_id}.243-198-{D3}-{D4}-20.7"
        ambient_temp_detai = self.get_detail_from_database(ambient_temp_key)
        if ambient_temp_detai:
            warmer['ambient_temp'] = ambient_temp_detai["value"]
        # ambient humidity
        ambient_hum_key = f"{ds_id}.243-198-{D3}-{D4}-22.7"
        ambient_hum_detai = self.get_detail_from_database(ambient_hum_key)
        if ambient_hum_detai:
            warmer['ambient_hum'] = ambient_hum_detai["value"]

    def init_fresh_air(self, air: Dict[str, Any], inst: List[int]):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst
        ac_ctrl = get_local_string("ac_ctrl", self._language)
        air['speed'] = D6
        air['speedZH'] = {
            1: ac_ctrl["low"],
            2: ac_ctrl["mid"],
            3: ac_ctrl["high"]
        }.get(D6, '')

    def init_adjust_curtain(self, curtain, inst):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst
        curtain['scale'] = D6

    def init_sensor(self, sensor, inst):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst
        self.init_common_sensor(sensor, inst)
        self.init_sensor_name(sensor, inst)

        sensor['unit'] = ''
        if D2 == 198:
            sensor['did'] = D6

            if D6 == 20:
                if D5 >= 128:
                    sensor['value'] = -1 * (D5 - 128)
                else:
                    sensor['value'] = D5
                sensor['unit'] = '℃'
            elif D6 == 21:
                sensor['value'] = D5 * 3
                sensor['unit'] = 'lux'
            elif D6 == 22:
                sensor['value'] = D5
                sensor['unit'] = '%'

        elif (39 <= D2 <= 45) or (120 <= D2 <= 128) or D2 == 135:
            sensor['did'] = D2
            HD = D7 << 16
            MD = D6 << 8
            value = HD + MD + D5

            sensor['value'] = value
            sensor['unit'] = ''

            self.init_sensor_name2(sensor, inst)

    def init_dry_sensor(self, sensor, inst):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst
        self.init_common_sensor(sensor, inst)
        sensor['did'] = D6
        sensor['value'] = 1 if D7 == 255 else 0
        if 1 <= D6 <= 38:
            sensor['vName'] = get_local_string("trigger_on", self._language) if sensor[
                                                                                    'value'] > 0 else get_local_string(
                "trigger_off", self._language)
        else:
            sensor['vName'] = get_local_string("dry_on", self._language) if sensor['value'] > 0 else get_local_string(
                "dry_off", self._language)
        self.init_sensor_name(sensor, inst)

    def init_security(self, security, inst):
        state = self.get_security_state(inst)
        security['cover'] = state

        if state == 2:
            security['coverName'] = get_local_string("arming", self._language)
        elif state == 1:
            security['coverName'] = get_local_string("disarm", self._language)
        elif state == 0:
            security['coverName'] = get_local_string("area_arming", self._language)
        elif state == 3:
            security['coverName'] = get_local_string("room_arming", self._language)
        elif state == 4:
            security['coverName'] = get_local_string("room_disarm", self._language)
        else:
            security['coverName'] = get_local_string("unknow_state", self._language)

    def init_event(self, event, inst):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst
        if D1 == 237:
            default_floor_name = get_default_floor_name(D2, self._language)
            default_room_name = get_default_room_name(D3, self._language)
            default_device_name = get_default_scene_name(D4, self._language)
            if (default_floor_name is not None and
                    default_room_name is not None and
                    default_device_name is not None):
                event['name'] = f'Event:{default_floor_name}{default_room_name}{default_device_name}'
        elif D1 == 12 and 0<=D5<=23:
            # 12,${floor},${room},${device}, 0, 255, 255
            default_floor_name = get_default_floor_name(D2, self._language)
            default_room_name = get_default_room_name(D3, self._language)
            default_device_name = get_default_device_name(D4, self._language)
            if (default_floor_name is not None and
                    default_room_name is not None and
                    default_device_name is not None):
                event['name'] = f'Event:{default_floor_name}{default_room_name}{default_device_name} - RCKEY{D5+1}'


    def get_security_state(self, inst):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst

        if D2 == 192:
            return 1
        if D2 == 191:
            return 2
        if D2 == 193:
            return 0
        if D2 in [194, 195]:
            if D6 == 85:
                return 3
            if D6 == 0:
                return 4
            if D6 == 255:
                return 0
        return -1

    def init_common_sensor(self, sensor, inst):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst
        # 设置传感器属性
        sensor['fid'] = D3
        sensor['rid'] = D4

    def init_sensor_name(self, sensor, inst):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst

        sensor['fid'] = D3
        sensor['rid'] = D4
        sensor['did'] = D5
        default_floor_name = get_default_floor_name(D3, self._language)
        default_room_name = get_default_room_name(D4, self._language)
        default_device_name = get_default_sensor_name(D6, self._language)
        sensor['fName'] = default_floor_name
        sensor['rName'] = default_room_name
        sensor['dName'] = default_device_name

    def init_sensor_name2(self, sensor, inst):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst

        sensor['fid'] = D3
        sensor['rid'] = D4
        sensor['did'] = D2

        default_floor_name = get_default_floor_name(D3, self._language)
        default_room_name = get_default_room_name(D4, self._language)
        default_device_name = get_default_sensor_name(D2, self._language)

        sensor['fName'] = default_floor_name
        sensor['rName'] = default_room_name
        sensor['dName'] = default_device_name

    def init_dry_sensor_name(self, sensor, inst):
        D1, D2, D3, D4, D5, D6, D7, D8 = inst
        sensor['fid'] = D3
        sensor['rid'] = D4
        sensor['did'] = D5

        default_floor_name = get_default_floor_name(D3, self._language)
        default_room_name = get_default_room_name(D4, self._language)
        dry_did = f"{D2}-{D6}"
        default_device_name = get_default_dry_name(dry_did, self._language)
        sensor['fName'] = default_floor_name
        sensor['rName'] = default_room_name
        sensor['dName'] = default_device_name
