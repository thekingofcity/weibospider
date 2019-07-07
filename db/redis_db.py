import os
import time
import json
import socket
import datetime
from typing import Tuple

import redis
from redis.sentinel import Sentinel

from logger import crawler
from config import (get_redis_args, get_share_host_count, get_running_mode,
                    get_cookie_expire_time, get_ip_expire_time)
from utils.getip import get_host_ip


MODE = get_running_mode()
SHARE_HOST_COUNT = get_share_host_count()
REDIS_ARGS = get_redis_args()

password = REDIS_ARGS.get('password', '')
cookies_db = REDIS_ARGS.get('cookies', 1)
urls_db = REDIS_ARGS.get('urls', 2)
broker_db = REDIS_ARGS.get('broker', 5)
backend_db = REDIS_ARGS.get('backend', 6)
id_name_db = REDIS_ARGS.get('id_name', 8)
cookie_expire_time = get_cookie_expire_time()
ip_expire_time = get_ip_expire_time()
data_expire_time = REDIS_ARGS.get('expire_time') * 60 * 60

sentinel_args = REDIS_ARGS.get('sentinel', '')
if sentinel_args:
    # default socket timeout is 2 secs
    master_name = REDIS_ARGS.get('master')
    socket_timeout = int(REDIS_ARGS.get('socket_timeout', 2))
    sentinel = Sentinel([(args['host'], args['port']) for args in sentinel_args], password=password,
                        socket_timeout=socket_timeout)
    cookies_con = sentinel.master_for(master_name, socket_timeout=socket_timeout, db=cookies_db)
    broker_con = sentinel.master_for(master_name, socket_timeout=socket_timeout, db=broker_db)
    urls_con = sentinel.master_for(master_name, socket_timeout=socket_timeout, db=urls_db)
    id_name_con = sentinel.master_for(master_name, socket_timeout=socket_timeout, db=id_name_db)
else:
    host = REDIS_ARGS.get('host', '127.0.0.1')
    port = REDIS_ARGS.get('port', 6379)
    cookies_con = redis.Redis(host=host, port=port, password=password, db=cookies_db)
    broker_con = redis.Redis(host=host, port=port, password=password, db=broker_db)
    urls_con = redis.Redis(host=host, port=port, password=password, db=urls_db)
    id_name_con = redis.Redis(host=host, port=port, password=password, db=id_name_db)


class Cookies(object):
    @classmethod
    def store_cookies(cls, name, password, cookies, proxy):
        pickled_cookies = json.dumps({
            'cookies': cookies,
            'password': password,
            'loginTime': datetime.datetime.utcnow().timestamp(),
            'proxy': proxy
        })
        if not cookies_con.hexists('account_pool', name):
            cookies_con.hset('account_pool', name, pickled_cookies)

    @classmethod
    def fetch_cookies(cls) -> Tuple[str, str]:
        """[called by node when it want to fetch cookies]
            When node start a request, it will call this to get cookies
            Definition:
                account = (name, {'cookies': cookies,'password': password,
                                    'loginTime': loginTime, 'proxy': proxy})
                cookies = account[1]

            pseudo-code:
                while not account:
                    if ip in redis db's key:
                        for account in ip:
                            if not timeout:
                                break
                            else:
                                account = None
                    else:
                        lock
                            if ip in redis db's key: continue
                            for account in account_pool:
                                if not timeout:
                                    break
                                else:
                                    account = None
                            if not account:
                                unlock
                                return None, None
                        unlock
                return account[0], account[1]['cookies']
        
        Returns:
            Tuple[str, bytes] -- [account name, account cookies]
        """

        ip = get_host_ip()
        pid = os.getpid()
        account = None
        while not account:
            current_ip_cookies_pool = cookies_con.exists(ip)
            if not current_ip_cookies_pool:
                cls.__lock(ip+"mutex", pid)
                # check if another process get an account before lock
                current_ip_cookies_pool = cookies_con.exists(ip)
                if current_ip_cookies_pool:
                    cls.__unlock(ip+"mutex", pid)
                    continue
                # we have to acquire new cookies form account_pool
                # account = (name, {'cookies': cookies,'password': password, ...})
                for account in cookies_con.hscan_iter('account_pool'):
                    if cls.check_cookies_timeout(account[1].decode('utf-8')):
                        cls.expire_cookies_in_acount_pool(account[0].decode('utf-8'))
                        account = None
                    else:
                        break
                if not account:
                    # No more cookies in any pool
                    cls.__unlock(ip+"mutex", pid)
                    return None, None
                cookies_con.hdel('account_pool', account[0])
                cookies_con.hset(ip, account[0], account[1])
                cls.__unlock(ip+"mutex", pid)
            else:
                # random select one in current_ip_cookies_pool
                # Now only implemented first one
                for account in cookies_con.hscan_iter(ip):
                    if cls.check_cookies_timeout(account[1].decode('utf-8')):
                        cls.abnormal_cookies_in_ip(account[0].decode('utf-8'))
                        account = None
                    else:
                        break
        cls.refresh_heartbeat(ip)
        name = account[0].decode('utf-8')
        cookies = json.loads(account[1].decode('utf-8'))
        return name, cookies['cookies']

    @classmethod
    def remove_account_from_login_pool(cls, name: str):
        """[remove account from login_pool]
            Used in successful login task
        
        Arguments:
            name {str} -- [name]
        """

        cookies_con.hdel('login_pool', name)

    @classmethod
    def push_account_to_login_pool(cls, name: str, password: str, retry: int):
        """[push account to login_pool]
        
        Arguments:
            name {str} -- [name]
            password {str} -- [password]
            retry {int} -- [retry times]
        """

        if cookies_con.hexists('login_pool', name):
            # multiple thread requesting weibo with account A may get banned at the same time
            # but they will all call abnormal_cookies_in_ip
            return
        pickled_cookies = json.dumps({'password': password, 'retry': retry})
        cookies_con.hset('login_pool', name, pickled_cookies)


    @classmethod
    def get_account_from_login_pool(cls) -> Tuple[str, bytes]:
        """[generator of account in login_pool]
        
        Returns:
            Tuple[str, bytes] -- [account name, account password and retry times in json]
        """

        for account in cookies_con.hscan_iter('login_pool'):
            yield account[0].decode('utf-8'), account[1]

    @classmethod
    def refresh_heartbeat(cls, ip: str):
        cookies_con.hset('heartbeat', ip,
                         datetime.datetime.utcnow().timestamp())

    @classmethod
    def remove_heartbeat(cls, ip: str):
        cookies_con.hdel('heartbeat', ip)

    @classmethod
    def check_heartbeat(cls):
        """[check_heartbeat]
            Should be called locally in one thread

            pseudo-code:
            for ip in heartbeat:
                if timeout:
                    for account in ip:
                        if timeout:
                            move to login_pool
                        else:
                            move to account_pool
        """

        for ip in cookies_con.hscan_iter('heartbeat'):
            last_timestamp = ip[1].decode('utf-8')  # type: str
            ip = ip[0].decode('utf-8')
            last_timestamp = datetime.datetime.fromtimestamp(float(last_timestamp))  # type: datetime
            if datetime.datetime.utcnow() - last_timestamp > datetime.timedelta(minutes=ip_expire_time):
                print('ip/pod:{ip} has missed its heartbeat'.format(ip=ip))
                # crawler.warning('ip/pod:{ip} has missed its heartbeat'.format(ip=ip))
                for account in cookies_con.hscan_iter(ip):
                    if cls.check_cookies_timeout(account[1].decode('utf-8')):
                        # If the cookies expired, we should move it to login_pool waiting for login
                        print('cookies expired {uid}'.format(uid=account[0]))
                        cls.__delete_cookies(ip, account[0].decode('utf-8'))
                    else:
                        # else move it to account_pool for another request
                        print('cookies valid {uid}'.format(uid=account[0]))
                        cookies_con.hset('account_pool', account[0], account[1])
                    cookies_con.hdel(ip, account[0])
                assert cookies_con.exists(ip)==0
                cls.remove_heartbeat(ip)

    @classmethod
    def check_cookies_timeout(cls, cookies: str) -> bool:
        """[check cookies timeout]

        Arguments:
            cookies {str} -- [format of cookies
                                '{'cookies': cookies,'password': password,
                                'loginTime': loginTime, 'proxy': proxy}'
                            ]

        Returns:
            bool -- [True for timeout, vice versa]
        """

        cookies_dict = json.loads(cookies)
        login_time_datetime = datetime.datetime.fromtimestamp(
            cookies_dict['loginTime'])
        if datetime.datetime.utcnow(
        ) - login_time_datetime > datetime.timedelta(hours=cookie_expire_time):
            return True
        else:
            return False

    @classmethod
    def expire_cookies_in_acount_pool(cls, name: str):
        crawler.warning('cookies expired {uid}'.format(uid=name))
        cls.__delete_cookies('account_pool', name)

    @classmethod
    def abnormal_cookies_in_ip(cls, name: str):
        """[Be called if 1. cookies banned 2. cookies timeout]
        
        Arguments:
            name {str} -- [account name]
        """

        ip = get_host_ip()
        crawler.warning('cookies banned {uid}'.format(uid=name))
        cls.__delete_cookies(ip, name)

    @classmethod
    def __delete_cookies(cls, key: str, name: str):
        """[delete cookies]
        move cookies from ip or account_pool to login_pool
        
        Arguments:
            key {[str]} -- [ip or account_pool]
            name {[str]} -- [account name]
        """

        cls.__lock(key+"mutex",os.getpid())
        account = cookies_con.hget(key, name)
        if account is None:
            cls.__unlock(key+"mutex",os.getpid())
            return
        cookies_con.hdel(key, name)
        cookies = json.loads(account.decode('utf-8'))
        cls.push_account_to_login_pool(name, cookies['password'], 0)
        cls.__unlock(key+"mutex",os.getpid())

    @classmethod
    def __lock(cls, lockKey:str, requestId:str):
        while not cookies_con.set(lockKey, requestId, ex=1, nx=True):
            time.sleep(1)
        return

    @classmethod
    def __unlock(cls, lockKey:str, requestId:str)->bool:
        script="if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
        script_obj=cookies_con.register_script(script)
        return script_obj(keys=[lockKey],args=[requestId])


class Urls(object):
    @classmethod
    def store_crawl_url(cls, url, result):
        urls_con.set(url, result)
        urls_con.expire(url, data_expire_time)


class IdNames(object):
    @classmethod
    def store_id_name(cls, user_name, user_id):
        id_name_con.set(user_name, user_id)

    @classmethod
    def delele_id_name(cls, user_name):
        id_name_con.delete(user_name)

    @classmethod
    def fetch_uid_by_name(cls, user_name):
        user_id = id_name_con.get(user_name)
        cls.delele_id_name(user_name)
        if user_id:
            return user_id.decode('utf-8')
        return ''
