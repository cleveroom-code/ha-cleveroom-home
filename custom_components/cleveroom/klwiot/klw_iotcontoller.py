import logging
import math
from typing import List, Dict, Callable
from typing import TYPE_CHECKING

from .klw_common import Instruction

if TYPE_CHECKING:
    from .klw_iotclient import KLWIOTClient


class KLWIOTController:
    def __init__(self, iotserver):
        self.klwiot: 'KLWIOTClient' = iotserver
        self.__logger = None

    def enable_logger(self):
        logger = logging.getLogger('IOTController')
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(ch)
        self.__logger = logger

    def disable_logger(self):
        self.__logger = None

    def log(self, *args):
        if self.__logger:
            # Convert all parameters to strings and merge
            message_parts = [str(arg) for arg in args]
            message = " - ".join(message_parts)
            # Log the message according to the level
            self.__logger.debug(message)

    def execute(self, cmd):
        """
        Execute the command, the complete instruction format is as follows
        cmd format:
        {
            "header": {
                "namespace": "IOT.Control",
                "action": "DeviceOn"
            },
            "payload": [
                {"oid":"81b2ab1bf4ebf77f.243-199-1-6-205.3"},
            ]
        }
        :return:
        """
        header = cmd.get('header', {})
        payload = cmd.get('payload', [])

        namespace = header.get('namespace')
        action = header.get('action')

        if namespace == 'IOT.Control':
            self.control(action, payload)

    def control(self, action, payload):
        """
            IOT.Control namespace to control devices
        """
        try:
            if action == 'DeviceOn':
                self.device_on(payload)
            elif action == 'DeviceOff':
                self.device_off(payload)
            elif action == 'DeviceToggle':
                self.device_toggle(payload)
            elif action == 'SceneTrigger':
                self.scene_trigger(payload)
            elif action == 'SetBrightness':
                self.set_brightness(payload)
            elif action == 'IncBrightness':
                self.inc_brightness(payload)
            elif action == 'DecBrightness':
                self.dec_brightness(payload)
            elif action == 'SetColor':
                self.set_color(payload)
            elif action == 'SetColorTemperature':
                self.set_color_temperature(payload)
            elif action == 'SetTemperature':
                self.set_temperature(payload)
            elif action == 'IncTemperature':
                self.inc_temperature(payload)
            elif action == 'DecTemperature':
                self.dec_temperature(payload)
            elif action == 'SetGear':
                self.set_gear(payload)
            elif action == 'SetMode':
                self.set_mode(payload)
            elif action == 'SetAuto':
                self.set_auto(payload)
            elif action == 'SetSpeed':
                self.set_speed(payload)
            elif action == 'SetSpeedLow':
                self.set_speed_low(payload)
            elif action == 'SetSpeedMid':
                self.set_speed_mid(payload)
            elif action == 'SetSpeedHigh':
                self.set_speed_high(payload)
            elif action == 'SetVolume':
                self.set_volume(payload)
            elif action == 'IncVolume':
                self.inc_volume(payload)
            elif action == 'DecVolume':
                self.dec_volume(payload)
            elif action == 'SendRCKey':
                self.set_rckey(payload)
            elif action == 'ShadeOpen':
                self.shade_open(payload)
            elif action == 'ShadeClose':
                self.shade_close(payload)
            elif action == 'ShadePause':
                self.shade_pause(payload)
            elif action == 'SetShadeScale':
                self.set_shade_scale(payload)
            elif action == 'SetSecurity':
                self.set_security(payload)
            elif action == 'SetVolume':
                self.set_volume(payload)
            elif action == 'IncVolume':
                self.inc_volume(payload)
            elif action == 'DecVolume':
                self.dec_volume(payload)
            elif action == 'SetPrevSong':
                self.set_prev_song(payload)
            elif action == 'SetNextSong':
                self.set_next_song(payload)
            elif action == 'SetSongFolder':
                self.set_song_folder(payload)
            elif action == 'SetSource':
                self.set_source(payload)
            elif action == 'SetCommand':
                self.set_command(payload)

        except Exception as e:
            self.log(f"Error in control: {e}")

    def send_control_commands(self, insts) -> None:
        """
        Send control commands
        """
        for inst in insts:
            self.klwiot.async_send(inst)

    def create_action(self, payload, create_instruction) -> List[Instruction]:
        """
        Create action instruction
        """
        cmds = []
        try:
            if isinstance(payload, list) and len(payload) > 0:
                for item in payload:
                    oid = item.get('oid')
                    if oid:
                        info = self.klwiot.devicebucket.get_detail_from_database(oid)
                        if info:
                            inst = create_instruction(info, item)
                            # inst may be an array or a single object, determine the type
                            if inst:
                                if isinstance(inst, list):
                                    cmds.extend(inst)
                                else:
                                    cmds.append(inst)
        except Exception as e:
            print(f"Error creating action: {e}")
        return cmds

    def sort_cmds_with_frd(self, cmds: List[Instruction]) -> None:
        """
            Sort commands according to fid,rid,did, and arrange devices in the same area together for batch control
        """
        cmds.sort(key=lambda x: (x.get_d3(), x.get_d4(), x.get_d5()))

    # Device control methods
    def device_on(self, payload) -> None:
        """Turn on the device"""
        self.log("DeviceOn", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return Instruction(f"243,154,{fid},{rid},{did},0,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def device_off(self, payload) -> None:
        """Turn off the device"""
        self.log("DeviceOff", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return Instruction(f"243,158,{fid},{rid},{did},0,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def device_toggle(self, payload) -> None:
        """Turn off the device"""
        self.log("DeviceToggle", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return Instruction(f"243,159,{fid},{rid},{did},0,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    # Scene control
    def scene_trigger(self, payload) -> None:
        """Trigger a scene"""
        self.log("SceneTrigger", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return Instruction(f"237,{fid},{rid},{did},0,0,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    # Brightness control
    def set_brightness(self, payload) -> None:
        """Set brightness"""
        self.log("SetBrightness", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            value = item.get('value', 0)
            # Convert brightness value from 0-100 to 0-15
            gear = math.floor(value / 100 * 15)
            return Instruction(f"243,165,{fid},{rid},{did},{gear},0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def inc_brightness(self, payload) -> None:
        """Increase brightness"""
        self.log("IncBrightness", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return Instruction(f"243,160,{fid},{rid},{did},0,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def dec_brightness(self, payload) -> None:
        """Decrease brightness"""
        self.log("DecBrightness", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return Instruction(f"243,161,{fid},{rid},{did},0,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    # Color control
    def set_color(self, payload) -> None:
        """Set color"""
        self.log("SetColor", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            color = item.get('value', {"r": 255, "g": 255, "b": 255})
            r = color.get('r', 255);
            g = color.get('g', 255);
            b = color.get('b', 255)
            return Instruction(f"112,{fid},{rid},{did},{r},{g},{b}")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def set_color_temperature(self, payload) -> None:
        """Set color temperature"""
        self.log("SetColorTemperature", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            value = item.get('value')
            if value is None:
                return None
            if value > 100:
                value = 100
            if value < 0:
                value = 0
            return Instruction(f"112,{fid},{rid},{did},{100 - value},0,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    # Temperature control
    def set_temperature(self, payload) -> None:
        """Set temperature"""
        self.log("SetTemperature", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            value = item.get('value')
            if value is None:
                return None
            if value > 30:
                value = 30
            if value < 15:
                value = 15
            return Instruction(f"46,{fid},{rid},{did},{value - 15},0,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def inc_temperature(self, payload) -> None:
        """Increase temperature"""
        self.log("IncTemperature", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return Instruction(f"243,160,{fid},{rid},{did},0,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def dec_temperature(self, payload) -> None:
        """Decrease temperature"""
        self.log("DecTemperature", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return Instruction(f"243,161,{fid},{rid},{did},0,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    # Gear and mode control
    def set_gear(self, payload) -> None:
        """Set gear"""
        self.log("SetGear", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            value = item.get('value')
            if value is None:
                return None
            if value > 15:
                value = 15
            if value < 0:
                value = 0
            return Instruction(f"243,165,{fid},{rid},{did},{value},0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def set_mode(self, payload) -> None:
        """Set mode"""
        self.log("SetMode", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            mode = item.get('value')
            if mode is None:
                return None
            if mode > 4:
                mode = 4
            if mode < 0:
                mode = 0
            modes = [18, 17, 4, 5]
            return Instruction(f"243,164,{fid},{rid},{did},{modes[mode]},0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    # Manual-automatic control
    def set_auto(self, payload) -> None:
        """Set automatic mode"""
        self.log("SetAuto", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            value = item.get('value')
            if value is None:
                return None
            if value > 1:
                value = 1
            if value < 0:
                value = 0

            modes = [23, 22]
            return Instruction(f"243,164,{fid},{rid},{did},{modes[value]},0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    # Speed control
    def set_speed(self, payload) -> None:
        """Set speed"""
        self.log("SetSpeed", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            value = item.get('value')
            if value is None:
                return None
            if value > 2:
                value = 2
            if value < 0:
                value = 0
            modes = [19, 20, 21]
            return Instruction(f"243,164,{fid},{rid},{did},{modes[value]},0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def set_speed_low(self, payload) -> None:
        """Set low speed"""
        self.log("SetSpeedLow", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return Instruction(f"243,164,{fid},{rid},{did},19,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def set_speed_mid(self, payload) -> None:
        """Set medium speed"""
        self.log("SetSpeedMid", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return Instruction(f"243,164,{fid},{rid},{did},20,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def set_speed_high(self, payload) -> None:
        """Set high speed"""
        self.log("SetSpeedHigh", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return Instruction(f"243,164,{fid},{rid},{did},21,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def set_rckey(self, payload) -> None:
        """Send remote control key"""
        self.log("SendRCKey", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            value = item.get('value')
            if value is None:
                return None
            if 0 <= value <= 23:
                # Remote control keys 0-23, a total of 24 keys at most
                return Instruction(f"243,164,{fid},{rid},{did},{value},0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    # Curtain control
    def shade_open(self, payload) -> None:
        """Open the curtain"""
        self.log("ShadeOpen", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return [Instruction(f"243,154,{fid},{rid},{did},0,0")]

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def shade_close(self, payload) -> None:
        """Close the curtain"""
        self.log("ShadeClose", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return [Instruction(f"243,158,{fid},{rid},{did},0,0")]

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def shade_pause(self, payload) -> None:
        """Pause the curtain"""
        self.log("ShadePause", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return [Instruction(f"243,187,{fid},{rid},{did},0,0")]

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def set_shade_scale(self, payload) -> None:
        """Set curtain position"""
        self.log("SetShadeScale", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            scale = item.get('value')
            if scale is None:
                return None
            if scale > 100:
                scale = 100
            if scale < 0:
                scale = 0
            newscale = math.floor(scale / 100 * 10)
            return Instruction(f"243,164,{fid},{rid},{did},{newscale + 6},0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def set_security(self, payload) -> None:
        """Set security"""
        self.log("SetSecurity", payload)

        def create_inst(info, item):
            value = item.get('value')
            if value is None:
                return None
            if value == 2:
                return Instruction(f"243,169,0,0,0,0,0")
            else:
                return Instruction(f"243,170,0,0,0,0,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

        # Volume control

    def set_volume(self, payload) -> None:
        """Set volume"""
        self.log("SetVolume", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            volume = item.get('value')
            if volume is None:
                return None
            if volume > 100:
                volume = 100
            if volume < 0:
                volume = 0
            # Convert volume value from 0-100 to 0-18
            volume = math.floor(volume / 100 * 18)
            return Instruction(f"243,165,{fid},{rid},{did},{volume},136")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def inc_volume(self, payload) -> None:
        """Increase volume"""
        self.log("IncVolume", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return Instruction(f"243,160,{fid},{rid},{did},0,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def dec_volume(self, payload) -> None:
        """Decrease volume"""
        self.log("DecVolume", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return Instruction(f"243,161,{fid},{rid},{did},0,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)
        # Volume control

    def set_prev_song(self, payload) -> None:
        """Previous song"""
        self.log("SetPrevSong", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return Instruction(f"243,162,{fid},{rid},{did},0,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def set_next_song(self, payload) -> None:
        """Next song"""
        self.log("SetNextSong", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            return Instruction(f"243,163,{fid},{rid},{did},0,0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def set_song_folder(self, payload) -> None:
        """Set song folder"""
        self.log("SetSongFolder", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            folder = item.get('value')
            if folder is None:
                return None
            if 0 <= folder <= 6:
                return Instruction(f"243,223,{fid},{rid},{did},{folder + 10},0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def set_source(self, payload) -> None:
        """Set audio source"""
        self.log("SetSource", payload)

        def create_inst(info, item):
            fid, rid, did = info['fid'], info['rid'], info['did']
            source = item.get('value')
            if source is None:
                return None
            if 1 <= source <= 4:
                return Instruction(f"243,165,{fid},{rid},{did},{source},0")

        cmds = self.create_action(payload, create_inst)
        self.sort_cmds_with_frd(cmds)
        self.send_control_commands(cmds)

    def set_command(self, payload) -> None:
        """Set command
        [{"cmd":[243,1,1,6,205,0,0,38]}]
        """
        self.log("SetCommand", payload)
        commands = []
        # 选好遍历payload数组
        if payload is None:
            return
        if len(payload) < 1:
            return
        # 选好遍历cmd
        # 遍历 payload
        for item in payload:
            cmd = item.get('cmd')
            #判断datas是是str类型，如果是的话需要对str进行拆分 '243,154,1,6,206,0,0,38',然后转成数字类型
            if cmd is None:
                continue
            if isinstance(cmd, str):
                splits = cmd.split(',')
                datas = [int(x) for x in splits]
            else:
                datas = item.get('cmd')
            if len(datas) < 7:
                continue
            inst = Instruction(datas)
            commands.append(inst)
        self.send_control_commands(commands)
