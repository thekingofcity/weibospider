from celery.exceptions import SoftTimeLimitExceeded

from .workers import app
from db.dao import (
    UserOper, SeedidsOper)
from page_get.user import (get_fans_or_followers_ids, get_profile, get_user_profile,
                      get_newcard_by_name)
from logger import crawler


@app.task(ignore_result=True)
def crawl_follower_fans(uid, verify_type):
    try:
        rs = get_fans_or_followers_ids(uid, 1, verify_type)
    except SoftTimeLimitExceeded:
        crawler.error("Exception SoftTimeLimitExceeded    uid={uid}".format(uid=uid))
        app.send_task('tasks.user.crawl_follower_fans', args=(uid, verify_type), queue='fans_followers',
                    routing_key='for_fans_followers')
        return
    if rs:
        for uid in rs:
            app.send_task('tasks.user.crawl_person_infos', args=(uid,), queue='user_crawler',
                          routing_key='for_user_info')
    # seed = SeedidsOper.get_seed_by_id(uid)
    # if seed.other_crawled == 0:
    # rs = get_fans_or_followers_ids(uid, 1)
    # rs.extend(get_fans_or_followers_ids(uid, 2))
    # datas = set(rs)
    # # If data already exits, just skip it
    # if datas:
    #     SeedidsOper.insert_seeds(datas)
    # SeedidsOper.set_seed_other_crawled(uid)


@app.task(ignore_result=True, acks_late=True, soft_time_limit=30)
def crawl_person_infos(uid):
    """
    Crawl user info and their fans and followers
    For the limit of weibo's backend, we can only crawl 5 pages of the fans and followers.
    We also have no permissions to view enterprise's followers and fans info
    :param uid: current user id
    :return: None
    """
    if not uid:
        return

    try:
        user, is_crawled = get_profile(uid)
        # If it's enterprise user, just skip it
        if user and user.verify_type == 2:
            # SeedidsOper.set_seed_other_crawled(uid)
            return

    # Crawl fans and followers
    # if not is_crawled:
    #     app.send_task('tasks.user.crawl_follower_fans', args=(uid,), queue='fans_followers',
    #                   routing_key='for_fans_followers')

    # By adding '--soft-time-limit secs' when you start celery, this will resend task to broker
    # e.g. celery -A tasks.workers -Q user_crawler worker -l info -c 1 --soft-time-limit 10
    except SoftTimeLimitExceeded:
        crawler.error("Exception SoftTimeLimitExceeded    uid={uid}".format(uid=uid))
        app.send_task('tasks.user.crawl_person_infos', args=(uid, ), queue='user_crawler',
                      routing_key='for_user_info')


def crawl_person_infos_not_in_seed_ids(uid):
    """
    Crawl user info not in seed_ids
    """
    if not uid:
        return

    app.send_task('tasks.user.crawl_person_infos', args=(uid, ), queue='user_crawler',
                    routing_key='for_user_info')


@app.task(ignore_result=True)
def crawl_person_infos_by_name(name):
    """
    Crawl user info not in seed_ids
    """
    if not name:
        return False

    user, is_crawled = get_newcard_by_name(name)
    if user is None:
        return False
    else:
        return True


def execute_user_task(uid):
    if not uid:
        return
    app.send_task('tasks.user.crawl_person_infos', args=(uid,), queue='user_crawler',
                  routing_key='for_user_info')


def execute_followers_fans_task(uid, verify_type):
    app.send_task('tasks.user.crawl_follower_fans', args=(uid, verify_type), queue='fans_followers',
                  routing_key='for_fans_followers')


def execute_crawl_person_infos_by_name(name):
    if not name:
        return False
    app.send_task('tasks.user.crawl_person_infos_by_name', args=(name,), queue='user_name_crawler',
                  routing_key='for_user_info')

