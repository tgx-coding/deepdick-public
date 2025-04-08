# -*- coding: utf-8 -*-
import os
import re
import time
import logging
import requests
import markdown
import html2text
import ddddocr as dd
from PIL import Image
from openai import OpenAI
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
#import pymysql as mysql

os.environ['TZ'] = 'Asia/Shanghai'
time.tzset()

os.makedirs(f"./logs/{os.getenv("username")}", exist_ok=True)  # 确保 logs 文件夹存在

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
retry_times = 0
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



# 创建 Chrome driver 的函数
def create_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument("--window-size=428,926")
    service = Service()
    driver_instance = webdriver.Chrome(service=service, options=options)
    return driver_instance

# 初始化全局 driver 和 WebDriverWait 对象
driver = create_driver()
wait = WebDriverWait(driver, 20, 0.1)  # 修改等待时间为20秒

def markdown_to_text(markdown_text):
    # 将 Markdown 转换为 HTML，再转换为纯文本
    html_content = markdown.markdown(markdown_text)
    text_maker = html2text.HTML2Text()
    text_maker.ignore_links = True
    text_maker.ignore_images = True
    text_maker.ignore_emphasis = True
    plain_text = text_maker.handle(html_content)
    return plain_text

def get():
    global times
    times += 1
    if times >= 10:
        exit(-1)
    try:
        words = driver.find_elements(By.CLASS_NAME, "pd-t-10")
        if words:
            if words[-1] is not None:
                times = 0
                logging.info(f"获取信息: {words[-1].text}")
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

def send_words(context):
    logging.info(f"发送信息: {context}")
    try:
        input_place = driver.find_element(By.XPATH, "//input")
        send_button = driver.find_element(By.XPATH, "//button")
        context = markdown_to_text(context)
        context = replace_non_bmp(context)
        if len(context) >= 160:
            # 分段发送
            words_to_spare = [context[i:i + 150] for i in range(0, len(context), 160)]
            for segment in words_to_spare:
                input_place.send_keys(segment)
                send_button.click()
                time.sleep(10)
        else:
            input_place.send_keys(context)
            send_button.click()
            time.sleep(5)
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
    global driver, wait, retry_times
    if retry_times >= 10:
        exit(-1)
    try:
        driver.get('https://wxapp.nhedu.net/edu-base/mobile/#/edu-base-login')
        driver.maximize_window()
        # 账号密码输入
        driver.find_element(By.NAME, "username").send_keys(secret[0])
        driver.find_element(By.NAME, "password").send_keys(secret[1])
        element = driver.find_element(By.ID, "account")
        # 截图验证码区域
        driver.execute_script("arguments[0].scrollIntoView();", element)
        driver.get_screenshot_as_file('screenshot.png')
        left = int(element.location['x'])
        top = int(element.location['y'])
        right = left + int(element.size['width'])
        bottom = top + int(element.size['height'])
        im = Image.open('screenshot.png')
        im.crop((left, top, right, bottom)).save('code.png')
        # OCR 验证码识别
        ocr = dd.DdddOcr()
        with open("code.png", "rb") as img_file:
            image = img_file.read()
        result = ocr.classification(image)

        element = driver.find_element(By.NAME, "captcha")
        element.send_keys(result)
        # 点击留言版按钮
        element = driver.find_element(By.CLASS_NAME, "van-button")
        element.click()
        time.sleep(15)
        # 定位首页的目标入口
        element = driver.find_element(By.XPATH, "//div[contains(text(), '智慧班牌留言板')]")
        driver.execute_script("arguments[0].scrollIntoView();", element)
        element.click()
        time.sleep(2)
        # 选择“我是本人”
        driver.find_element(By.XPATH, f"//p[contains(text(), '我是{os.getenv("parents_name")}')]").click()
        retry_times = 0
    except KeyboardInterrupt:
        exit(0)
    except Exception as e:
        logging.error(f"login() 出现异常: {e}")
        try:
            driver.quit()
        except Exception:
            pass
        retry_times += 1
        # 重新创建 driver 实例以确保会话正常
        global wait
        driver = create_driver()
        wait = WebDriverWait(driver, 20, 0.1)  # Update wait time here as well
        login()

# 登录操作
login()
print("成功登录")
logging.info("成功登录")
time.sleep(10)
send_words("成功登录 请使用‘/ds’进行提问,使用‘/ds (内容)/reason’输出推理过程（仅在模型为r1时接受）使用‘/v3’切换至v3模型，使用‘/r1’切换至r1模型")
time.sleep(2)
times = 0
words = get()
times = 0
daiji = False
latest_word = words[-1].text

# 主循环：检测新信息并调用 API 返回回复
while True:
    try:
        if time.time() - time_stemp >= 300:
            daiji = True
        words = get()
        if words[-1].text == "/v3":
            ds_model = "deepseek-chat"
            send_words("//已切换至v3")
            logging.info("已切换至v3")
            time.sleep(5)
            words = get()
            latest_word = words[-1].text
        elif words[-1].text == "/r1":
            ds_model = "deepseek-reasoner"
            send_words("//已切换至r1")
            logging.info("已切换至r1")
            time.sleep(5)
            words = get()
            latest_word = words[-1].text
        elif words[-1].text == "stops":
            send_words("已停止")
            logging.info("已停止")
            exit(0)
        elif words[-1].text == "待机" or daiji:
            send_words("正在待机")
            logging.info("正在待机")
            time.sleep(5)
            words = get()
            latest_word = words[-1].text
            while True:
                get()
                time.sleep(180)
                #time.sleep(10)
                driver.refresh()
                time.sleep(10)
                driver.find_element(By.XPATH, f"//p[contains(text(), '我是{os.getenv("parents_name")}')]").click()
                time.sleep(5)
                words = get()
                if words[-1].text != latest_word and words[-1].text != "正在待机":
                    daiji = False
                    time.sleep(5)
                    words = get()
                    time_stemp = time.time()
                    break
        elif words[-1].text == "余额":
            send_words(blance())
            time.sleep(5)
            words = get()
            latest_word = words[-1].text

        if (words[-1].text != latest_word and
            re.search(re.escape("/ds"), words[-1].text)):
            send_words("收到")
            logging.info(f"收到: {words[-1].text}")
            print(words[-1].text)
            qes = words[-1].text.replace("/ds", "")
            if re.search(re.escape("/reason"), words[-1].text):
                reason = True
                qes = qes.replace("/reason", "")
            ds_o = deepseek_api(qes, ds_model)
            time.sleep(5)
            send_words("回答完毕")
            time.sleep(8)
            words = get()
            latest_word = words[-1].text
            time_stemp = time.time()
        time.sleep(10)
        driver.refresh()
        time.sleep(5)
        driver.find_element(By.XPATH, f"//p[contains(text(), '我是{os.getenv("parents_name")}')]").click()
        time.sleep(5)


    except TypeError:

        time.sleep(10)

        driver.refresh()

        time.sleep(5)

        element = driver.find_element(By.XPATH, f"//p[contains(text(), '我是{os.getenv("parents_name")}')]")

        element.click()

        time.sleep(5)

        continue

    except KeyboardInterrupt:

        exit(0)

    except:

        driver.quit()
        create_driver()
        login()
        logging.info("崩溃重启")
        continue

