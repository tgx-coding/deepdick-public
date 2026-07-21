import json
import logging
import os
from typing import Optional

from pydub import AudioSegment

from text_utils import time_to_seconds

# These globals are set from main.py after import to avoid circular imports.
session = None
send_words = None

cloud_music_api=os.getenv("cloud_music_api")
cloud_music_cookie=os.getenv("cloud_music_cookie")

logging.info(f"cloud_music_api: {cloud_music_api}")
logging.info(f"cloud_music_cookie: {cloud_music_cookie}")


def _ensure_session() -> None:
    if session is None:
        raise RuntimeError("music_service.session is not configured")


def get_voice_list(name, from_where=1, retry_times=0):
    _ensure_session()
    try:
        logging.info(f"查询歌曲:{name}")
        if int(retry_times) >= 10:
            raise RuntimeError("get voice list failed")
        response = session.get(f"{cloud_music_api}/cloudsearch?keywords={name}")
        voice_list = json.loads(response.content)
        if voice_list["code"] != 200:
            retry_times += 1
            logging.info(f"获取歌曲列表重试次数：{retry_times}")
            return get_voice_list(name, from_where, retry_times)
        de_voice_list = []
        singer=""
        song_id=[]
        for item in voice_list["result"]["songs"]:
            song_id.append(item["id"])
            for singer_name in item["ar"]:
                singer+=singer_name["name"]+", "
            de_voice_list.append(f"{item['name']}---{singer[:-2]}")
        return de_voice_list, song_id
    except Exception as exc:  # pragma: no cover - network heavy
        if from_where and send_words:
            send_words("获取失败")
        logging.error(f"出现异常: {exc}")
        return [], []

def get_song(name=None,id=None, choose=1, quality="exhigh", retry_times=0, output_path="./1.mp3",song_id_list=[]) -> Optional[int]:
    _ensure_session()
    try:
        try:
            if id is None:
                if song_id_list:
                    id=song_id_list[choose-1]
                else:
                    song_list, song_id_list = get_voice_list(name)
                    if not song_id_list:
                        raise RuntimeError("get song id failed")
                    id = song_id_list[choose - 1]
        except IndexError:
            send_words("选择的歌曲超出范围，请重新选择")
            logging.error("选择的歌曲超出范围，请重新选择")
            return None
            
        params = {
  'id': id,
  'level': quality,
  'cookie': cloud_music_cookie
}

        if id is not None:
            response = session.get(
            f"{cloud_music_api}/song/url/v1",
            params=params
        )
        else:
            raise RuntimeError("song id is None")
        voice = json.loads(response.content)
        if voice["code"] != 200:
            logging.info(voice['code'])
            if int(retry_times) >= 10:
                raise RuntimeError("get voice file failed")
            retry_times += 1
            logging.info(f"重试获取歌曲次数：{retry_times}")
            return get_song(name,id, choose, quality, retry_times, output_path)
        voice_url = voice["data"][0]["url"]
        interval = time_to_seconds("3分40秒")#这里以前有用，现在没用了
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

def get_personal_song_list(id):
    try:
        headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0',
    }
        response=session.get(f"{cloud_music_api}/playlist/track/all?id={id}",headers=headers)
        lists=json.loads(response.content)
        if lists["code"]!=200:
            raise RuntimeError("get song list failed")
        song_list={}
        for i in lists["songs"]:
            song_list[i["name"]]=i["id"]
        if song_list:
            send_words("获取歌单成功")
        else:
            send_words("歌单为空,或获取失败")
        return song_list
    except Exception as e:
        if send_words:
            send_words("获取歌单失败")
        logging.error(f"出现异常: {e}")

def send_personal_song_list(song_list):
    try:
        count=1
        temp=""
        for i in song_list:
            temp+=(f"{count}--{i}\n")
            count += 1
            if count%10==0:
                send_words(temp)
                temp=""
        if temp:
            send_words(temp)
            temp=""
    except Exception as e:
        if send_words:
            send_words("发送歌单失败")
        logging.error(f"出现异常: {e}")
