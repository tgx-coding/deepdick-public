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
import ddddocr as dd
from PIL import Image
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
            logging.info(f"下载url：{voice_url}")
            file=requests.get(voice_url)
            open("./1.mp3","wb").write(file.content)
            logging.info("下载完成")
            return
    except Exception as e:
        send_words("获取歌曲失败")
        logging.error(f"出现异常: {e}")
        return

def send_words(context,type=0):
    logging.info(f"发送信息: {context}")
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
            print(deresponse['msg'])
            raise CustomError('send failed')
        time_stemp = time.time()
    except Exception as e:
        logging.error(f"send_words() 出现异常: {e}")

def replace_non_bmp(text, replacement="(无法显示)"):
    return re.sub(r'[^\u0000-\uFFFF]', replacement, text)

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
        time.sleep(10)
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

