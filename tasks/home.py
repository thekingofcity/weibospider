import time

from celery.exceptions import SoftTimeLimitExceeded

from logger import crawler
from .workers import app
from page_parse.user import public
from page_get import get_page
from config import (get_max_home_page, get_time_after)
from db.dao import (
    WbDataOper, SeedidsOper)
from page_parse.home import (
    get_data, get_ajax_data, get_total_page)


# only crawls origin weibo
# HOME_URL = 'http://weibo.com/u/{}?is_ori=1&is_tag=0&profile_ftype=1&page={}'
# AJAX_URL = 'http://weibo.com/p/aj/v6/mblog/mbloglist?ajwvr=6&domain={}&pagebar={}&is_ori=1&id={}{}&page={}' \
#            '&pre_page={}&__rnd={}'

# crawls all weibo
HOME_URL = 'http://weibo.com/u/{}?is_all=1&page={}'
AJAX_URL = 'http://weibo.com/p/aj/v6/mblog/mbloglist?ajwvr=6&domain={}&wvr=6&is_all=1&pagebar={}&id={}{}' \
           '&feed_type=0&page={}&pre_page={}&__rnd={}'


def determine(weibo_datum, timeafter):
    weibo_time = time.mktime(
        time.strptime(weibo_datum.create_time, '%Y-%m-%d %H:%M:%S'))
    if weibo_time < timeafter:
        return False
    if WbDataOper.get_wb_by_mid(weibo_datum.weibo_id):
        return False
    return True


@app.task(ignore_result=True)
def crawl_ajax_page(url, auth_level):
    """
    :param url: user home ajax url
    :param auth_level: 1 stands for no login but need fake cookies, 2 stands for login
    :return: resp.text
    """
    ajax_html = get_page(url, auth_level, is_ajax=True)
    ajax_wbdata = get_ajax_data(ajax_html)
    if not ajax_wbdata:
        return ''

    timeafter = time.mktime(
        time.strptime(get_time_after(), '%Y-%m-%d %H:%M:%S'))
    ajax_wbdata = [
        ajax_wbdatum for ajax_wbdatum in ajax_wbdata
        if determine(ajax_wbdatum, timeafter)
    ]

    WbDataOper.add_all(ajax_wbdata)
    return ajax_html


@app.task(ignore_result=True)
def crawl_weibo_datas(uid):
    limit = get_max_home_page()
    cur_page = 1
    while cur_page <= limit:
        url = HOME_URL.format(uid, cur_page)
        if cur_page == 1:
            html = get_page(url, auth_level=1)
        else:
            html = get_page(url, auth_level=2)
        weibo_data = get_data(html)

        if not weibo_data:
            crawler.warning("user {} has no weibo".format(uid))
            return

        # Check whether weibo created after time in spider.yaml
        original_length_weibo_data = len(weibo_data)
        timeafter = time.mktime(
            time.strptime(get_time_after(), '%Y-%m-%d %H:%M:%S'))
        weibo_data = [
            weibo_datum for weibo_datum in weibo_data
            if determine(weibo_datum, timeafter)
        ]

        for weibo_datum in weibo_data:
            try:
                WbDataOper.add_one(weibo_datum)
            except Exception as e:
                print(weibo_datum.weibo_id)
                print(weibo_datum.weibo_cont)
                print("weibo_img",weibo_datum.weibo_img)
                print("weibo_video",weibo_datum.weibo_video)
                print("weibo_img_path",weibo_datum.weibo_img_path)
                print(weibo_datum.repost_num)
                print(weibo_datum.comment_num)
                print(weibo_datum.praise_num)
                print(weibo_datum.uid)
                print(weibo_datum.is_origin)
                print(weibo_datum.origin_weibo_id)
                print(weibo_datum.device)
                print(weibo_datum.create_time)
                print(e)
        # WbDataOper.add_all(weibo_data)

        # the forwarded weibo might interfere with the origin weibo
        # # If the weibo isn't created after the given time, jump out the loop
        # if len(weibo_data) != original_length_weibo_data:
        #     print(len(weibo_data), original_length_weibo_data)
        #     break

        if cur_page == 1:
            auth_level = 2

            domain = public.get_userdomain(html)
            cur_time = int(time.time()*1000)
            ajax_url_0 = AJAX_URL.format(domain, 0, domain, uid, cur_page, cur_page, cur_time)
            ajax_url_1 = AJAX_URL.format(domain, 1, domain, uid, cur_page, cur_page, cur_time + 100)

            # local call to simulate human interaction
            crawl_ajax_page(ajax_url_0, auth_level)

            # here we use local call to get total page number
            total_page = get_total_page(crawl_ajax_page(ajax_url_1, auth_level))

            if total_page < limit:
                limit = total_page

        else:
            auth_level = 2

            domain = public.get_userdomain(html)
            cur_time = int(time.time()*1000)
            ajax_url_0 = AJAX_URL.format(domain, 0, domain, uid, cur_page, cur_page - 1, cur_time)
            ajax_url_1 = AJAX_URL.format(domain, 1, domain, uid, cur_page, cur_page - 1, cur_time+100)

            # Still the same as before
            app.send_task('tasks.home.crawl_ajax_page', args=(ajax_url_0, auth_level), queue='ajax_home_crawler',
                          routing_key='ajax_home_info')
            app.send_task('tasks.home.crawl_ajax_page', args=(ajax_url_1, auth_level), queue='ajax_home_crawler',
                          routing_key='ajax_home_info')

        cur_page += 1


def execute_home_task(uid: str = None):
    if not uid:
        # you can have many strategies to crawl user's home page, here we choose table seed_ids's uid
        # whose home_crawl is 0
        id_objs = SeedidsOper.get_home_ids()
        for id_obj in id_objs:
            app.send_task(
                'tasks.home.crawl_weibo_datas',
                args=(id_obj.uid, ),
                queue='home_crawler',
                routing_key='home_info')
    else:
        app.send_task(
            'tasks.home.crawl_weibo_datas',
            args=(uid, ),
            queue='home_crawler',
            routing_key='home_info')
