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

def get_song(name=None,id=None, choose=1, quality="standard", retry_times=0, output_path="./1.mp3",song_id_list=[]) -> Optional[int]:
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
VOICE_ID3_HEADROOM = 4096     # 为容器头/ID3 标签预留的字节
OPUS_MIN_BITRATE = 6000       # Opus 单声道官方最低码率(bps)

# MP3 码率阶梯(高到低,低码率档位越细,越能保住整首)
_MP3_RATE_LADDER = (64000, 48000, 40000, 32000, 24000, 20000,
                    16000, 12000, 8000)


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


def _export(song: AudioSegment, out_path: str, fmt: str,
            sample_rate: int, bitrate: int) -> int:
    """按给定参数编码并返回文件大小。"""
    piece = song.set_frame_rate(sample_rate)
    if fmt == "mp3":
        piece.export(out_path, format="mp3", bitrate=f"{bitrate // 1000}k")
    else:  # opus
        piece.export(out_path, format="opus", parameters=["-b:a", str(bitrate)])
    return os.path.getsize(out_path)


def compress_song_to_limit(file_path: str, out_path: str, max_bytes=None) -> int:
    """把整首歌压缩到 max_bytes 以内,返回最终文件字节数。

    策略(优先完整保留整首,只降质量,最后手段才裁尾):
      1. 解码 MP3 -> 单声道;
      2. 按"体积预算 / 时长"估算所需码率,从 MP3 阶梯中选取起始档位,
         逐级下调(采样率同步 16kHz/8kHz),能放下即整首无损时长;
      3. MP3 最低 8kbps 仍放不下时,改用 Opus 6kbps(整首可覆盖约 3.3 分钟);
      4. Opus 6kbps 也放不下时,才裁掉结尾到刚好放下的长度;
      5. 无 ffmpeg 时退化为字节截断兜底(见 _truncate_mp3_raw)。

    注意:输出文件实际是低码率 MP3/Opus 内容(扩展名保持兼容,服务端不校验格式)。
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
    budget = max_bytes - VOICE_ID3_HEADROOM
    # 放得下整首所需的最低码率(bps)
    req_rate = budget * 8 / duration_s

    # ---- 1) MP3 阶梯:码率逐级下调,全程不裁时长 ----
    if req_rate >= VOICE_MIN_BITRATE:
        # 阶梯中第一个不超过所需码率的档位(避免从过高码率白白多试)
        start = next(i for i, r in enumerate(_MP3_RATE_LADDER) if r <= req_rate)
        last_size = None
        for bitrate in _MP3_RATE_LADDER[start:]:
            sample_rate = 16000 if bitrate >= 20000 else 8000
            last_size = _export(song, out_path, "mp3", sample_rate, bitrate)
            if last_size <= max_bytes:
                logging.info(
                    f"整首歌压缩完成: {duration_s:.0f}s 歌曲 -> {last_size}B "
                    f"@{bitrate // 1000}kbps {sample_rate}Hz(未截断)"
                )
                return last_size
            logging.info(
                f"MP3 {bitrate // 1000}kbps 得 {last_size}B 仍超 {max_bytes}B,继续降码率"
            )
        logging.warning(f"MP3 8kbps 仍超限({last_size}B),改用 Opus 极限码率")

    # ---- 2) Opus 6kbps 整首(物理极限:约 3.3 分钟) ----
    last_size = _export(song, out_path, "opus", 8000, OPUS_MIN_BITRATE)
    if last_size <= max_bytes:
        logging.info(
            f"整首歌 Opus 压缩完成: {duration_s:.0f}s 歌曲 -> {last_size}B "
            f"@{OPUS_MIN_BITRATE // 1000}kbps 8000Hz(未截断)"
        )
        return last_size
    logging.warning(
        f"Opus 6kbps 得 {last_size}B 仍超 {max_bytes}B,开始裁掉结尾"
    )

    # ---- 3) 最后手段:裁尾(只裁到刚好放下) ----
    # budget*8/bitrate = 可容纳秒数,×0.96 对冲容器开销,×1000 转毫秒
    keep_ms = int(budget * 8 / OPUS_MIN_BITRATE * 0.96 * 1000)
    for _ in range(8):
        piece = song[:keep_ms]
        last_size = _export(piece, out_path, "opus", 8000, OPUS_MIN_BITRATE)
        if last_size <= max_bytes:
            logging.warning(
                f"歌曲过长({duration_s:.0f}s),保留前 {keep_ms / 1000:.0f}s "
                f"(Opus {OPUS_MIN_BITRATE // 1000}kbps,裁掉 "
                f"{(duration_ms - keep_ms) / 1000:.0f}s)"
            )
            return last_size
        # 按实际超出比例收缩,收敛快且不多裁
        keep_ms = int(keep_ms * (max_bytes - VOICE_ID3_HEADROOM) / last_size * 0.98)
        if keep_ms < 1000:
            break

    raise RuntimeError(f"压缩失败: 最低码率下仍无法压到 {max_bytes}B")


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
