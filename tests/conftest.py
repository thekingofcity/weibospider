import os
import json
import time

import pytest

from db.basic import db_session
from db.redis_db import cookies_con
from config import create_all
from tasks.login import login_task
from login import get_cookies
from page_get import get_page
from utils.getip import get_host_ip


@pytest.fixture(scope='class', autouse=False)
def session():
    login_name = os.getenv('WEIBO_ACCOUNT')
    login_pass = os.getenv('WEIBO_PASS')
    login_task(login_name, json.dumps({'password': login_pass, 'retry': 0}))
    assert cookies_con.hget('account_pool', login_name) is not None
    yield
    cookies_con.flushdb()


@pytest.fixture(scope='function', autouse=False)
def get_page_2_setup():
    ip = get_host_ip()  # type: str
    BASE_URL = 'https://weibo.com/aj/v6/like/likelist?ajwvr=6&mid={}&issingle=1&type=0&_t=0&__rnd={}'
    cur_time = int(time.time() * 1000)
    cur_url = BASE_URL.format('4336987379189211', cur_time)
    html = get_page(cur_url, auth_level=2, is_ajax=True)
    assert html is not None
    assert cookies_con.exists('account_pool') is False
    assert cookies_con.hlen(ip) is 1


@pytest.fixture(scope='session', autouse=True)
def fake_cookies():
    return get_cookies()


@pytest.fixture(scope='session', autouse=True)
def create_tables():
    db_session.execute('drop database if exists weibo;')
    db_session.execute('create database weibo;use weibo;')
    rs = db_session.execute('show tables;')
    assert rs.rowcount == 0
    create_all.create_all_table()
    rs = db_session.execute('show tables;')
    assert rs.rowcount > 0