import socket
import time
from typing import Dict, List, Optional, Callable
import struct

from .klw_singleton import Singleton


class KLWBroadcast(metaclass=Singleton):
    def __init__(self):
        self.devices: Dict[str, dict] = {}
        self.listener: Optional[Callable] = None
        self.udp_client: Optional[socket.socket] = None
        self.multicast_ip = "230.90.76.1"

    def init(self, listener: Callable = None) -> None:
        self.listener = listener
        # Create UDP socket
        self.udp_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Set broadcast option
        self.udp_client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Set multicast TTL
        self.udp_client.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 128)
        # Bind to any port
        self.udp_client.bind(('', 0))
        # Join multicast group
        mreq = struct.pack("4sl", socket.inet_aton(self.multicast_ip), socket.INADDR_ANY)
        self.udp_client.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        self.udp_client.setblocking(False)

    def get_devices(self) -> List[dict]:
        return list(self.devices.values())

    def _get_hex(self, num: int) -> str:
        return '{:02X}'.format(num)

    def get_udp_info(self, buf: bytes, rinfo: tuple) -> dict:

        ip = rinfo[0]

        # Get device name length
        begin = 41
        lenx = 0
        for i in range(41, 52):
            if buf[i] == 0:
                break
            lenx += 1

        # Get MAC address
        sid = ''
        macbyte = []
        for i in range(34, 40):
            sid += self._get_hex(buf[i])
            macbyte.append(buf[i])

        # Get local IP
        localip = f"{buf[3]}.{buf[4]}.{buf[5]}.{buf[6]}"

        # Get device name
        namebyte = bytearray(lenx)
        for i in range(begin, begin + lenx):
            namebyte[i - begin] = buf[i]

        # Catch the exception here
        dev_name = "Unknown"
        try:
            dev_name = self.uint8array_to_string(namebyte)
        except Exception as e:
            print(f"Error decoding device name: {e}")

        # Format MAC address
        mac = '-'.join(self._get_hex(b) for b in macbyte)

        # Get port information
        local_port = (buf[19] << 8) | buf[20]
        dest_port = (buf[21] << 8) | buf[22]

        # Get group IP
        group_ip = f"{buf[108]}.{buf[109]}.{buf[110]}.{buf[111]}"

        # Get version information
        version = f"V1.{(buf[106] & 0xff) + 383}"
        work_model = buf[23]

        return {
            'ip': localip,
            'devName': dev_name,
            'localport': local_port,
            'destport': dest_port,
            'groupip': group_ip,
            'version': version,
            'mac': mac,
            'sid': sid,
            'workmodel': work_model
        }

    def uint8array_to_string(self, uint8array) -> str:
        return bytes(uint8array).decode('gbk')

    def _search_params(self) -> bytes:
        b = bytearray(170)
        b[0] = 0x5a
        b[1] = 0x4c
        b[2] = 0x00
        return bytes(b)

    def search(self) -> List[dict]:
        params = self._search_params()
        self.udp_client.sendto(params, ('255.255.255.255', 1092))

        # Wait to receive response
        start_time = time.time()
        while time.time() - start_time < 4:  # 5 second timeout
            try:
                data, addr = self.udp_client.recvfrom(1024)
                info = self.get_udp_info(data, addr)
                self.devices[info['sid']] = info
                if self.listener:
                    self.listener(info)
            except BlockingIOError:
                # print("Blocking Socket timeout.")
                pass
                # time.sleep(0.1)  # Short sleep to avoid excessive CPU usage
            except Exception as e:
                print(f"Error receiving data: {e}")

        return self.get_devices()
