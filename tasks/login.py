import time
import json

from db.redis_db import Cookies
from exceptions import (LoginWrongPasswordException,
                        LoginAccountForbiddenException)
from logger import crawler
from login import get_session
from db.dao import LoginInfoOper
from .workers import app


@app.task(ignore_result=True)
def login_task(name, data):
    data = json.loads(data)
    password = data['password']
    retry = int(data['retry'])
    if retry <= 3:
        try:
            session, proxy = get_session(name, password)
            Cookies.store_cookies(name, password, session.cookies.get_dict(), proxy['http'])
        except LoginAccountForbiddenException:
            retry += 1
            Cookies.push_account_to_login_pool(name, password, retry)
        except LoginWrongPasswordException:
            retry += 1
            Cookies.push_account_to_login_pool(name, password, retry)
    else:
        Cookies.push_account_to_login_pool(name, password, retry)


def execute_login_task():
    crawler.info('The login task is starting...')
    # data:dict = {'password': password:str, 'retry': retry:str}
    for name, data in Cookies.get_account_from_login_pool():
        # to avoid duplicate login task when login node is down
        Cookies.remove_account_from_login_pool(name)
        app.send_task(
            'tasks.login.login_task',
            args=(name, data.decode('utf-8')),
            queue='login_queue',
            routing_key='for_login')


def check_heartbeat():
    Cookies.check_heartbeat()


def cookies_banned(name):
    """[test method, called in node]
    
    Arguments:
        name {[str]} -- [name]
    """

    Cookies.abnormal_cookies_in_ip(name)


def push_account_to_login_pool(name, password):
    """[test method, called in master]
    
    Arguments:
        name {[str]} -- [name]
        password {[str]} -- [password]
    """

    Cookies.push_account_to_login_pool(name, password, 0)
