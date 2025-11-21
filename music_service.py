import json
import logging
from typing import Optional

from pydub import AudioSegment

from text_utils import time_to_seconds

# These globals are set from main.py after import to avoid circular imports.
session = None
send_words = None


def _ensure_session() -> None:
    if session is None:
        raise RuntimeError("music_service.session is not configured")


def get_voice_list(name, from_where=1, retry_times=0):
    _ensure_session()
    try:
        logging.info(f"查询歌曲:{name}")
        if retry_times >= 10:
            raise RuntimeError("get voice list failed")
        response = session.get(f"https://api.vkeys.cn/v2/music/netease?word={name}")
        voice_list = json.loads(response.content)
        if voice_list["code"] != 200:
            retry_times += 1
            logging.info(f"获取歌曲列表重试次数：{retry_times}")
            return get_voice_list(name, from_where, retry_times)
        de_voice_list = []
        for item in voice_list["data"]:
            de_voice_list.append(f"{item['song']}---{item['singer']}")
        return de_voice_list
    except Exception as exc:  # pragma: no cover - network heavy
        if from_where and send_words:
            send_words("获取失败")
        logging.error(f"出现异常: {exc}")
        return []


def get_song(name, choose=1, quality=4, retry_times=0, output_path="./1.mp3") -> Optional[int]:
    _ensure_session()
    try:
        response = session.get(
            f"https://api.vkeys.cn/v2/music/netease?word={name}&choose={choose}&quality={quality}"
        )
        voice = json.loads(response.content)
        if voice["code"] != 200:
            if retry_times >= 10:
                raise RuntimeError("get voice file failed")
            retry_times += 1
            logging.info(f"重试获取歌曲次数：{retry_times}")
            return get_song(name, choose, quality, retry_times, output_path)
        voice_url = voice["data"]["url"]
        interval = time_to_seconds(voice["data"]["interval"])
        logging.info(f"下载url：{voice_url}")
        file_resp = session.get(voice_url)
        logging.info("下载完成")
        with open(output_path, "wb") as file_obj:
            file_obj.write(file_resp.content)
        return interval
    except Exception as exc:  # pragma: no cover - network heavy
        if send_words:
            send_words("获取歌曲失败")
        logging.error(f"出现异常: {exc}")
        return None


def mp3_to_wav(file_path="./1.mp3", wav_path="1.wav"):
    song = AudioSegment.from_mp3(file_path)
    song.export(wav_path, format="wav")
