import requests


from config import get_proxy_url


def getIP(param):
    return {
        'http': '',
        'https': '',
    }


def getIPWithoutLogin(param):
    apiUrl = get_proxy_url()
    res = requests.get(apiUrl).content.decode()
    ips = res.split('\n')
    ip = ips[0]
    ret = {
        'http': 'http://' + ip,
        'https': 'https://' + ip,
    }
    return ret
