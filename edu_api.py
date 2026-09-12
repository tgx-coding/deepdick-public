import json
import logging
import time
import random

from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

# These globals are populated from main.py after import.
session = None
token = None
phoneNumber = None
send_words = None
timestemp = None


def _ensure_session():
    if session is None:
        raise RuntimeError("edu_api.session is not configured")


def get_parentId(relation):
    _ensure_session()
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
    try:
        result = json.loads(response.content)
    except ValueError:
        logging.error(f"parents 接口返回非 JSON(HTTP {response.status_code}),无法获取家长id")
        return None
    for item in result.get("result", []):
        if item.get("relation") == relation:
            logging.info(f"获取家长id：{item['parentId']}")
            return item.get("parentId")
    return None


def _do_upload(in_file, parentId, time_label, max_retries):
    """执行上传,返回 (url, reason);reason 为 None 表示成功。

    失败原因标识:
      'network'     请求异常(超时/连接错误)
      'http_XXX'    HTTP 状态码非 200(如 500 的 nginx 错误页)
      'empty_body'  HTTP 200 但响应体为空
      'non_json'    HTTP 200 但响应体不是 JSON
      'api_error'   接口返回 msg != success
      'no_url'      返回成功但缺少 result 字段
    """
    _ensure_session()
    filename = f"{random.randint(1000, 9999)}_{parentId}_{phoneNumber or ''}_{time_label}.wav"
    fields = {
        'file': (filename, in_file, 'application/octet-stream')
    }

    if hasattr(in_file, "seek"):
        in_file.seek(0)

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
    headers['Content-Type'] = encoder.content_type

    reason = 'unknown'
    for attempt in range(1, max_retries + 1):
        if hasattr(in_file, "seek"):
            in_file.seek(0)
        progress_state = {'last_percent': -1}

        def make_callback(total_length):
            def _callback(monitor):
                if not total_length:
                    return
                percent = int(monitor.bytes_read * 100 / total_length)
                if percent > progress_state['last_percent']:
                    progress_state['last_percent'] = percent
                    logging.info(f"上传进度：{percent}% ({monitor.bytes_read}/{total_length} bytes)")
            return _callback

        monitor = MultipartEncoderMonitor(encoder, make_callback(encoder.len))
        logging.info(f"正在上传(第 {attempt}/{max_retries} 次)")

        try:
            response = session.post(
                'https://wxapp.nhedu.net/edu-iot/be/ym-message//upload-voice',
                headers=headers,
                data=monitor,
                timeout=180,
            )
        except Exception as exc:  # pragma: no cover - network heavy
            reason = 'network'
            logging.error(f"上传请求异常(第 {attempt}/{max_retries} 次): {exc}")
            if attempt < max_retries:
                time.sleep(2 * attempt)
                continue
            break

        if response.status_code != 200:
            # 500 时响应体是 nginx 错误页(HTML),只需记录前 120 字节
            reason = f'http_{response.status_code}'
            logging.error(
                f"上传失败(第 {attempt}/{max_retries} 次): HTTP {response.status_code}, "
                f"响应: {response.content[:120]!r}"
            )
            if attempt < max_retries:
                time.sleep(2 * attempt)
                continue
            break

        if not response.content:
            # HTTP 200 但响应体为空,同样视为失败
            reason = 'empty_body'
            logging.error(f"上传响应体为空(第 {attempt}/{max_retries} 次): HTTP 200")
            if attempt < max_retries:
                time.sleep(2 * attempt)
                continue
            break

        try:
            deresponse = json.loads(response.content)
        except ValueError:
            reason = 'non_json'
            logging.error(
                f"上传响应非 JSON(第 {attempt}/{max_retries} 次): {response.content[:120]!r}"
            )
            if attempt < max_retries:
                time.sleep(2 * attempt)
                continue
            break

        if deresponse.get('msg') != 'success':
            reason = 'api_error'
            logging.error(f"上传返回失败(第 {attempt}/{max_retries} 次): {deresponse}")
            if attempt < max_retries:
                time.sleep(2 * attempt)
                continue
            break

        upload_file_url = deresponse.get("result")
        if not upload_file_url:
            reason = 'no_url'
            logging.error(f"上传响应缺少 result(第 {attempt}/{max_retries} 次): {deresponse}")
            if attempt < max_retries:
                time.sleep(2 * attempt)
                continue
            break

        logging.info(f"上传成功: {upload_file_url}")
        return upload_file_url, None

    logging.error(f"上传最终失败: 原因={reason}")
    return None, reason


def upload_voice(in_file, parentId=114514,
                 time_label=time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime()),
                 max_retries: int = 3):
    """上传语音文件,失败自动重试;成功返回 url,失败返回 None 并提示用户。

    服务端体积上限会变化:2026-08 实测 >163.7KB 必然 500,
    2026-09 复测 3.4MB 原曲已能正常上传。因此调用方宜优先尝试完整原曲,
    失败再回退压缩上传(见 main.upload_song_with_fallback)。
    """
    url, reason = _do_upload(in_file, parentId, time_label, max_retries)
    if not url and send_words:
        send_words("请重试")
    return url


def upload_voice_probe(in_file, parentId=114514,
                       time_label=time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime()),
                       max_retries: int = 1):
    """探测式上传:返回 (url, reason),不向用户发失败提示。

    供"先试完整原曲、失败再回退压缩"的流程使用(见 main.upload_song_with_fallback)。
    reason 取值见 _do_upload 的说明。
    """
    return _do_upload(in_file, parentId, time_label, max_retries)
