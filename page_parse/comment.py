import json
import time
import datetime
import re

from bs4 import BeautifulSoup

from logger import parser
from db.models import WeiboComment
from decorators import parse_decorator


@parse_decorator('')
def get_html_cont(html):
    cont = ''
    data = json.loads(html, encoding='utf-8').get('data', '')
    if data:
        cont = data.get('html', '')

    return cont


def get_total_page(html):
    try:
        page_count = json.loads(html, encoding='utf-8').get('data', '').get('page', '').get('totalpage', 1)
    except Exception:
        try:
            json.loads(html, encoding='utf-8').get('data', '').get('tag', '')
            page_count = 1
        except Exception as e:
            parser.error('Get total page error, the reason is {}'.format(e))
            page_count = 1

    return page_count


@parse_decorator('')
def get_next_url(html):
    """
    获取下一次应该访问的url
    :param html: 
    :return: 
    """
    cont = get_html_cont(html)
    if not cont:
        return ''
    soup = BeautifulSoup(cont, 'html.parser')
    url = ''
    if 'comment_loading' in cont:
        url = soup.find(attrs={'node-type': 'comment_loading'}).get('action-data')

    if 'click_more_comment' in cont:
        url = soup.find(attrs={'action-type': 'click_more_comment'}).get('action-data')
    return url


def get_create_time_from_text_default_error_handler() -> datetime:
    """[default error handler will return datetime of now]
    
    Returns:
        datetime -- [description]
    """

    return datetime.datetime.now()


def get_create_time_from_text(create_time_str: str) -> datetime:
    """[Get create time from text]
    
    Arguments:
        create_time_str {str} -- [create time str]
    
    Returns:
        datetime -- [create time]
    """

    if '分钟前' in create_time_str:
        # 2分钟前/12分钟前/55分钟前
        create_time_minute = re.sub(r"\D", "", create_time_str)  # 10分钟前 -> 10
        try:
            create_time_minute = int(create_time_minute)
        except ValueError:
            create_time = get_create_time_from_text_default_error_handler()
        else:
            create_time = (datetime.datetime.now() + datetime.timedelta(
                minutes=-create_time_minute))
    elif '今天' in create_time_str:
        # 今天 22:11/今天 21:44/今天 05:11
        create_time = create_time.split()
        if len(create_time) == 2:
            create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:") + create_time[1]
            try:
                datetime.datetime.strptime(create_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                create_time = get_create_time_from_text_default_error_handler()
        else:
            create_time = get_create_time_from_text_default_error_handler()
    elif '月' in create_time_str:
        # 9月21日 14:05/9月21日 03:07/9月20日 22:20/1月5日 08:39
        try:
            create_time = datetime.datetime.strptime(create_time_str, "%m月%d日 %H:%M")
        except ValueError:
            create_time = get_create_time_from_text_default_error_handler()
        else:
            # the year of create_time will be 1900 (default value)
            year = int(datetime.datetime.now().strftime("%Y"))
            create_time.replace(year=year)
    else:
        # 2017-12-29 10:48/2017-12-28 10:15
        try:
            create_time = datetime.datetime.strptime(create_time_str, "%Y-%m-%d %H:%M")
        except ValueError:
            create_time = get_create_time_from_text_default_error_handler()
    return create_time


@parse_decorator([])
def get_comment_list(html, wb_id):
    """
    获取评论列表
    :param html: 
    :param wb_id: 
    :return: 
    """
    cont = get_html_cont(html)
    if not cont:
        return list()

    soup = BeautifulSoup(cont, 'html.parser')
    comment_list = list()
    comments = soup.find(attrs={'node-type': 'comment_list'}).find_all(attrs={'class': 'list_li S_line1 clearfix'})

    for comment in comments:
        wb_comment = WeiboComment()
        try:
            wb_comment.comment_cont = comment.find(attrs={'class': 'WB_text'}).text.strip()
            wb_comment.comment_id = comment['comment_id']
            # TODO 将wb_comment.user_id加入待爬队列（seed_ids）
            wb_comment.user_id = comment.find(attrs={'class': 'WB_text'}).find('a').get('usercard')[3:]

            create_time = comment.find(attrs={'class': 'WB_from S_txt2'}).text
            create_time = get_create_time_from_text(create_time)
            create_time = create_time.strftime("%Y-%m-%d %H:%M:%S")
            wb_comment.create_time = create_time

            wb_comment.weibo_id = wb_id
        except Exception as e:
            parser.error('解析评论失败，具体信息是{}'.format(e))
        else:
            comment_list.append(wb_comment)
    return comment_list