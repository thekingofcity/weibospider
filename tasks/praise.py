import time

from .workers import app
from page_parse import praise
from logger import crawler
from config import conf
from page_get import get_page
from db.dao import (WbDataOper, PraiseOper)


BASE_URL = 'http://weibo.com/aj/v6/like/big?ajwvr=6&mid={}&page={}&__rnd={}'


def determine(praise_datum):
    if PraiseOper.get_Praise_by_realtionship(praise_datum.mid,
                                             praise_datum.user_id):
        return False
    return True


@app.task(ignore_result=True)
def crawl_praise_by_page(mid, page_num):
    cur_time = int(time.time() * 1000)
    cur_url = BASE_URL.format(mid, page_num, cur_time)
    html = get_page(cur_url, auth_level=2, is_ajax=True)
    praise_data = praise.get_praise_list(html, mid)
    origin_praise_data_len = len(praise_data)
    praise_data = [
        praise_datum for praise_datum in praise_data
        if determine(praise_datum)
    ]
    PraiseOper.add_all(praise_data)
    # if page_num == 1:
    #     WbDataOper.set_weibo_comment_crawled(mid)

    for praise_datum in praise_data:
        app.send_task(
            'tasks.user.crawl_person_infos',
            args=(praise_datum.user_id, ),
            queue='user_crawler',
            routing_key='for_user_info')

    if len(praise_data) != origin_praise_data_len:
        need_more_praise_crawler = False
    else:
        need_more_praise_crawler = True
    return html, praise_data, need_more_praise_crawler


@app.task(ignore_result=True)
def crawl_praise_page(mid):
    # 这里为了马上拿到返回结果，采用本地调用的方式
    first_page = crawl_praise_by_page(mid, 1)[0]
    total_page = praise.get_total_page(first_page)

    for page_num in range(2, total_page + 1):
        app.send_task('tasks.praise.crawl_praise_by_page', args=(mid, page_num), queue='praise_page_crawler',
                      routing_key='praise_page_info')


def execute_praise_task():
    weibo_datas = WbDataOper.get_weibo_praise_not_crawled()
    for weibo_data in weibo_datas:
        app.send_task('tasks.praise.crawl_praise_page', args=(weibo_data.weibo_id,), queue='praise_crawler',
                      routing_key='praise_info')
