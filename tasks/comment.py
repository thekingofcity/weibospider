from celery.exceptions import SoftTimeLimitExceeded

from .workers import app
from page_parse import comment
from config import conf
from page_get import get_page
from db.dao import (
    WbDataOper, CommentOper)


BASE_URL = 'http://weibo.com/aj/v6/comment/big?ajwvr=6&id={}&page={}'


def determine(comment_datum):
    if CommentOper.get_comment_by_id(comment_datum.comment_id):
        return False
    return True


@app.task(ignore_result=True)
def crawl_comment_by_page(mid, page_num):
    cur_url = BASE_URL.format(mid, page_num)
    html = get_page(cur_url, auth_level=1, is_ajax=True)
    comment_data = comment.get_comment_list(html, mid)
    origin_comment_data_len = len(comment_data)
    comment_data = [
        comment_datum for comment_datum in comment_data
        if determine(comment_datum)
    ]
    CommentOper.add_all(comment_data)
    # if page_num == 1:
    #     WbDataOper.set_weibo_comment_crawled(mid)
    if len(comment_data) != origin_comment_data_len:
        need_more_comment_crawler = False
    else:
        need_more_comment_crawler = True
    return html, comment_data, need_more_comment_crawler


@app.task(ignore_result=True)
def crawl_comment_page(mid):
    limit = conf.get_max_comment_page() + 1
    # 这里为了马上拿到返回结果，采用本地调用的方式
    ret = crawl_comment_by_page(mid, 1)
    first_page = ret[0]
    total_page = comment.get_total_page(first_page)

    if total_page < limit:
        limit = total_page + 1

    if ret[2]:
        for page_num in range(2, limit):
            app.send_task('tasks.comment.crawl_comment_by_page', args=(mid, page_num), queue='comment_page_crawler',
                        routing_key='comment_page_info')


def execute_comment_task():
    # 只解析了根评论，而未对根评论下的评论进行抓取，如果有需要的同学，可以适当做修改
    weibo_datas = WbDataOper.get_weibo_comment_not_crawled()
    for weibo_data in weibo_datas:
        app.send_task('tasks.comment.crawl_comment_page', args=(weibo_data.weibo_id,), queue='comment_crawler',
                      routing_key='comment_info')
