# -*- coding: utf-8 -*-
import os
import re
import time
import logging
import json
import requests
import datetime
import ddddocr as dd
from openai import OpenAI
code = os.getenv("wechat_login_code") #将登录code存储到变量中方便读取
import context_utils
import edu_api
import music_service
import text_utils
from context_utils import (
    append_conversation_message,
    clear_conversation_context,
    cleanup_old_logs,
    load_conversation_context,
    pop_last_conversation_message,
)
from edu_api import get_parentId, upload_voice
from music_service import get_song, get_voice_list
from text_utils import markdown_to_text, parse_song_request, replace_non_bmp
timestemp=time.time()
timestemp*=1000
edu_api.timestemp = timestemp
token=""
edu_api.token = token
song_list=[]
REQUEST_TIMEOUT = 180
USERNAME = os.getenv("username") or "default_user"
LOG_DIR = os.path.join("./logs", USERNAME)
CONTEXT_FILE = os.path.join(LOG_DIR, "conversation_context.json")
MAX_CONTEXT_MESSAGES = 20
# Ensure per-user log directory exists early (used by context + song list id persistence)
os.makedirs(LOG_DIR, exist_ok=True)

# Persist song list id under the user's log directory.
# Backward compatible: migrate legacy ./song_list_id.txt to LOG_DIR on first run.
LEGACY_SONG_LIST_ID_FILE = os.path.join(os.getcwd(), "song_list_id.txt")
SONG_LIST_ID_FILE = os.path.join(LOG_DIR, "song_list_id.txt")
if not os.path.exists(SONG_LIST_ID_FILE) and os.path.exists(LEGACY_SONG_LIST_ID_FILE):
    try:
        os.replace(LEGACY_SONG_LIST_ID_FILE, SONG_LIST_ID_FILE)
    except OSError:
        pass

# Ensure the song list ID placeholder exists for downstream components
if not os.path.exists(SONG_LIST_ID_FILE):
    open(SONG_LIST_ID_FILE, "w", encoding="utf-8").close()

song_list_id = None
with open(SONG_LIST_ID_FILE, "r", encoding="utf-8") as _f:
    _content = _f.read().strip()
    if _content:
        song_list_id = _content
# 对话上下文缓存，启动时从本地日志目录恢复
context_utils.CONTEXT_FILE = CONTEXT_FILE
context_utils.MAX_CONTEXT_MESSAGES = MAX_CONTEXT_MESSAGES
conversation_context = context_utils.conversation_context


class TimeoutSession(requests.Session):
    def __init__(self, timeout=None):
        super().__init__()
        self._timeout = timeout

    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", self._timeout)
        return super().request(method, url, **kwargs)


session = TimeoutSession(timeout=REQUEST_TIMEOUT)
music_service.session = session
edu_api.session = session
class CustomError(Exception):
    def __init__(self, message):
        self.message = message
os.environ['TZ'] = 'Asia/Shanghai'
time.tzset()
year = datetime.datetime.now().year
# LOG_DIR is created above; keep this as a no-op safety in case of refactors.
os.makedirs(LOG_DIR, exist_ok=True)  # 确保 logs 文件夹存在
studentName=''
phoneNumber=''
relation=os.getenv("parents_name")
script_start_time = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(time.time()))
log_filename = os.path.join(LOG_DIR, f"{script_start_time}.log")
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
load_conversation_context()
cleanup_old_logs(LOG_DIR)

no_word = ["正在待机", "收到", "余额"]
ds_model = "deepseek-reasoner"
# secret = [os.getenv("username"), os.getenv("password")]
time_stemp = time.time()
reason = False
times = 0

username=os.getenv("username") #将用户名存储到变量中方便读取


retry_times=0

def get():
    global times,studentName,phoneNumber
    time.sleep(3)
    times += 1
    if times >= 20:
        exit(-1)
    try:
        
        headers = {
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Origin': 'https://wxapp.nhedu.net',
    'Pragma': 'no-cache',
    'Referer': 'https://wxapp.nhedu.net/edu-iot/mobile/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 16; 25102RKBEC Build/BP2A.250605.031.A3; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/142.0.7444.173 Mobile Safari/537.36 XWEB/1420229 MMWEBSDK/20260101 MMWEBID/8824 REV/f54f4fa14ece7d4915b69ce007dd50b11f259aed MicroMessenger/8.0.69.3040(0x2800453F) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64',
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'content-type': 'application/json; charset=UTF-8',
    'edu-token': token,
    'sec-ch-ua': '"Chromium";v="142", "Android WebView";v="142", "Not_A Brand";v="99"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'sso-user': 'true',
    'x-requested-with': 'com.tencent.mm',
    # 'Cookie': 'sl-session=xxB8Wj6QrmktzotWSI9laQ==; edu-token=b21df2a9-44c5-4b76-a05b-1ade349356f4',
}

        json_data = {
    't': timestemp,
    'pageNo': 1,
    'pageSize': 10,
    "startTime": f"{year}-01-01 00:00:00",
    "endTime": f"{year}-12-31 23:59:59",
    'pageType': 'first',
}
        response = requests.post(
        'https://wxapp.nhedu.net/edu-iot/be/ym-message//queryMessages',
        
        headers=headers,
        json=json_data,
    )
        deresponse=json.loads(response.content)
        # logging.info(f"获取信息: {deresponse}")
        if deresponse['msg']!='success':
            raise CustomError('get messages failed')
        messages=json.loads(response.content)
        words=[]
        for i in messages['result']["content"]:
            words.append(i['content'])
        if phoneNumber==None or phoneNumber=='':
            phoneNumber=messages['result']["content"][0]['parentPhone']
        studentName=messages['result']["content"][0]['studentName']
        edu_api.phoneNumber = phoneNumber

        if words:
            if words[0] is not None:
                times = 0
                if words[0]!="正在待机":#防止日志在待机时增长过大
                    logging.info(f"获取信息: {words[0]}")
                return words
            else:
                time.sleep(5)
                return get()
        else:
            time.sleep(5)
            return get()
    except KeyboardInterrupt:
        exit(0)
    except Exception as e:
        if response:
            logging.error(response.content)
        try:
            if messages['result']["content"] == None:
                return [" "]
        except Exception as e:
            raise CustomError("get messages failed,messages may be NOT EXIS")
        
        logging.error(f"get() 出现异常: {e}")
        return get()


def send_words(context,type=0,interval=0):

    try:
        now = datetime.datetime.now()
        year = now.year
        month = now.month
        day = now.day
        hour = now.hour
        minute = now.minute
        second = now.second
        date_string = f"{year}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}+08:00"
        global timestemp,time_stemp

        headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json; charset=UTF-8',
    'Origin': 'https://wxapp.nhedu.net',
    'Referer': 'https://wxapp.nhedu.net/edu-iot/mobile/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0',
    'edu-token': f'{token}',
    'sec-ch-ua': '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sso-user': 'true',
}
        if type:
            logging.info(f"发送音频链接：{context}，时长：{interval}秒")
            json_data = {
    't': time_stemp,
    'dateTime': date_string,
    'studentName': studentName,
    'submitType': 1,
    'audioFilePath': context,
    'audioLen': 60,
    'phoneNumber': phoneNumber,
    'bindId': 0,
}

            response = session.post('https://wxapp.nhedu.net/edu-iot/be/ym-message//post',headers=headers, json=json_data)
            os.system("rm -f 1.mp3")
            return
        context = markdown_to_text(context)
        context = replace_non_bmp(context)
        logging.info(f"发送信息: {context}")
        
        if len(context) >= 250:
            # 分段发送
            words_to_spare = [context[i:i + 150] for i in range(0, len(context), 160)]
            for segment in words_to_spare:
                time.sleep(1)
                json_data = {
    't': time_stemp,
    'dateTime': date_string,
    'studentName': studentName,
    'submitType': 0,
    'message': segment,
    'phoneNumber': phoneNumber,
    'bindId': 0,
}
                response = session.post('https://wxapp.nhedu.net/edu-iot/be/ym-message//post',headers=headers, json=json_data)   
        else:
            json_data = {
    't': time_stemp,
    'dateTime': date_string,
    'studentName': studentName,
    'submitType': 0,
    'message': context,
    'phoneNumber': phoneNumber,
    'bindId': 0,
}
            time.sleep(1)
            response = session.post('https://wxapp.nhedu.net/edu-iot/be/ym-message//post',headers=headers, json=json_data)   
        
        deresponse=json.loads(response.content)
        if deresponse['msg']!='success':

            raise CustomError('send failed')
            
        time_stemp = time.time()
    except Exception as e:
        if response:
            logging.error(response.content)
        logging.error(f"send_words() 出现异常: {e}")

music_service.send_words = send_words
edu_api.send_words = send_words

def blance():
    url = "https://api.deepseek.com/user/balance"
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {os.getenv("API_KEY")}'
    }
    response = session.get(url, headers=headers)
    return response.text

def deepseek_api(qes, models):
    logging.info(f"调用 DeepSeek API: {qes}")
    client = OpenAI(api_key=os.getenv("API_KEY"), base_url="https://api.deepseek.com")
    messages = [{
        "role": "system",
        "content": "如果这是个数学问题，请遵循以下规则：“我的环境无法渲染Latex和markdown,所以请以纯文本形式输出数学公式，且尽量避免换行。”其他情况请正常回答。"
    }]
    messages.extend(conversation_context)
    response = client.chat.completions.create(
        model=models,
        messages=messages,
        stream=True,
        temperature=1.5
    )
    reasoning_content = ""
    reasoning_content_total = ""
    content = ""
    content_total = ""

    for chunk in response:
        if models == "deepseek-reasoner":
            if chunk.choices[0].delta.reasoning_content and reason:
                reasoning_content += chunk.choices[0].delta.reasoning_content
                reasoning_content_total += chunk.choices[0].delta.reasoning_content
                if len(reasoning_content) >= 150:
                    send_words(reasoning_content)
                    reasoning_content = ""
            elif chunk.choices[0].delta.content:
                if reasoning_content:
                    send_words(reasoning_content)
                    reasoning_content = ""
                if len(content) >= 150:
                    send_words(content)
                    content = ""
                content += chunk.choices[0].delta.content
                content_total += chunk.choices[0].delta.content
        else:
            if chunk.choices[0].delta.content:
                if len(content) >= 150:
                    send_words(content)
                    content = ""
                content += chunk.choices[0].delta.content
                content_total += chunk.choices[0].delta.content
    if content:
        send_words(content)
    if reasoning_content:
        send_words(reasoning_content)
    logging.info(f"推理内容: {reasoning_content_total}")
    logging.info(f"回答内容: {content_total}")
    return content_total

def login(code):
    global token
    headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json; charset=UTF-8',
    'Origin': 'https://wxapp.nhedu.net',
    'Pragma': 'no-cache',
    'Referer': 'https://wxapp.nhedu.net/edu-base/mobile/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 16; 25102RKBEC Build/BP2A.250605.031.A3; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/142.0.7444.173 Mobile Safari/537.36 XWEB/1420283 MMWEBSDK/20260201 MMWEBID/8824 REV/ec8e1e22ce14c15777e32b125633f1cf59a36aa3 MicroMessenger/8.0.69.3040(0x2800455B) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64',
    'X-Requested-With': 'com.tencent.mm',
    'edu-token': 'null',
    'sec-ch-ua': '"Chromium";v="142", "Android WebView";v="142", "Not_A Brand";v="99"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'sso-user': 'true',
    # 'Cookie': 'sl-session=IVVKS0kdymk5DqwwMSbEUQ==',
}

    json_data = {
        't': timestemp,
        'code': code,
        'appId': 'wxbfc968922bd0610d',
        'loginType': 'wx_mp',
    }

    response = requests.post('https://wxapp.nhedu.net/edu-base/be/open/login', headers=headers, json=json_data)
    deresponse=json.loads(response.content)
    token=deresponse["result"]["token"]
    edu_api.token = token
    if deresponse['msg']!='success':
        raise CustomError("login failed")
        exit(-1)

def get_phoneNumber(relation):
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
        'Connection': 'keep-alive',
        'Referer': 'https://wxapp.nhedu.net/edu-iot/mobile/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0',
        'edu-token': f'{token}',
        'sec-ch-ua': '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sso-user': 'true',
    }

    params = {
        't': f'{timestemp}',
    }

    response = session.get('https://wxapp.nhedu.net/edu-iot/be/ym-message//parents', params=params, headers=headers)
    result = json.loads(response.content)
    for item in result.get("result", []):
        if item.get("relation") == relation:
            logging.info(f"获取家长电话：{item['mobile']}")
            return item.get("mobile")
    return None

# 登录操作
login(code)
if token:
    logging.info(f"成功登录 token: {token}")
phoneNumber=get_phoneNumber(relation)
send_words("成功登录 请使用‘/ds’进行提问,使用‘/ds (内容)/reason’输出推理过程（仅在模型为r1时接受）使用‘/v3’切换至v3模型，使用‘/r1’切换至r1模型，使用“/new”开始新对话，使用‘/查询歌曲 歌名’查询歌曲列表，使用‘/点歌 歌名 第几首’点歌")
send_words("使用‘/设置歌单id 歌单id’设置网易云歌单id，使用‘/获取歌单’获取歌单内容，使用‘/歌单第几首’点歌")
get()
time.sleep(2)
times = 0
words = get()
times = 0
daiji = False
latest_word = words[0]
# 主循环：检测新信息并调用 API 返回回复
while True:
    try:
        if time.time() - time_stemp >= 300:
            daiji = True
        words = get()
        if words[0] == "/v3":
            ds_model = "deepseek-chat"
            send_words("//已切换至v3")
            logging.info("已切换至v3")
            words = get()
            latest_word = words[0]
        elif words[0] == "/r1":
            ds_model = "deepseek-reasoner"
            send_words("//已切换至r1")
            logging.info("已切换至r1")
            words = get()
            latest_word = words[0]
        elif words[0] == "stops":
            send_words("已停止")
            logging.info("已停止")
            exit(0)
        elif words[0] == "待机" or daiji:
            send_words("正在待机")
            logging.info("正在待机")
            words = get()
            latest_word = words[0]
            while True:
                words=get()
                time.sleep(180)
                words = get()
                if words[0] != latest_word and words[0] != "正在待机":
                    daiji = False
                    words = get()
                    time_stemp = time.time()
                    break
        elif words[0] == "余额":
            send_words(blance())
            words = get()
            latest_word = words[0]
        elif words[0] == "/new":
            # 用户主动开始新一轮对话，重置上下文
            send_words("已开启新的对话，历史上下文已清空")
            logging.info("已清空对话上下文并开始新对话")
            clear_conversation_context()
            words = get()
            latest_word = words[0]
            time_stemp = time.time()

        if (words[0] != latest_word and
            re.search(re.escape("/ds"), words[0])):
            send_words("收到")
            logging.info(f"收到: {words[0]}")
            qes = words[0].replace("/ds", "")
            if re.search(re.escape("/reason"), words[0]):
                reason = True
                qes = qes.replace("/reason", "")
            # 统一整理用户提问内容，确保上下文记录干净
            qes = qes.strip()
            user_message_recorded = False
            if not qes:
                send_words("请提供提问内容")
                reason = False
                words = get()
                latest_word = words[0]
                time_stemp = time.time()
                continue
            append_conversation_message("user", qes)
            user_message_recorded = True
            try:
                answer_text = deepseek_api(qes, ds_model)
            except Exception:
                if user_message_recorded:
                    pop_last_conversation_message()
                raise
            if answer_text:
                # 记录模型回复，供后续轮次继续引用
                append_conversation_message("assistant", answer_text)
            time.sleep(1)
            send_words("回答完毕")
            reason = False
            words = get()
            latest_word = words[0]
            time_stemp = time.time()
        elif (words[0] != latest_word and
            re.search(re.escape("/查询歌曲"), words[0])):
            send_words("收到请求")
            logging.info(f"收到: {words[0]}")
            song_name=words[0].replace("/查询歌曲", "")
            song_name=song_name.replace(" ","")
            song_list=get_voice_list(song_name)
            number=1

            if song_list:
                logging.info("成功获取")
                for i in song_list:
                    send_words(f"{number}.{i}")
                    number+=1
            song_list=[]
        elif (words[0] != latest_word and
            re.search(re.escape("/点歌"), words[0])):
            send_words("收到请求")
            logging.info(f"点歌: {words[0]}")
            song_name, song_number = parse_song_request(words[0])
            if song_name and song_number:
                send_words(f"正在点歌: {song_name} 第{song_number}首")
                logging.info(f"正在点歌: {song_name} 第{song_number}首")
                interval=get_song(name=song_name, choose=song_number)
                if interval:
                    # parent_id = get_parentId(relation)
                    # if not parent_id:
                    #     send_words("获取家长信息失败")
                    #     logging.info("获取家长信息失败")
                    #     continue
                    with open("./1.mp3", "rb") as f:
                        upload_url = upload_voice(f)
                        if upload_url:
                            send_words(upload_url, 1, interval)
                            logging.info("点歌成功")
                            send_words("点歌成功")
                        else:
                            send_words("点歌失败")
                            logging.info("点歌失败")
                else:
                    send_words("点歌失败")
                    logging.info("点歌失败")
            else:
                send_words("无法解析点歌请求")
                logging.info("无法解析点歌请求")
        elif words[0] != latest_word and re.search(re.escape("/设置歌单id"), words[0]):
            send_words("收到请求")
            logging.info(f"设置歌单id: {words[0]}")
            song_list_id=words[0].replace("/设置歌单id","").strip()
            with open(SONG_LIST_ID_FILE, "w", encoding="utf-8") as f:
                f.write(song_list_id)
            song_list=music_service.get_personal_song_list(song_list_id)
            send_words(f"已设置歌单id为: {song_list_id}")
            logging.info(f"已设置歌单id为: {song_list_id}")
        elif words[0] != latest_word and re.search(re.escape("/获取歌单"), words[0]):
            send_words("收到请求")
            logging.info(f"获取歌单: {words[0]}")
            if not song_list_id:
                send_words("请先使用‘/设置歌单id 歌单id’设置歌单id")
                logging.info("未设置歌单id")
                continue
            try:
                
                if not song_list:
                    song_list=music_service.get_personal_song_list(song_list_id)
                if not song_list:
                    send_words("获取歌单失败，请检查歌单id是否正确")
                    logging.info("获取歌单失败")
                    continue
                if song_list:
                    send_words("获取成功")
                    music_service.send_personal_song_list(song_list)
                logging.info("获取歌单成功")
            except Exception as e:
                send_words("获取歌单失败")
                logging.error(f"获取歌单出现异常: {e}")
        elif words[0] != latest_word and re.search(re.escape("/歌单第"), words[0]):
            send_words("收到请求")
            logging.info(f"歌单点歌: {words[0]}")
            song_number = text_utils.parse_playlist_index(words[0])
            if not song_list:
                song_list=music_service.get_personal_song_list(song_list_id)
            if not song_number:
                send_words("无法解析歌单序号，请重试")
                logging.info("无法解析歌单序号")
                continue
            if not isinstance(song_list, dict) or not song_list:
                send_words("歌单为空，请先使用‘/获取歌单’")
                logging.info("歌单为空")
                continue
            playlist_entries = list(song_list.items())
            if song_number < 1 or song_number > len(playlist_entries):
                send_words("歌单序号超出范围")
                logging.info("歌单序号超出范围")
                continue
            target_name,target_id= playlist_entries[song_number - 1]
            send_words(f"正在点歌歌单第{song_number}首: {target_name} id:{target_id}")
            logging.info(f"正在点歌歌单第{song_number}首: {target_name}id:{target_id}")
            interval = get_song(id = target_id)
            if interval is None:
                send_words("点歌失败")
                logging.info("歌单点歌失败")
                continue
            # parent_id = get_parentId(relation)
            # if not parent_id:
            #     send_words("获取家长信息失败")
            #     logging.info("获取家长信息失败")
            #     continue
            with open("./1.mp3", "rb") as f:
                upload_url = upload_voice(f)
                if upload_url:
                    send_words(upload_url, 1, interval)
                    logging.info("歌单点歌成功")
                    send_words("点歌成功")
                else:
                    send_words("点歌失败")
                    logging.info("歌单点歌失败")
            
            
        time.sleep(1)
        get()


    except TypeError:

        words=get()
        continue

    except KeyboardInterrupt:

        exit(0)

    except Exception as e:

        login()
        logging.info("崩溃重启")
        logging.error(f"主循环出现异常: {e}")
        continue






