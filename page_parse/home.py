import re
import json
import urllib.parse
import datetime

from bs4 import BeautifulSoup

from page_get import status
from logger import parser
from db.models import WeiboData
from config import get_crawling_mode
from decorators import parse_decorator


# weibo will use https in the whole website in the future,so the default protocol we use is https
ORIGIN = 'http'
PROTOCOL = 'https'
ROOT_URL = 'weibo.com'
CRAWLING_MODE = get_crawling_mode()


# todo 重构搜索解析代码和主页解析代码，使其可重用；捕获所有具体异常，而不是笼统的使用Exception
@parse_decorator('')
def get_weibo_infos_right(html):
    """
    通过网页获取用户主页右边部分（即微博部分）字符串
    :param html: 
    :return: 
    """
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all('script')
    pattern = re.compile(r'FM.view\((.*)\)')

    # 如果字符串'fl_menu'(举报或者帮上头条)这样的关键字出现在script中，则是微博数据区域
    cont = ''
    for script in scripts:
        m = pattern.search(script.string)
        if m and 'fl_menu' in script.string:
            all_info = m.group(1)
            cont += json.loads(all_info).get('html', '')
    return cont


@parse_decorator(None)
def get_weibo_info_detail(each, html):
    wb_data = WeiboData()

    user_cont = each.find(attrs={'class': 'face'})
    user_info = str(user_cont.find('a'))
    user_pattern = 'id=(\\d+)&amp'
    m = re.search(user_pattern, user_info)
    if m:
        wb_data.uid = m.group(1)
    else:
        parser.warning("fail to get user'sid, the page source is{}".format(html))
        return None

    weibo_pattern = 'mid=(\\d+)'
    m = re.search(weibo_pattern, str(each))
    if m:
        wb_data.weibo_id = m.group(1)
    else:
        parser.warning("fail to get weibo's id,the page source {}".format(html))
        return None

    time_url = each.find(attrs={'node-type': 'feed_list_item_date'})

    create_time_str = time_url.get('title', '').strip()
    # 2017-12-29 10:48/2017-12-28 10:15
    try:
        create_time = datetime.datetime.strptime(create_time_str, "%Y-%m-%d %H:%M")
    except ValueError as e:
        create_time = datetime.datetime.strptime("1970-01-01 08:00", "%Y-%m-%d %H:%M")
    wb_data.create_time = create_time.strftime("%Y-%m-%d %H:%M:%S")

    wb_data.weibo_url = time_url.get('href', '')
    if ROOT_URL not in wb_data.weibo_url:
        wb_data.weibo_url = '{}://{}{}'.format(PROTOCOL, ROOT_URL, wb_data.weibo_url)

    def url_filter(url):
        return ':'.join([PROTOCOL, url]) if PROTOCOL not in url and ORIGIN not in url else url

    try:
        imgs = str(each.find(attrs={'node-type': 'feed_content'}).find(attrs={'node-type': 'feed_list_media_prev'}).
                   find_all('img'))
        imgs_url = map(url_filter, re.findall(r"src=\"(.+?)\"", imgs))
        wb_data.weibo_img = ';'.join(imgs_url)
    except Exception:
        wb_data.weibo_img = ''

    try:
        li = str(each.find(attrs={'node-type': 'feed_content'}).find(attrs={'node-type': 'feed_list_media_prev'}).
                 find_all('li'))
        extracted_url = urllib.parse.unquote(re.findall(r"video_src=(.+?)&amp;", li)[0])
        wb_data.weibo_video = url_filter(extracted_url)
    except Exception:
        wb_data.weibo_video = ''

    try:
        wb_data.weibo_cont = each.find(attrs={'node-type': 'feed_content'}).find(
            attrs={'node-type': 'feed_list_content'}).text.strip()
    except Exception:
        wb_data.weibo_cont = ''

    if '展开全文' in str(each):
        is_all_cont = 0
    else:
        is_all_cont = 1

    try:
        try:
            wb_data.device = each.find(attrs={'class': 'WB_from S_txt2'}).find_all('a')[1].text
        except Exception:
            wb_data.device = each.find(attrs={'class': 'WB_from S_txt2'}).find(attrs={'action-type': 'app_source'}).text
    except Exception:
        wb_data.device = ''

    # support for forward weibo
    try:
        wb_data.repost_num = int(each.find(attrs={'action-type': 'fl_forward'}).find_all('em')[1].text)
    except Exception:
        wb_data.repost_num = 0
    try:
        wb_data.comment_num = int(each.find(attrs={'action-type': 'fl_comment'}).find_all('em')[1].text)
    except Exception:
        wb_data.comment_num = 0
    try:
        try:
            # Since both the origin and forwarded weibo have fl_like
            # in action-type, we have no choice but to use find_all.
            # PS: We could find out if this weibo is origin or
            # forwarded by finding
            # `each.find_all(attrs={'action-type': 'fl_like'})[1]`
            # existed or not
            praise = each.find_all(attrs={'action-type': 'fl_like'})[1].find_all('em')[1].text
            if '赞' in praise:
                wb_data.praise_num = 0
            else:
                wb_data.praise_num = int(praise)
        except Exception:
            praise = each.find_all(attrs={'action-type': 'fl_like'})[0].find_all('em')[1].text
            if '赞' in praise:
                wb_data.praise_num = 0
            else:
                wb_data.praise_num = int(praise)
    except Exception:
        wb_data.praise_num = 0

    try:
        expand_weibo_dataum = each.find(attrs={'node-type': 'feed_list_forwardContent'})

        # the weibo might has been deleted or has premission
        try:
            empty_weibo_dataum = expand_weibo_dataum.find(attrs={'class': 'WB_empty'})
        except Exception:
            pass
        if empty_weibo_dataum:
            wb_data.is_origin = 0
            wb_data.origin_weibo_id = "0"
            return wb_data, is_all_cont

        wb_data_forward = WeiboData()

        user_cont = expand_weibo_dataum.find(attrs={'class': 'WB_info'})
        user_info = str(user_cont.find('a'))
        user_pattern = 'id=(\\d+)&amp'
        m = re.search(user_pattern, user_info)
        if m:
            wb_data_forward.uid = m.group(1)
        else:
            parser.warning("fail to get user'sid, the page source is{}".format(html))
            return wb_data, is_all_cont

        weibo_pattern = 'mid=(\\d+)'
        m = re.search(weibo_pattern, str(expand_weibo_dataum.find(attrs={'class': 'WB_func clearfix'})))
        if m:
            wb_data_forward.weibo_id = m.group(1)
        else:
            parser.warning("fail to get weibo's id,the page source {}".format(html))
            return wb_data, is_all_cont

        wb_data.is_origin = 0
        wb_data.origin_weibo_id = m.group(1)

        # Since the origin weibo can't have img/video
        # So we move origin's img/video to the forwarded
        wb_data_forward.weibo_img = wb_data.weibo_img
        wb_data_forward.weibo_video = wb_data.weibo_video
        wb_data.weibo_img = ''
        wb_data.weibo_video = ''

        time_url = expand_weibo_dataum.find(attrs={'node-type': 'feed_list_item_date'})

        create_time_str = time_url.get('title', '').strip()
        # 2017-12-29 10:48/2017-12-28 10:15
        try:
            create_time = datetime.datetime.strptime(create_time_str, "%Y-%m-%d %H:%M")
        except ValueError as e:
            create_time = datetime.datetime.strptime("1970-01-01 08:00", "%Y-%m-%d %H:%M")
        wb_data_forward.create_time = create_time.strftime("%Y-%m-%d %H:%M:%S")

        wb_data_forward.weibo_url = time_url.get('href', '')
        if ROOT_URL not in wb_data_forward.weibo_url:
            wb_data_forward.weibo_url = '{}://{}{}'.format(PROTOCOL, ROOT_URL, wb_data_forward.weibo_url)

        try:
            wb_data_forward.weibo_cont = expand_weibo_dataum.find(attrs={'node-type': 'feed_list_reason'}).text.strip()
        except Exception:
            wb_data_forward.weibo_cont = ''

        try:
            wb_data_forward.device = expand_weibo_dataum.find(attrs={'class': 'WB_from S_txt2'}).find(attrs={'action-type': 'app_source'}).text
        except Exception:
            wb_data_forward.device = ''

        try:
            handle = expand_weibo_dataum.find(attrs={'class': 'WB_func clearfix'}).find_all("em")
            # use this line to debug num
            # print(handle)
        except Exception:
            wb_data_forward.repost_num = 0
            wb_data_forward.comment_num = 0
            wb_data_forward.praise_num = 0
        else:
            try:
                wb_data_forward.repost_num = int(handle[1].text)
            except Exception:
                wb_data_forward.repost_num = 0
            try:
                # comment_icon = expand_weibo_dataum.find(attrs={'class': 'W_ficon ficon_repeat S_ficon'})
                # wb_data_forward.comment_num = int(comment_icon.find_next_siblings("em").text)
                wb_data_forward.comment_num = int(handle[3].text)
            except Exception:
                wb_data_forward.comment_num = 0
            try:
                # wb_data_forward.praise_num = int(expand_weibo_dataum.find(attrs={'action-type': 'fl_like'}).find_all('em')[1].text)
                wb_data_forward.praise_num = int(handle[5].text)
            except Exception:
                wb_data_forward.praise_num = 0

        return wb_data, is_all_cont, wb_data_forward

    except Exception:
        return wb_data, is_all_cont


def get_weibo_list(html):
    """
    get the list of weibo info
    :param html:
    :return: 
    """
    if not html:
        return list()
    soup = BeautifulSoup(html, "html.parser")
    feed_list = soup.find_all(attrs={'action-type': 'feed_list_item'})
    weibo_datas = []
    for data in feed_list:
        r = get_weibo_info_detail(data, html)
        if r is not None:
            wb_data = r[0]
            if r[1] == 0 and CRAWLING_MODE == 'accurate':
                weibo_cont = status.get_cont_of_weibo(wb_data.weibo_id)
                wb_data.weibo_cont = weibo_cont if weibo_cont else wb_data.weibo_cont
            weibo_datas.append(wb_data)
            if len(r) == 3:
                weibo_datas.append(r[2])
    return weibo_datas


@parse_decorator(1)
def get_max_num(html):
    """
    get the total page number
    :param html:
    :return:
    """
    soup = BeautifulSoup(html, "html.parser")
    try:
        href_list = soup.find(attrs={'action-type': 'feed_list_page_morelist'}).find_all('a')
    except Exception:
        # The user has only one page
        return 1
    return len(href_list)


@parse_decorator(list())
def get_data(html):
    """
    从主页获取具体的微博数据
    :param html: 
    :return: 
    """
    cont = get_weibo_infos_right(html)
    return get_weibo_list(cont)


@parse_decorator(list())
def get_ajax_data(html):
    """
    通过返回的ajax内容获取用户微博信息
    :param html: 
    :return: 
    """
    cont = json.loads(html, encoding='utf-8').get('data', '')
    return get_weibo_list(cont)


@parse_decorator(1)
def get_total_page(html):
    """
    从ajax返回的内容获取用户主页的所有能看到的页数
    :param html: 
    :return: 
    """
    cont = json.loads(html, encoding='utf-8').get('data', '')
    if not cont:
        # todo 返回1或者0还需要验证只有一页的情况
        return 1
    return get_max_num(cont)
