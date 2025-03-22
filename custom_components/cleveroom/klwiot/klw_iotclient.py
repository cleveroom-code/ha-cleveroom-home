import asyncio
import socket
import struct
import threading
import time
import queue
import logging
import hashlib
from typing import Union, List, Optional, Callable, Any, Coroutine

from .klw_iotcontoller import KLWIOTController
from .klw_type import BufferType
from .klw_bucket import DeviceBucket
from .klw_type import DeviceType
from .klw_common import Instruction, CRMDevice, DeviceBuffer, safe_merge_objects, ascii_to_hex, get_current_time
from .klw_eventemitter import KLWEventEmitter


class KLWIOTClient(KLWEventEmitter):
    """
     :events
        on_login_success : when login success
        on_login_failed  : when login failed
        on_connect_change: connect state change
        on_device_change : device state change

    """

    def __init__(self, host='192.168.1.178', port=4002, client_id=None, password="1234", system_level=0,
                 connect_timeout=10, reconnect_interval=15, keeplive=True, language='zh-Hans', bucket_manager=None,
                 data_changed_callback: Callable[[], None] = None):
        """
        :param host: cleveroom system host
        :param port: cleveroom system port
        :param client_id: client id (if None, use host md5)
        :param system_level: system level 0~5,
         0 - up to 50 devices, 50ms interval,
         1 - up to 100 devices, 100ms interval,
         2 - up to 200 devices, 200ms interval, 3 -up to 300 devices, 500ms interval, depending on the actual installation environment.
        :param connect_timeout: Connection timeout, in seconds (Under normal service conditions, it should not exceed 10 seconds. Exceeding this indicates an unstable network)
        :param reconnect_interval: Reconnect interval, in seconds (The reconnection logic is that it must be accessible initially to trigger reconnection)
        """
        super().__init__()

        ###----socket----###
        self.logger_on = None
        self._is_living = None
        self.send_thread = None
        self.receive_thread = None
        self.host = host
        self.port = port
        self.gwpwd = password
        # 如果client_id为空，则使用使用host的md5值
        self.__init_client_id(client_id)
        self.reconnect_interval = reconnect_interval
        self.connect_timeout = connect_timeout
        self.client = None
        self.running = False
        self.connected = False
        self.reconnect_thread = None
        self.ever_connected = False
        self.waiting_commands = queue.Queue()  # async message queue
        self.input_thread = None  # input thread
        self.__logger = None  # logger setting
        self._authed = False  # default not authed
        self.system_level = system_level
        self.keeplive = keeplive  # 启动以后就一直尝试重连
        self.show_stop_scene = False
        self._language = language
        ###----buissness----###
        self.data_buffer = []  # data cache
        self.allowed_d1 = {243, 112, 250, 35, 37, 38, 62, 87, 22,237}
        self.heartbeat_interval = 15  # headbeat interval
        # Initialize buffers
        self.__devbuffer = DeviceBuffer(BufferType.DEVICEBUFFER)
        self.__scenebuffer = DeviceBuffer(BufferType.SCENEBUFFER)
        self.__sensorbuffer = DeviceBuffer(BufferType.SENSORBUFFER)
        self.__sensorextendbuffer = DeviceBuffer(BufferType.SENSOREXBUFFER)
        self.__securitybuffer = DeviceBuffer(BufferType.SECURITYBUFFER)
        self.__alarmbuffer = DeviceBuffer(BufferType.ALARMBUFFER)
        self.__timebuffer = DeviceBuffer(BufferType.TIMEBUFFER)
        self.__fmbuffer = DeviceBuffer(BufferType.FMBUFFER)
        self.__volbuffer = DeviceBuffer(BufferType.VOLBUFFER)
        self.__versionbuffer = DeviceBuffer(BufferType.VERSIONBUFFER)
        self.__gwbuffer = DeviceBuffer(BufferType.GWBUFFER)
        self.__pwdbuffer = DeviceBuffer(BufferType.GWPASSWORDBUFFER)
        self.__clockbuffer = DeviceBuffer(BufferType.CLOCKBUFFER)
        self.__rgbbuffer = DeviceBuffer(BufferType.RGBBUFFER)
        self.__cachebuffer = DeviceBuffer(BufferType.CACHEBUFFER)
        self.__f199buffer = DeviceBuffer(BufferType.CACHEBUFFER)
        self.__curtainbuffer = DeviceBuffer(BufferType.CURTAINBUFFER)

        self.__triggerbuffer = DeviceBuffer(BufferType.EVENTBUFFER)

        # Initialize feedback callbacks
        self.__feedback_callbacks = {}
        # client the last data update timestamp
        self._last_timestamp = None
        # Initialize device buckets
        self.devicebucket = DeviceBucket(client_id=self.client_id, persistence=True, language=self._language,
                                         bucket_manager=bucket_manager, data_changed_callback=data_changed_callback)
        self.__buffers_register()
        self.__register_controller()

    def __buffers_register(self):
        buffers = [
            self.__devbuffer,
            self.__scenebuffer,
            self.__sensorbuffer,
            self.__sensorextendbuffer,
            self.__volbuffer,
            self.__rgbbuffer,
            self.__cachebuffer,
            self.__securitybuffer,
            self.__triggerbuffer
        ]
        for bf in buffers:
            bf.add_listener("inner_buffer", {
                'on_add': self.on_add_device,
                'on_change': self.on_change_device
            })

    def __register_controller(self):
        self.controller = KLWIOTController(self)

    def __init_client_id(self, client_id):
        if not client_id:
            m = hashlib.md5()
            m.update(self.host.encode('utf-8'))
            client_id = m.hexdigest()
        self.client_id = client_id

    async def delayed_task(self, delay_seconds: float, callback, *args, **kwargs):
        """Asynchronously execute the delayed task."""
        await asyncio.sleep(delay_seconds)
        return callback(*args, **kwargs)

    async def set_timeout(self, delay_seconds: float, callback, *args, **kwargs):
        """Simulate the setTimeout function."""
        # Create a task but do not wait
        task = asyncio.create_task(
            self.delayed_task(delay_seconds, callback, *args, **kwargs)
        )
        return task

    async def delayed_device_create_or_update(self, device: CRMDevice, buff_type):
        await self.set_timeout(0.2, self.on_device_create_or_update, device, buff_type)
        # self.on_device_create_or_update(device, buff_type)

    def on_add_device(self, device: CRMDevice, buff_type):
        # self.log(f"Added:{device}, Type:{buff_type}")
        if buff_type == BufferType.RGBBUFFER:
            # asyncio.run(self.delayed_device_create_or_update(device, buff_type))
            pass
        else:
            self.on_device_create_or_update(device, buff_type)

    def on_change_device(self, device: CRMDevice, buff_type):
        # self.log(f"Updated:{device}, Type:{buff_type}")
        # Determine if it is RGBBUFFER type data, it should be processed with a delay of 200ms
        if buff_type == BufferType.RGBBUFFER:
            # asyncio.run(self.delayed_device_create_or_update(device, buff_type))
            pass
        else:
            self.on_device_create_or_update(device, buff_type)

    def on_device_create_or_update(self, device: CRMDevice, buff_type):
        # Get basic information
        ds_id = self.client_id
        inst = device.get_inst().get_inst()
        buffer_type = buff_type
        uid = device.get_uid()

        cod = self.devicebucket.create_object_detail(ds_id, inst, buffer_type, uid)
        # print raw
        # print(cod)
        # Create object details
        if not cod:
            # If parsing fails, return directly
            return
        ori_obj = cod.get('oriObj')
        change_obj = cod.get('changeObj')
        # Merge data, deep copy to prevent modification
        merge_obj = safe_merge_objects(ori_obj, change_obj)

        if merge_obj:
            # Filter invalid data
            if (merge_obj.get('category') == DeviceType.SENSOR and
                    (merge_obj.get('fid', 0) >= 255 or merge_obj.get('rid', 0) >= 255)):
                return

            if merge_obj.get('did', 0) >= 255:
                return

            # RGB information type conversion
            if buffer_type == BufferType.RGBBUFFER:
                buffer_type = BufferType.DEVICEBUFFER

            # Build object ID
            oid = f"{ds_id}.{uid}.{buffer_type}"
            # Add timestamp
            merge_obj['timestamp'] = int(time.time() * 1000)
            # Build complete object
            raw = {
                'nid': ds_id,
                'oid': oid,
                'data': inst,
                'uid': uid,
                'type': buffer_type,
                'detail': merge_obj,
            }
            # Update cache
            # Determine whether it is the first creation or update of data
            is_new = persistence = (ori_obj is None)
            self.devicebucket.save_device_to_database(oid, raw, is_new)
            # self.devicebucket.save_device_to_database(oid, raw, True)
            # Trigger listener
            self.emit('on_device_change', raw, is_new=is_new)

    def get_devicebucket(self) -> DeviceBucket:
        return self.devicebucket

    def enable_logger(self):
        """
         Configure the logger
        :return:
        """
        logger = logging.getLogger('Cleveroom')
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(ch)
        self.__logger = logger
        self.controller.enable_logger()

    def disable_logger(self):
        """
        Disable the logger
       :return:
       """
        self.__logger = None
        self.controller.disable_logger()

    def log(self, *args):
        if self.__logger:
            # Convert all parameters to strings and merge
            message_parts = [str(arg) for arg in args]
            message = " - ".join(message_parts)
            # Log the message according to the level
            self.__logger.debug(message)

    def create_socket(self):
        if self.client:
            try:
                self.client.close()
            except:
                pass
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.settimeout(self.connect_timeout)  # Connection timeout, in seconds

    def get_crm_key_ins(self):
        pwdb = ascii_to_hex(self.gwpwd)
        # Calculate the group size
        size = (len(pwdb) + 3) // 4  # Round up division
        # Store the instruction list
        inslt = []
        # Generate instructions
        for i in range(size):
            idx = i * 4
            # Get four bytes, and use 255 to fill if it exceeds the length
            d4 = pwdb[idx] if idx < len(pwdb) else 255
            d5 = pwdb[idx + 1] if idx + 1 < len(pwdb) else 255
            d6 = pwdb[idx + 2] if idx + 2 < len(pwdb) else 255
            d7 = pwdb[idx + 3] if idx + 3 < len(pwdb) else 255
            # Create an instruction object
            ins = Instruction([243, 131, i + 1, d4, d5, d6, d7])
            inslt.append(ins)
            # Check if you need to add the last instruction
            if i == size - 1:
                if not all(x == 255 for x in [d4, d5, d6, d7]):
                    last_ins = Instruction([243, 131, i + 2, 255, 255, 255, 255])
                    inslt.append(last_ins)

        return inslt

    def login(self):
        # Log in to the system
        inslist = self.get_crm_key_ins()
        for ins in inslist:
            self.async_send(ins)
        # Wait for login results
        time.sleep(2)  # 1 second delay to check the result
        if self._is_logined():
            self._authed = True
        else:
            self._authed = False

        return self._authed

    def _is_logined(self) -> bool:
        """
        Check if logged in
        """
        buf = self.__pwdbuffer.get_device_list() if self.__pwdbuffer else []
        if buf and len(buf) > 0:
            dev = buf[0].get_inst()
            # Check device status
            return all(
                getattr(dev, f'get_d{i}')() == 0
                for i in range(3, 8)
            )
        return False

    def _after_login(self):
        """
        Processing after successful login
        """
        # Start the heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self.heartbeat_handler)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()
        # Query all devices
        self.query_all_devices()

    def query_all_devices(self):
        """
        Query all devices
        """
        instlist = [
            Instruction('243, 166, 255, 0, 0, 0, 0'),
            Instruction('243, 168, 0, 0, 0, 0, 0'),
            Instruction('243, 180, 0, 0, 0, 0, 0'),
            Instruction('243, 110, 0, 0, 0, 0, 0')
        ]
        for inst in instlist:
            self.async_send(inst)

    def connect(self):
        self.running = True
        if not self.attempt_connection():
            pass
            # self.running = False
            # return False
            # self.handle_disconnection()

        # Start the input processing thread
        self.input_thread = threading.Thread(target=self.handle_input)
        self.input_thread.daemon = False
        self.input_thread.start()

        # Start the reconnection thread
        self.reconnect_thread = threading.Thread(target=self.auto_reconnect)
        self.reconnect_thread.daemon = True
        self.reconnect_thread.start()

        return True

    def attempt_connection(self):
        self.create_socket()
        try:
            self.client.connect((self.host, self.port))
            self.connected = True
            self.ever_connected = True
            print(f"{get_current_time()} Successfully connected to {self.host}:{self.port}")
            # Remove timeout limit after successful connection
            self.client.settimeout(None)
            # Start sending and receiving threads
            self.receive_thread = threading.Thread(target=self.receive_messages)
            self.send_thread = threading.Thread(target=self.__async_send_messages_handler)
            self.receive_thread.daemon = True
            self.send_thread.daemon = True
            self.receive_thread.start()
            self.send_thread.start()
            # Log in to the system
            self.login()
            self.log("Login system:" + str(self._authed))
            if self._authed:
                self.emit('on_login_success')
                self._after_login()
            else:
                self.emit('on_login_failed')

            return True
        except socket.timeout:
            print(f"{get_current_time()} Connection timeout after {self.connect_timeout} seconds")
            self.connected = False
            self.handle_disconnection()
            return False
        except ConnectionRefusedError:
            print(f"{get_current_time()} Connection failed. Server not available.")
            self.connected = False
            self.handle_disconnection()
            return False
        except Exception as e:
            print(f"{get_current_time()} Connection error: {str(e)}")
            self.connected = False
            self.handle_disconnection()
            return False

    def handle_input(self):
        """New thread (non-daemon thread) to handle user input"""
        while self.running:
            time.sleep(1)

    def pack_binary_data(self, data: Union[bytes, bytearray, List[int]]) -> bytes:
        if isinstance(data, bytes):
            return data
        elif isinstance(data, list):
            # Package the integer list into binary
            return struct.pack(f'{len(data)}B', *data)
        elif isinstance(data, bytearray):
            return bytes(data)
        else:
            raise ValueError("Unsupported data type")

    def async_send(self, inst: Instruction):
        """Asynchronously send a message"""
        if not self.connected:
            print(f"{get_current_time()} Not connected to server", inst)
            return
        self.log(f"Waiting Send: {inst}")
        self.waiting_commands.put(inst)

    def sync_send(self, inst: Instruction):
        """Synchronously send a message"""
        if not self.connected:
            print(f"{get_current_time()} Not connected to server")
            return
        data = inst.get_inst()
        self.log(f"Sync Send: {self._get_decs(data)}")
        self._send_data(data)

    async def async_send_list(self, insts: List[Instruction], interval: float = 1.0) -> None:
        """Asynchronously send a list of instructions, with custom interval time"""
        if not self.connected:
            print(f"{get_current_time()} Not connected to server")
            return
        for inst in insts:
            try:
                data = inst.get_inst()
                self.log(f"Async Send: {self._get_decs(data)}")
                self._send_data(data)
                # Use asynchronous wait instead of time.sleep
                await asyncio.sleep(interval)
            except Exception as e:
                print(f"Failed to send instruction: {e}")
                # You can choose to continue sending or interrupt
                # break

    def _send_data(self, data: Union[bytes, bytearray, List[int]]):
        # Convert to bytearray
        cmds = self.pack_binary_data(data)
        self.client.send(cmds)

    def __async_send_messages_handler(self):
        """Thread function to send messages"""
        while self.running:
            if not self.connected:
                time.sleep(1)
                continue
            try:
                # Use the queue to get messages, set a timeout to avoid blocking
                try:
                    inst = self.waiting_commands.get(timeout=1)
                    if self.connected:
                        data = inst.get_inst()
                        self.log(f"Async Send: {self._get_decs(data)}")
                        self._send_data(data)
                        # Wait to ensure that there is an interval between the sent commands
                        time.sleep(self.get_sleep_time())

                except queue.Empty:
                    continue
            except Exception as e:
                print(f"{get_current_time()} Send error: {str(e)}")
                time.sleep(1)

    def get_sleep_time(self):
        """
        Get the instruction interval time according to the system level
        :return:
        """
        if self.system_level == 0:
            return 0.05
        elif self.system_level == 1:
            return 0.1
        elif self.system_level == 2:
            return 0.2
        elif self.system_level == 3:
            return 0.3
        else:
            return 0.5

    def auto_reconnect(self):
        while self.running:
            # if not self.connected and self.ever_connected:
            if self.running and not self._authed:
                print(f"{get_current_time()} Attempting to reconnect in {self.reconnect_interval} seconds...")
                time.sleep(self.reconnect_interval)
                if self.attempt_connection():
                    print(f"{get_current_time()} Reconnection successful!")
            time.sleep(1)

    def receive_messages(self):
        while self.running:
            if not self.connected:
                time.sleep(1)
                continue
            try:
                data = self.client.recv(1024)
                if data:
                    datas_hex = self._get_decs(data)
                    self.log(f"Received: {datas_hex}")
                    self.data_buffer.extend(data)
                    self.split_datas()
                else:
                    print(f"{get_current_time()} Server disconnected")
                    self.handle_disconnection()
                    break
            except ConnectionResetError:
                print(f"{get_current_time()} Connection reset by server")
                self.handle_disconnection()
                break
            except Exception as e:
                print(f"{get_current_time()} Receive error: {str(e)}")
                self.handle_disconnection()
                break

    def heartbeat_handler(self):
        while self.running:

            time.sleep(self.heartbeat_interval)
            if self.connected and self._authed:
                # Send heartbeat instruction
                ins = Instruction([243, 255, 255, 255, 255, 255, 255])
                self.async_send(ins)
            # Check if no data has been received for more than 3 cycles, it is considered that the connection is disconnected and a reconnection operation is required
            if self._last_timestamp and (
                    time.time() * 1000 - self._last_timestamp > 3 * self.heartbeat_interval * 1000):
                print(f"{get_current_time()} Connection timeout, reconnecting...")
                self.handle_disconnection()
                break

    def split_datas(self):
        """
        Split and process the data packets in the data buffer. The processed data will be removed from the buffer to avoid data accumulation
        """
        buf = self.data_buffer
        processed_length = 0  # Record the length of processed data

        while len(buf) > 0:
            if len(buf) >= 4 and buf[0] == 0x77 and buf[1] == 0x55 and buf[2] == 0x33 and buf[3] == 0x11:
                # Header verification passed
                if len(buf) < 14:
                    break
                data_len = buf[13]
                pack_len = 14 + data_len + 2

                if len(buf) >= pack_len:
                    data = buf[:pack_len]
                    processed_length += pack_len
                    self._translate_plc(data)
                    buf = buf[pack_len:]
                else:
                    break
            else:
                if len(buf) >= 8:
                    data = buf[:8]
                    processed_length += 8
                    self._translate(data)
                    buf = buf[8:]
                else:
                    break

        # Update the buffer, removing the processed data
        if processed_length > 0:
            self.data_buffer = self.data_buffer[processed_length:]

        # Update timestamp
        self._last_timestamp = time.time() * 1000
        self.set_living(True)

    def _is_available_dx(self, dx) -> bool:
        """Check if the target value dx is in the allowed list"""
        return dx in self.allowed_d1

    def _translate_plc(self, data):
        # Placeholder for PLC translation logic
        pass

    def _translate(self, data):
        ins = Instruction(data)
        if self._is_available_dx(ins.get_d1()):
            self._add_to_device_list(ins)

        # Respond to asynchronous callbacks
        self.process_callbacks(ins)

    def process_callbacks(self, data, is_plc=False) -> None:
        # Create a copy of the callback list to iterate
        callbacks = list(self.__feedback_callbacks.items())
        for key, callback in callbacks:
            try:
                if callback:
                    callback(data, is_plc)
            except Exception as e:
                print(f"Error processing callback {key}: {e}")
                # You can choose whether to remove the erroneous callback
                self.__feedback_callbacks.pop(key, None)

    def _add_to_device_list(self, ins):
        ins_bit = ins.get_inst()
        # D1 = ins_bit[0]
        # D2 = ins_bit[1]
        D1, D2, D3, D4, D5, D6, D7, D8 = ins_bit

        if D1 == 35:
            self.__clockbuffer.add(ins, [0, 1, 2, 3, 4, 5, 6])
        elif D1 == 37:
            self.__clockbuffer.clear()
        elif D1 == 62:
            if ins_bit[1] == 1:
                if ins_bit[5] == 3:
                    self.__gwbuffer.add(ins, [0, 1, 2, 3, 4, 5, 6])
                elif ins_bit[5] == 2:
                    self.__versionbuffer.add(ins, [0, 1, 2, 3, 4, 5, 6])
        elif D1 == 250:
            if self.is_live_dev(D4) and self.is_valid_room(D3) and self.is_valid_floor(D2):
                self.__rgbbuffer.add_with_uid(ins, f"243-199-{D2}-{D3}-{D4}")

        elif D1 == 243:
            cmd = ins_bit[1]
            if cmd == 102:
                self.__volbuffer.add(ins, [0, 1, 2, 3, 4])
            elif cmd in [39, 40, 41, 42, 43, 44, 45, 120, 121, 122, 123, 124, 125, 126, 127, 128, 135]:
                if self.is_valid_room(D4) and self.is_valid_floor(D3):
                    self.__sensorbuffer.add(ins, [0, 1, 2, 3])
            elif cmd == 130:
                self.__pwdbuffer.add(ins, [0, 1])
            elif cmd in [191, 192, 193]:
                self.__securitybuffer.add(ins, [0])
            elif cmd == 129:
                if self.is_valid_scene(D5) and self.is_valid_room(D4) and self.is_valid_floor(D3):
                    if (D3 > 0 and D4 == 0) or (D3 == 0 and D4 > 0):
                        pass
                    else:
                        self.__scenebuffer.add(ins, [0, 1, 2, 3, 4])
            elif cmd == 199:
                if self.is_live_dev(D5) and self.is_valid_room(D4) and self.is_valid_floor(D3):
                    if (D3 > 0 and D4 == 0) or (D3 == 0 and D4 > 0):
                        pass
                    else:
                        self.__f199buffer.add(ins, [1, 2, 3, 4])
                        self.__devbuffer.add(ins, [0, 1, 2, 3, 4])
            elif cmd == 200:
                if self.is_live_dev(D5) and self.is_valid_room(D4) and self.is_valid_floor(
                        D3) and self.is_available_infrared(D6, D7):
                    key199 = f"199-{D3}-{D4}-{D5}"
                    crm_device199 = self.__f199buffer.get_device_by_id(key199)

                    if not crm_device199:
                        # 如果199设备不存在，将200指令转换为199指令
                        ins199 = Instruction(f"{D1},199,{D3},{D4},{D5},0,0")
                        # 添加到199缓冲区
                        self.__f199buffer.add(ins199, [1, 2, 3, 4])
                        # 添加到设备缓冲区
                        self.__devbuffer.add(ins, [0, 1, 2, 3, 4])

            elif cmd == 201:
                if self.is_live_dev(D5) and self.is_valid_room(D4) and self.is_valid_floor(D3):
                    if (D3 > 0 and D4 == 0) or (D3 == 0 and D4 > 0):
                        pass
                    else:
                        self.__devbuffer.add(ins, [0, 1, 2, 3, 4])
            elif cmd == 202:
                self.__fmbuffer.add(ins, [0, 1, 2, 3, 4])
            elif cmd == 203:
                self.__cachebuffer.add(ins, [0, 1, 2, 3, 4])
            elif cmd == 204:
                if self.is_live_dev(D5) and self.is_valid_room(D4) and self.is_valid_floor(D3):
                    if (D3 > 0 and D4 == 0) or (D3 == 0 and D4 > 0):
                        pass
                    else:
                        self.__devbuffer.add(ins, [0, 1, 2, 3, 4])
            elif cmd in [194, 195]:
                self.__securitybuffer.add(ins, [0, 2, 3])
                if self.is_valid_room(D4) and self.is_valid_floor(D3):
                    if (D3 > 0 and D4 == 0) or (D3 == 0 and D4 > 0):
                        pass
                    else:
                        self.__sensorbuffer.add(ins, [0, 1, 2, 3, 6])

            elif cmd in [196, 197]:
                if self.is_valid_room(D4) and self.is_valid_floor(D3):
                    if (D3 > 0 and D4 == 0) or (D3 == 0 and D4 > 0):
                        pass
                    else:
                        self.__sensorbuffer.add(ins, [0, 1, 2, 3])
            elif cmd == 198:
                if self.is_valid_room(D4) and self.is_valid_floor(D3) and 20 <= D6 <= 22:
                    if (D3 > 0 and D4 == 0) or (D3 == 0 and D4 > 0):
                        pass
                    else:
                        self.__sensorbuffer.add(ins, [0, 1, 2, 3, 5])
                elif self.is_valid_room(D4) and self.is_valid_floor(D3) and self.is_valid_extend_sensor(D6):
                    if (D3 > 0 and D4 == 0) or (D3 == 0 and D4 > 0):
                        pass
                    else:
                        self.__sensorextendbuffer.add(ins, [0, 1, 2, 3, 5])

            elif cmd == 98:
                if self.is_valid_room(D4) and self.is_valid_floor(D3) and (
                        self.is_valid_extend_sensor(D6) or 101 <= D6 <= 120):
                    if (D3 > 0 and D4 == 0) or (D3 == 0 and D4 > 0):
                        pass
                    else:
                        self.__sensorextendbuffer.add(ins, [0, 1, 2, 3, 5])
            elif cmd == 205:
                self.__timebuffer.add(ins, [0, 1])
            # elif cmd == 164:
            #     self.__triggerbuffer.just_trigger_event_delay(ins,0.1)
        elif D1 == 237:
            #listen to scene actived
            self.__triggerbuffer.just_trigger_event_delay(ins)


    def handle_disconnection(self):
        self.connected = False
        self._authed = False
        self.set_living(False)
        try:
            self.client.close()
        except:
            pass
        print(f"{get_current_time()} Connection lost. Auto-reconnect enabled.")

    def is_alarm(self, inst) -> bool:
        """Determine if it is an alarm."""
        data = inst.get_inst()  # Assume the object has a get_inst method
        d1, d2 = data[0], data[1]

        if (d1 in [0, 1]) and d2 == 0:
            return True
        elif d1 == 243 and (23 <= d2 <= 28):
            return True
        elif d1 == 243 and (30 <= d2 <= 34):
            return True
        elif d1 == 243 and d2 == 91:
            return True

        return False

    def is_live_dev(self, device: int) -> bool:
        """Determine if it is a valid device."""
        return (0 <= device <= 33) or (device == 41) \
            or (61 <= device <= 119) \
            or (191 <= device <= 194) \
            or (201 <= device <= 254)

    def is_valid_scene(self, scene: int) -> bool:
        """Determine if it is a valid scene."""
        if self.show_stop_scene:
            return 1 <= scene <=45 and 129<=scene <= 173
        else:
            return 129 <= scene <= 173

    def is_valid_room(self, room_id: int) -> bool:
        """Determine if it is a valid room."""
        return (0 <= room_id <= 34) or (41 <= room_id <= 155)

    def is_valid_floor(self, floor: int) -> bool:
        """Determine if it is a valid floor."""
        return (0 <= floor <= 99) or (201 <= floor <= 209)

    def is_valid_extend_sensor(self, sensor_id: int) -> bool:
        return (1 <= sensor_id <= 18) or (35 <= sensor_id <= 38)

    def is_available_infrared(self, d6, d7) -> bool:
        return not (d6 == 0 and d7 == 0)

    def set_living(self, living):
        if living != self._is_living:
            # Process network changes here
            self.emit("on_connect_change", living)

        self._is_living = living

    def is_living(self):
        return self._is_living

    def clear_all_buffers(self):
        self.__devbuffer.clear()
        self.__scenebuffer.clear()
        self.__sensorbuffer.clear()
        self.__sensorextendbuffer.clear()
        self.__securitybuffer.clear()
        self.__alarmbuffer.clear()
        self.__timebuffer.clear()
        self.__fmbuffer.clear()
        self.__volbuffer.clear()
        self.__versionbuffer.clear()
        self.__gwbuffer.clear()
        self.__pwdbuffer.clear()
        self.__clockbuffer.clear()
        self.__rgbbuffer.clear()
        self.__cachebuffer.clear()
        self.__f199buffer.clear()
        self.__curtainbuffer.clear()
        self.__triggerbuffer.clear()

    def stop(self):
        """Stop the client"""
        self.running = False
        self.connected = False
        # clear all listeners
        self.remove_all_listeners()
        try:
            self.client.close()
            print(f"{()} Connection closed")
        except Exception as e:
            print(f"{get_current_time()} Error closing connection: {str(e)}")

    def _get_hex(self, num: int) -> str:
        hex_str = format(num, '02X')
        return hex_str

    def _get_hexes(self, datas) -> str:
        return ' '.join(self._get_hex(data) for data in datas)

    def _get_decs(self, datas) -> str:
        return ' '.join(str(data) for data in datas)
