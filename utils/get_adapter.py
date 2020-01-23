from typing import List, Optional
import socket

from requests_toolbelt.adapters.source import SourceAddressAdapter

from config import get_adapter_ip


class get_adapter():
    adapters: Optional[List[SourceAddressAdapter]] = None

    def __init__(self):
        APAPTER_IPS_RAW: str = get_adapter_ip()
        if APAPTER_IPS_RAW:
            APAPTER_IPS: List[str] = APAPTER_IPS_RAW.split(',')
            try:
                # make sure the ip is valid
                for ip in APAPTER_IPS:
                    socket.inet_aton(ip)
            except socket.error:
                return

            self.adapters: List[SourceAddressAdapter] = [
                SourceAddressAdapter(ip.strip()) for ip in APAPTER_IPS
            ]

    def get_adapter(self, worker_index: int) -> Optional[SourceAddressAdapter]:
        if self.adapters:
            return self.adapters[worker_index % len(self.adapters)]
        return None
