import requests


def getIP(param):
    return {
        'http': '',
        'https': '',
    }


def getIPWithoutLogin(param):
    return {
        'http': '',
        'https': '',
    }
    apiUrl = ""
    res = requests.get(apiUrl).content.decode()
    ips = res.split('\n')
    ip = ips[0]
    ret = {
        'http': 'http://' + ip,
        'https': 'https://' + ip,
    }
    return ret
