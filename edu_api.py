import json
import logging
import time

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
    result = json.loads(response.content)
    for item in result.get("result", []):
        if item.get("relation") == relation:
            logging.info(f"获取家长id：{item['parentId']}")
            return item.get("parentId")
    return None


def upload_voice(in_file, parentId,
                 time_label=time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime()),
                 max_retries: int = 3,
                 chunk_size: int = 256 * 1024):
    _ensure_session()
    filename = f"{parentId}_{phoneNumber}_{time_label}.wav"
    fields = {
        'parentId': str(parentId),
        'mobile': str(phoneNumber),
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
    headers['Content-Type'] = monitor.content_type

    logging.info("正在上传")
    deresponse = None
    try:
        response = session.post(
            'https://wxapp.nhedu.net/edu-iot/be/ym-message//upload-voice',
            headers=headers,
            data=monitor,
            timeout=180,
        )
        deresponse = json.loads(response.content)
        if deresponse.get('msg') != 'success':
            raise RuntimeError('UPLOAD failed')
        upload_file_url = deresponse.get("result")
        logging.info("成功")
        return upload_file_url
    except Exception as exc:  # pragma: no cover - network heavy
        logging.error(f"上传失败: {exc}")
        if deresponse is not None:
            logging.error(deresponse)
        if send_words:
            send_words("请重试")
        return None
