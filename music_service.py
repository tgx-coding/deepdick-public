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
            singer=""
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


# ===== 上传音频体积控制 =====
# 服务端上传接口实测:请求体约 163.7KB 以内稳定成功,>=400KB 必然 500。
# 这里默认限制在 150KB,留出安全余量。
VOICE_MAX_BYTES = int(os.getenv("VOICE_MAX_BYTES", str(150 * 1024)))
VOICE_MIN_BITRATE = 8000      # LAME 支持的最低码率(bps)
VOICE_MAX_BITRATE = 64000     # 16kHz 采样下 MP3 可用的较高码率
VOICE_ID3_HEADROOM = 4096     # 为 MP3 容器头/ID3 标签预留的字节


def _truncate_mp3_raw(file_path: str, out_path: str, max_bytes: int) -> int:
    """无 ffmpeg 时的兜底方案:直接截取 MP3 前 max_bytes 字节。

    字节截断无法压缩整首歌,只能保留开头片段。
    服务端只对体积敏感,并不校验真实音频格式,截取的 MP3 片段也能上传成功。
    """
    file_size = os.path.getsize(file_path)
    keep = min(file_size, max_bytes)
    with open(file_path, "rb") as src, open(out_path, "wb") as dst:
        dst.write(src.read(keep))
    logging.warning(
        f"未检测到 ffmpeg,已退回字节截断:原文件 {file_size}B -> 截取 {keep}B"
        f"(无法压缩整首歌,请安装 ffmpeg 后重试)"
    )
    return keep


def compress_song_to_limit(file_path: str, out_path: str, max_bytes=None) -> int:
    """把整首歌压缩到 max_bytes 以内,返回最终文件字节数。

    策略(整首歌完整保留,只降质量):
      1. 解码 MP3 -> 单声道;
      2. 按"体积预算 / 时长"估算码率,从 64kbps 起逐级下调
         (采样率同步降到 16kHz / 8kHz),每次编码后实测文件大小;
      3. 已到 LAME 最低码率 8kbps 仍超限时(歌曲时长 > 约 2.5 分钟),
         只能按比例裁掉结尾,保证文件达标;
      4. 无 ffmpeg 时退化为字节截断兜底(见 _truncate_mp3_raw)。

    注意:输出文件实际是低码率 MP3 内容(扩展名保持兼容,服务端不校验格式)。
    """
    max_bytes = max_bytes or VOICE_MAX_BYTES
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"音频文件不存在: {file_path}")

    # ---- 解码(需要 ffmpeg / ffprobe) ----
    try:
        song = AudioSegment.from_mp3(file_path)
    except FileNotFoundError as exc:
        # pydub 找不到 ffprobe/ffmpeg 时抛出 FileNotFoundError
        if "ffprobe" in str(exc) or "ffmpeg" in str(exc):
            return _truncate_mp3_raw(file_path, out_path, max_bytes)
        raise
    except Exception as exc:
        # MP3 损坏等其他解码异常也走字节截断兜底,保证功能可用
        logging.warning(f"MP3 解码失败({exc}),退回字节截断")
        return _truncate_mp3_raw(file_path, out_path, max_bytes)

    song = song.set_channels(1)
    duration_ms = len(song)
    duration_s = duration_ms / 1000.0

    # ---- 估算起始码率 ----
    budget = max_bytes - VOICE_ID3_HEADROOM
    bitrate = int(budget * 8 / duration_s)
    bitrate = max(VOICE_MIN_BITRATE, min(bitrate, VOICE_MAX_BITRATE))
    bitrate = max(VOICE_MIN_BITRATE, bitrate // 8000 * 8000)  # 对齐 LAME 支持的档位

    trim_ms = 0
    last_size = None
    for _ in range(24):
        piece = song if not trim_ms else song[:duration_ms - trim_ms]
        # 低码率配低采样率:16kbps 以下用 8kHz,否则 16kHz
        sample_rate = 8000 if bitrate <= 16000 else 16000
        piece = piece.set_frame_rate(sample_rate)
        piece.export(out_path, format="mp3", bitrate=f"{bitrate // 1000}k")
        last_size = os.path.getsize(out_path)

        if last_size <= max_bytes:
            cut_note = f",裁掉结尾 {trim_ms / 1000:.1f}s" if trim_ms else ""
            logging.info(
                f"整首歌压缩完成: {duration_s:.0f}s 歌曲 -> {last_size}B "
                f"@{bitrate // 1000}kbps {sample_rate}Hz{cut_note}"
            )
            return last_size

        if bitrate > VOICE_MIN_BITRATE:
            # 仍超限:下调码率(约 15% 一档)重试
            bitrate = max(VOICE_MIN_BITRATE, int(bitrate * 0.85) // 8000 * 8000)
            logging.info(f"压缩后 {last_size}B 仍超 {max_bytes}B,码率降至 {bitrate // 1000}kbps")
            continue

        # 最低码率仍超限:按超出比例裁掉结尾
        cut_ratio = min(0.5, (last_size - max_bytes) / max_bytes + 0.03)
        new_trim = trim_ms + int(duration_ms * cut_ratio)
        if new_trim >= duration_ms - 500:
            raise RuntimeError(f"压缩失败: 最低码率下仍无法压到 {max_bytes}B")
        trim_ms = new_trim
        logging.warning(
            f"最低码率仍超限({last_size}B > {max_bytes}B),"
            f"裁掉结尾 {trim_ms / 1000:.1f}s 重试"
        )

    raise RuntimeError(f"压缩失败: 迭代次数超限(最后大小 {last_size}B)")


def mp3_to_wav(file_path="./1.mp3", wav_path="1.wav"):
    """兼容旧调用入口:整首歌压缩到体积上限,输出仍写在 wav_path。

    输出文件实际为低码率 MP3 内容,扩展名仅保持兼容(服务端不校验格式)。
    """
    return compress_song_to_limit(file_path, wav_path)

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
