from typing import Dict, Tuple
import socket

import requests

from config import get_proxy_url

max_retreis = 50


def getIP(param: None) -> Dict:
    return {
        'http': '',
        'https': '',
    }


def getIPWithoutLogin(param: None) -> Tuple[Dict, bool]:
    apiUrl = get_proxy_url()
    if not apiUrl:
        return {
            'http': '',
            'https': '',
        }, True
    ip = "too many requests"
    i = 0
    while ("too many requests" in ip) and (i < max_retreis):
        res = requests.get(apiUrl).content.decode()
        ips = res.split('\n')
        ip = ips[0]
        i = i + 1

    if "充值续费" in ip:
        return {
            'http': '',
            'https': '',
        }, False
    ret = {
        'http': 'http://' + ip,
        'https': 'https://' + ip,
    }
    return ret, True if i < max_retreis else False


def get_host_ip() -> str:
    """[find the current ip of this machine]
    
    Returns:
        [str] -- [ip]
    """

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


def get_ip_address(ifname: str) -> str:
    """[find the current ip of this machine]
    https://www.cnblogs.com/my_life/articles/9187714.html
    
    Arguments:
        ifname {str} -- [something like 'eth0' or 'ens3']
    
    Returns:
        str -- [ip]
    """
    import fcntl
    import struct
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(
        fcntl.ioctl(s.fileno(), 0x8915,
                    struct.pack('256s', bytes(ifname[:15], 'utf-8')))[20:24])
