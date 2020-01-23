import json
import os
import time
import datetime

import pytest

from config import get_cookie_expire_time, get_ip_expire_time
from db.redis_db import cookies_con, Cookies
from logger import crawler
from page_get import get_page
from tasks.login import push_account_to_login_pool, login_task
from utils.getproxy import get_host_ip

login_name = os.getenv('WEIBO_ACCOUNT')
ip = get_host_ip()  # type: str


class TestCookiesPolicy_Normal:
    @pytest.mark.parametrize(
        'uid, page', [('1188203673', '1'),]
        )
    def test_crawl_page_without_login(self, session, uid, page):
        HOME_URL = 'https://weibo.com/u/{}?is_all=1&page={}'
        url = HOME_URL.format(uid, page)
        html = get_page(url, auth_level=1)
        assert html is not None
        assert cookies_con.exists('account_pool') is not None

    def test_crawl_page_with_login(self, session, get_page_2_setup):
        pass


class TestCookiesPolicy_Abnormal_IpExpire:
    def test_ip_expire(self, session, get_page_2_setup):
        ip_expire_time = get_ip_expire_time()
        obsolete_timestamp = datetime.datetime.utcnow(
        ) - 3 * datetime.timedelta(
            minutes=ip_expire_time)  # type: datetime.datetime
        cookies_con.hset('heartbeat', ip, obsolete_timestamp.timestamp())
        ###
        Cookies.check_heartbeat()
        ###
        assert cookies_con.exists(ip) is False
        assert cookies_con.hlen('account_pool') is 1


class TestCookiesPolicy_Abnormal_BannedInGetPage:
    def test_banned_in_get_page(self, session, get_page_2_setup):
        Cookies.abnormal_cookies_in_ip(login_name)
        assert cookies_con.exists(ip) is False
        assert cookies_con.hlen('login_pool') is 1
