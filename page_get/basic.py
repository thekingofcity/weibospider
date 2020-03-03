import os
import time
import signal
import json

import requests
from billiard import current_process

from config import headers
from logger import crawler
from login import get_cookies
from db.dao import LoginInfoOper
from utils import (send_email, getproxy)
from utils.adapter import ADAPTER
from db.redis_db import Cookies
from page_parse import (is_403, is_404, is_complete)
from decorators import (timeout_decorator, timeout)
from config import (get_timeout, get_crawl_interal, get_excp_interal,
                    get_max_retries, get_login_interval)

TIME_OUT = int(get_timeout())
INTERAL = get_crawl_interal()
MAX_RETRIES = get_max_retries()
EXCP_INTERAL = get_excp_interal()
login_interval = int(get_login_interval())
COOKIES = get_cookies()

# Instead of disable warning, why not use it as docs suggested
# https://stackoverflow.com/questions/42982143/python-requests-how-to-use-system-ca-certificates-debian-ubuntu
os.environ['REQUESTS_CA_BUNDLE'] = os.path.join(os.sep, '/etc/ssl/certs',
                                                'ca-certificates.crt')


def is_banned(url):
    if any(keyword in url for keyword in
           ['unfreeze', 'accessdeny', 'userblock', 'verifybmobile']):
        return True
    return False


@timeout(200)
@timeout_decorator
def get_page(url, auth_level=2, is_ajax=False, need_proxy=False):
    """
    :param url: url to crawl
    :param auth_level: 0 stands for need nothing,1 stands for no login but need cookies,2 stands for need login.
    :param is_ajax: whether the request is ajax
    :param need_proxy: whether the request need a http/https proxy
    :return: response text, when a exception is raised, return ''
    """
    host_ip = ADAPTER.get_host_ip(current_process().index)
    crawler.debug(f'the crawling url is {url} via {host_ip}')

    count = 0
    while count < MAX_RETRIES:
        if auth_level == 2:
            name_cookies = Cookies.fetch_cookies()

            if name_cookies[0] is None:
                if count < MAX_RETRIES:
                    # wait for 3x login_interval(minutes) for new account in account_pool
                    time.sleep(login_interval * 60 * 3)
                    count += 1
                else:
                    crawler.warning(
                        'No cookie in cookies pool. Maybe all accounts are banned, or all cookies are expired'
                    )
                    send_email()
                    os.kill(os.getppid(), signal.SIGTERM)
        else:
            proxy = getproxy.getIPWithoutLogin('')
            if proxy[1]:
                proxy = proxy[0]
                if proxy['http']:
                    crawler.info('the proxy is ' + json.dumps(proxy['http']))
            else:
                crawler.warning('No more proxy available')
                os.kill(os.getppid(), signal.SIGTERM)

        try:
            with requests.Session() as s:
                s.headers.update(headers)

                if auth_level == 2:
                    s.cookies.update(name_cookies[1])
                elif auth_level == 1:
                    s.cookies.update(COOKIES)

                adapter = ADAPTER.get_adapter(current_process().index)
                if adapter:
                    # requests via another ip
                    s.mount('http://', adapter)
                    s.mount('https://', adapter)

                resp = s.get(url,
                             timeout=TIME_OUT,
                             verify=False)
        except (requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError, AttributeError) as e:
            crawler.warning(
                'Excepitons are raised when crawling {}.Here are details:{}'.
                format(url, e))
            count += 1
            time.sleep(eval(EXCP_INTERAL))
            continue

        if resp.status_code == 414:
            crawler.warning('This ip has been blocked by weibo system')
            if not need_proxy:
                send_email()
                os.kill(os.getppid(), signal.SIGTERM)
        if resp.text:
            page = resp.text.encode('utf-8', 'ignore').decode('utf-8')
        else:
            count += 1
            continue
        if auth_level == 2:
            # slow down to aviod being banned
            time.sleep(INTERAL)
            if is_banned(resp.url) or is_403(page):
                crawler.warning('Account {} has been banned'.format(
                    name_cookies[0]))
                LoginInfoOper.freeze_account(name_cookies[0], 0)
                Cookies.abnormal_cookies_in_ip(name_cookies[0])
                count += 1
                continue

            if not is_ajax and not is_complete(page):
                count += 1
                continue

        if is_404(page):
            crawler.warning('{} seems to be 404'.format(url))
            return ''
        # Urls.store_crawl_url(url, 1)
        return page

    # Urls.store_crawl_url(url, 0)
    return ''
