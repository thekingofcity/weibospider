from typing import List, Tuple, Optional
import socket

from requests_toolbelt.adapters.source import SourceAddressAdapter

from config import get_adapter_ip


class Adapter():
    adapters: Optional[List[Tuple[str, SourceAddressAdapter]]] = None

    def __init__(self):
        APAPTER_IPS_RAW: str = get_adapter_ip()
        if APAPTER_IPS_RAW:
            APAPTER_IPS: List[str] = APAPTER_IPS_RAW.split(',')
            try:
                # make sure the ip is valid
                for ip in APAPTER_IPS:
                    socket.inet_aton(ip.strip())
            except socket.error:
                return

            self.adapters: List[Tuple[str, SourceAddressAdapter]] = [
                (ip.strip(), SourceAddressAdapter(ip.strip()))
                for ip in APAPTER_IPS
            ]

    def get_adapter(self, worker_index: int) -> Optional[SourceAddressAdapter]:
        if self.adapters and worker_index:
            return self.adapters[worker_index % len(self.adapters)][1]
        return None

    def get_host_ip(self, worker_index: Optional[int] = None) -> str:
        if self.adapters and worker_index:
            return self.adapters[worker_index % len(self.adapters)][0]
        else:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
            finally:
                s.close()
            return ip


ADAPTER = Adapter()
