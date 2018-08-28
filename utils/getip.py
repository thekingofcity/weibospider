from typing import Dict, Tuple

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

    ret = {
        'http': 'http://' + ip,
        'https': 'https://' + ip,
    }
    return ret, True if i < max_retreis else False
