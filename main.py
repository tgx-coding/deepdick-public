# -*- coding: utf-8 -*-
import os
import re
import time
import logging
import json
import requests
import markdown
import html2text
import datetime
from requests_toolbelt import MultipartEncoder
from requests_toolbelt import MultipartEncoderMonitor
import ddddocr as dd
from PIL import Image
from pydub import AudioSegment
from openai import OpenAI
#import pymysql as mysql
timestemp=time.time()
timestemp*=1000
token=""
song_list=[]
session=requests.session()
class CustomError(Exception):
    def __init__(self, message):
        self.message = message
os.environ['TZ'] = 'Asia/Shanghai'
time.tzset()
year = datetime.datetime.now().year
os.makedirs(f"./logs/{os.getenv("username")}", exist_ok=True)  # 确保 logs 文件夹存在
studentName=''
phoneNumber=''
relation=os.getenv("parents_name")
script_start_time = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(time.time()))
log_filename = f"./logs/{os.getenv("username")}/{script_start_time}.log"
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

no_word = ["正在待机", "收到", "余额"]
ds_model = "deepseek-reasoner"
secret = [os.getenv("username"), os.getenv("password")]

time_stemp = time.time()
reason = False
times = 0

username=os.getenv("username") #将用户名存储到变量中方便读取

'''
#配置mysql,记得要配置好先喵
db = mysql.connect(
    host="mysql",
    user="mysql",
    password="114514",
    database="deepdick"
)
cursor = db.cursor()
#定义sql语句
log ="""INSERT INTO LOGS(user,token)   
        VALUES (%s, %s)""" #写入操作日志数据库
balance_write ="""INSERT INTO BALANCE(user,balance) 
            VALUES (%s,%S)""" #写入余额数据库
balance_read ="""SELECT balance FROM BALANCE WHERE user = %s""" #读取余额数据库

#没搞懂消息发送逻辑，摆了，给你放个实例你来写吧（
cursor.execute(balance_read, (username)) #这里前面是会执行的定义好的语句，后面是要用来替换语句中占位符的内容（比如这里就会用username这个变量替换第一个占位符）
results = cursor.fetchall() #读取语句
for row in results:
    balance = row[0] #这里指的是把balance定义为查询到的第一个结果
'''



def markdown_to_text(markdown_text):
    # 将 Markdown 转换为 HTML，再转换为纯文本
    html_content = markdown.markdown(markdown_text)
    text_maker = html2text.HTML2Text()
    text_maker.ignore_links = True
    text_maker.ignore_images = True
    text_maker.ignore_emphasis = True
    plain_text = text_maker.handle(html_content)
    return plain_text
def time_to_seconds(time_str):
    """
    将"x分x秒"格式的时间转换为总秒数
    
    参数:
        time_str: 字符串，格式如"5分30秒"、"1分"、"45秒"等
    
    返回:
        int: 总秒数
    """
    # 初始化分钟和秒数
    minutes = 0
    seconds = 0
    
    # 检查字符串中是否包含"分"
    if "分" in time_str:
        # 分割字符串
        parts = time_str.split("分")
        
        # 提取分钟部分
        if parts[0]:  # 确保分钟部分不为空
            minutes = int(parts[0])
        
        # 提取秒数部分（如果存在）
        if len(parts) > 1 and parts[1] and "秒" in parts[1]:
            seconds_str = parts[1].replace("秒", "")
            if seconds_str:  # 确保秒数部分不为空
                seconds = int(seconds_str)
    elif "秒" in time_str:
        # 只有秒数的情况
        seconds_str = time_str.replace("秒", "")
        if seconds_str:  # 确保秒数部分不为空
            seconds = int(seconds_str)
    
    # 计算总秒数
    total_seconds = minutes * 60 + seconds
    return total_seconds
retry_times=0
def get():
    global times,studentName,phoneNumber
    times += 1
    if times >= 10:
        exit(-1)
    try:
        
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
        json_data = {
    't': timestemp,
    'pageNo': 1,
    'pageSize': 10,
    'startTime': '2025-01-01T00:00:00+08:00',
    'endTime': f'{year}-12-31T23:59:59+08:00',
    'pageType': 'first',
}
        response = session.post('https://wxapp.nhedu.net/edu-iot/be/ym-message//list',headers=headers, json=json_data)
        deresponse=json.loads(response.content)
        if deresponse['msg']!='success':
            raise CustomError('get messages failed')
        messages=json.loads(response.content)
        words=[]
        for i in messages['result']['rows']:
            words.append(i['content'])
        studentName=messages['result']['rows'][0]['studentName']
        phoneNumber=messages['result']['rows'][0]['parentPhone']

        if words:
            if words[0] is not None:
                times = 0
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
        logging.error(f"get() 出现异常: {e}")
        return get()
def get_voice_list(name,from_where=1,retry_times=0):
    try:
        logging.info(f"查询歌曲:{name}")
        if retry_times>=10:
            retry_times=0
            raise CustomError("get voice list failed")
        response=requests.get(f"https://api.vkeys.cn/v2/music/netease?word={name}")
        voice_list=json.loads(response.content)
        
        if voice_list["code"]!=200:
            retry_times+=1
            logging.info(f"获取歌曲列表重试次数：{retry_times}")
            return get_voice_list(name,from_where,retry_times)
        de_voice_list=[]
        for i in voice_list["data"]:
            de_voice_list.append(f"{i["song"]}---{i["singer"]}")
        
        return de_voice_list
    except Exception as e:
        if from_where:
            send_words("获取失败")
        else:
            return []
        logging.error(f"出现异常: {e}")
        return
        
def get_song(name,choose=1,quality=4,retry_times=0):
    try:
        response=requests.get(f"https://api.vkeys.cn/v2/music/netease?word={name}&choose={choose}&quality={quality}")
        voice=json.loads(response.content)
        if voice['code']!=200:
            if retry_times>=10:
                retry_times=0
                raise CustomError("get voice file failed")
            else:
                retry_times+=1
                logging.info(f"重试获取歌曲次数：{retry_times}")
                return get_song(name,choose,quality,retry_times)
        else:
            voice_url=voice["data"]["url"]
            interval=time_to_seconds(voice["data"]["interval"])
            logging.info(f"下载url：{voice_url}")
            file=requests.get(voice_url)
            logging.info("下载完成")
            open('./1.mp3','wb').write(file.content)
            return interval
    except Exception as e:
        send_words("获取歌曲失败")
        logging.error(f"出现异常: {e}")
def my_callback(monitor):
    progress = (monitor.bytes_read / monitor.len) * 100
    logging.info("\r 文件上传进度：%d%%(%d/%d)" % (progress, monitor.bytes_read, monitor.len), end=" ")
def get_parentId(relation):
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

    response = session.get('https://wxapp.nhedu.net/edu-iot/be/ym-message//parents', params=params,headers=headers)
    result=json.loads(response.content)
    for i in result["result"]:
        if i["relation"]==relation:
            logging.info(f"获取家长id：{i["parentId"]}")
            return i["parentId"]
def upload_voice(in_file, parentId,
                 time=time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime()),
                 max_retries: int = 3,
                 chunk_size: int = 256 * 1024):
    filename = f"{parentId}_{phoneNumber}_{time}.wav"
    fields = {
        'parentId': str(parentId),
        'mobile': str(phoneNumber),
        'file': (filename, in_file, 'application/octet-stream')
    }

    if hasattr(in_file, "seek"):
        in_file.seek(0)

    try:
        headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
    'Connection': 'keep-alive',
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

        encoder = MultipartEncoder(fields=fields)

        progress_state = {'last_bucket': -1}

        def make_callback(total_length):
            def _callback(monitor):
                if not total_length:
                    return
                percent = int(monitor.bytes_read * 100 / total_length)
                bucket = percent // 10
                if bucket > progress_state['last_bucket']:
                    progress_state['last_bucket'] = bucket
                    logging.info(f"上传进度：{percent}% ({monitor.bytes_read}/{total_length} bytes)")
            return _callback

        monitor = MultipartEncoderMonitor(encoder, make_callback(encoder.len))
        headers['Content-Type'] = monitor.content_type

        logging.info("正在上传")
        response = session.post(
        'https://wxapp.nhedu.net/edu-iot/be/ym-message//upload-voice',
        headers=headers,
        data=monitor,
        timeout=180,
    )

        deresponse=json.loads(response.content)
        if deresponse['msg']!='success':
            raise CustomError('UPLOAD failed')
        upload_file_url=deresponse["result"]
        logging.info("成功")
        return upload_file_url

    except Exception as exc:
        logging.error(f"上传失败: {exc}")
        send_words("请重试")
        return None

def mp3_to_wav(file_path="./1.mp3"):
    song = AudioSegment.from_mp3(file_path)
    song.export("1.wav", format="wav")
    return


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
    't': timestemp,
    'dateTime': date_string,
    'studentName': studentName,
    'dataType': 1,
    'fileUrl': context,
    'voiceTime': 60,
    'phoneNumber': phoneNumber,
}

            response = requests.post('https://wxapp.nhedu.net/edu-iot/be/ym-message//post',headers=headers, json=json_data)
            os.system("rm -f 1.mp3")
            return
        logging.info(f"发送信息: {context}")
        context = markdown_to_text(context)
        context = replace_non_bmp(context)
        if len(context) >= 160:
            # 分段发送
            words_to_spare = [context[i:i + 150] for i in range(0, len(context), 160)]
            for segment in words_to_spare:
                time.sleep(1)
                json_data = {
                
    't': timestemp,
    'dateTime': date_string,
    'studentName': studentName,
    'dataType': 0,
    'content': segment,
    'phoneNumber': phoneNumber,
}
                response = session.post('https://wxapp.nhedu.net/edu-iot/be/ym-message//post',headers=headers, json=json_data)   
        else:
            json_data = {
    't': timestemp,
    'dateTime': date_string,
    'studentName': studentName,
    'dataType': 0,
    'content': context,
    'phoneNumber': phoneNumber,
}
            time.sleep(1)
            response = session.post('https://wxapp.nhedu.net/edu-iot/be/ym-message//post',headers=headers, json=json_data)   
        deresponse=json.loads(response.content)
        if deresponse['msg']!='success':
            raise CustomError('send failed')
        time_stemp = time.time()
    except Exception as e:
        logging.error(f"send_words() 出现异常: {e}")

def replace_non_bmp(text, replacement="(无法显示)"):
    return re.sub(r'[^\u0000-\uFFFF]', replacement, text)
def parse_song_request(text):
    """
    解析点歌请求，提取歌曲名和序号
    格式：/点歌XXX第XX首
    """
    pattern = r'/点歌(.+?)第(\d+)首'
    match = re.search(pattern, text)
    
    if match:
        song_name = match.group(1)  # 歌曲名
        song_number = match.group(2)  # 序号
        return song_name, int(song_number)
    else:
        return None, None

def blance():
    url = "https://api.deepseek.com/user/balance"
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {os.getenv("API_KEY")}'
    }
    response = requests.get(url, headers=headers)
    return response.text

def deepseek_api(qes, models):
    logging.info(f"调用 DeepSeek API: {qes}")
    client = OpenAI(api_key=os.getenv("API_KEY"), base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model=models,
        messages=[
            {"role": "system", "content": "如果这是个数学问题，请遵循以下规则：“我的环境无法渲染Latex和markdown,所以请以纯文本形式输出数学公式，且尽量避免换行。”其他情况请正常回答。"},
            {"role": "user", "content": qes},
        ],
        stream=True,
        temperature=1.5
    )
    ans = ['', '']
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
    logging.info(f"推理内容: {reasoning_content_total}")
    logging.info(f"回答内容: {content_total}")
    return ans

def login():
    global token
    headers = {
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
    'Connection': 'keep-alive',
    'If-Modified-Since': 'Sat, 20 Sep 2025 05:20:28 GMT',
    'If-None-Match': '"68ce399c-371"',
    'Referer': 'https://wxapp.nhedu.net/edu-base/mobile/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0',
    'sec-ch-ua': '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}

    response = session.get('https://wxapp.nhedu.net/edu-base/mobile/', headers=headers)
    image=requests.get("https://wxapp.nhedu.net/edu-base/be/captcha/captcha.jpg?uuid=2e022573-11a3-4f25-8999-cdfa36bff424")
    ocr = dd.DdddOcr()
    result = ocr.classification(image.content)
    logging.info(f"验证码：{result}")
    headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json; charset=UTF-8',
    'Origin': 'https://wxapp.nhedu.net',
    'Referer': 'https://wxapp.nhedu.net/edu-base/mobile/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0',
    'edu-token': 'null',
    'sec-ch-ua': '"Microsoft Edge";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sso-user': 'true',
}

    json_data = {
        't': 1759378471057,
        'loginType': 'sso_username',
        'username': str(secret[0]),
        'password': str(secret[1]),
        'captcha': str(result),
        'captchaUuid': '2e022573-11a3-4f25-8999-cdfa36bff424',
    }

    response = session.post('https://wxapp.nhedu.net/edu-base/be/open/login',headers=headers, json=json_data)
    deresponse=json.loads(response.content)
    token=deresponse["result"]["token"]
    if deresponse['msg']!='success':
        raise CustomError("login failed")
        exit(-1)



# 登录操作
login()
get()
logging.info("成功登录")
send_words("成功登录 请使用‘/ds’进行提问,使用‘/ds (内容)/reason’输出推理过程（仅在模型为r1时接受）使用‘/v3’切换至v3模型，使用‘/r1’切换至r1模型")
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

        if (words[0] != latest_word and
            re.search(re.escape("/ds"), words[0])):
            send_words("收到")
            logging.info(f"收到: {words[0]}")
            qes = words[0].replace("/ds", "")
            if re.search(re.escape("/reason"), words[0]):
                reason = True
                qes = qes.replace("/reason", "")
            ds_o = deepseek_api(qes, ds_model)
            time.sleep(5)
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
                interval=get_song(song_name, song_number)
                if interval:
                    with open("./1.mp3", "rb") as f:
                        upload_url = upload_voice(f, get_parentId(relation))
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
        time.sleep(1)
        get()


    except TypeError:

        words=get()
        continue

    except KeyboardInterrupt:

        exit(0)

    except:

        login()
        logging.info("崩溃重启")
        continue

