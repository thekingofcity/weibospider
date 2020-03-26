import time

from .workers import app
from page_parse import repost
from db.redis_db import IdNames
from db.dao import RepostOper
from page_get import (get_page, get_profile)
from config import get_max_repost_page


BASE_URL = ('https://weibo.com/aj/v6/'
            'mblog/info/big?ajwvr=6&id={}&page={}&__rnd={}')


def determine(repost_datum):
    if RepostOper.get_repost_by_rid(repost_datum.weibo_id):
        return False
    else:
        return True


@app.task(ignore_result=True)
def crawl_repost_by_page(mid, page_num):
    cur_time = int(time.time()*1000)
    cur_url = BASE_URL.format(mid, page_num, cur_time)
    html = get_page(cur_url, auth_level=2, is_ajax=True)
    repost_data = repost.get_repost_list(html, mid)

    repost_data = [
        repost_datum for repost_datum in repost_data
        if determine(repost_datum)
    ]
    RepostOper.add_all(repost_data)
    # if page_num == 1:
    #     WbDataOper.set_weibo_repost_crawled(mid)

    for repost_datum in repost_data:
        app.send_task(
            'tasks.user.crawl_person_infos',
            args=(repost_datum.user_id, ),
            queue='user_crawler',
            routing_key='for_user_info')

    return html, repost_data


@app.task(ignore_result=True)
def crawl_repost_page(mid, uid):
    limit = get_max_repost_page() + 1
    first_repost_data = crawl_repost_by_page(mid, 1)
    total_page = repost.get_total_page(first_repost_data[0])
    repost_datas = first_repost_data[1]

    if not repost_datas:
        return

    root_user, _ = get_profile(uid)

    if total_page < limit:
        limit = total_page + 1

    for page_num in range(2, limit):
        app.send_task('tasks.repost.crawl_repost_by_page',
                      args=(mid, page_num),
                      queue='repost_page_crawler',
                      routing_key='repost_page_info')
        # cur_repost_datas = crawl_repost_by_page(mid, page_num)[1]
        # if cur_repost_datas:
        #     repost_datas.extend(cur_repost_datas)

    for index, repost_obj in enumerate(repost_datas):
        user_id = IdNames.fetch_uid_by_name(repost_obj.parent_user_name)
        if not user_id:
            # when it comes to errors, set the args to default(root)
            repost_obj.parent_user_id = root_user.uid
            repost_obj.parent_user_name = root_user.name
        else:
            repost_obj.parent_user_id = user_id
        repost_datas[index] = repost_obj

    RepostOper.add_all(repost_datas)


def execute_repost_task(weibo_id: str, uid: str):
    if weibo_id and uid:
        app.send_task('tasks.repost.crawl_repost_page',
                      args=(weibo_id, uid),
                      queue='repost_crawler',
                      routing_key='repost_info')
