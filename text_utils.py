import markdown
import html2text
import re
from typing import Optional, Tuple


def markdown_to_text(markdown_text: str) -> str:
    """Convert Markdown content to a plain-text representation."""
    html_content = markdown.markdown(markdown_text)
    text_maker = html2text.HTML2Text()
    text_maker.ignore_links = True
    text_maker.ignore_images = True
    text_maker.ignore_emphasis = True
    return text_maker.handle(html_content)


def replace_non_bmp(text: str, replacement: str = "(无法显示)") -> str:
    """Replace characters outside the BMP range to avoid encoding issues."""
    return re.sub(r"[^\u0000-\uFFFF]", replacement, text)


def time_to_seconds(time_str: str) -> int:
    """Convert strings like '5分30秒' into seconds."""
    minutes = 0
    seconds = 0
    if "分" in time_str:
        parts = time_str.split("分")
        if parts[0]:
            minutes = int(parts[0])
        if len(parts) > 1 and parts[1] and "秒" in parts[1]:
            seconds_str = parts[1].replace("秒", "")
            if seconds_str:
                seconds = int(seconds_str)
    elif "秒" in time_str:
        seconds_str = time_str.replace("秒", "")
        if seconds_str:
            seconds = int(seconds_str)
    return minutes * 60 + seconds


_DIGIT_MAP = {
    "零": 0,
    "〇": 0,
    "○": 0,
    "一": 1,
    "壹": 1,
    "二": 2,
    "两": 2,
    "贰": 2,
    "三": 3,
    "叁": 3,
    "四": 4,
    "肆": 4,
    "五": 5,
    "伍": 5,
    "六": 6,
    "陆": 6,
    "七": 7,
    "柒": 7,
    "八": 8,
    "捌": 8,
    "九": 9,
    "玖": 9,
}

_UNIT_MAP = {
    "十": 10,
    "拾": 10,
    "百": 100,
    "佰": 100,
    "千": 1000,
    "仟": 1000,
    "万": 10000,
}


def chinese_numeral_to_int(text: str) -> Optional[int]:
    """Convert common Chinese numerals to integers."""
    if not text:
        return None
    text = text.strip()
    total = 0
    current = 0
    for char in text:
        if char in _DIGIT_MAP:
            current = _DIGIT_MAP[char]
        elif char in _UNIT_MAP:
            unit_value = _UNIT_MAP[char]
            if unit_value == 10000:
                total = (total + current) * unit_value
                current = 0
            else:
                if current == 0:
                    current = 1
                total += current * unit_value
                current = 0
        elif char.isdigit():
            return None
        else:
            return None
    total += current
    return total if total else None


def parse_song_request(text: str) -> Tuple[Optional[str], Optional[int]]:
    """Parse commands like '/点歌XXX第XX首' into song name and index."""
    pattern = r"/点歌(.+?)第([\d一二三四五六七八九十百千万零两壹贰叁肆伍陆柒捌玖拾佰仟万〇○]+)首"
    match = re.search(pattern, text)
    if not match:
        return None, None
    song_name = match.group(1)
    song_number_raw = match.group(2)
    try:
        song_number = int(song_number_raw)
    except ValueError:
        song_number = chinese_numeral_to_int(song_number_raw)
    return (song_name, song_number) if song_number else (None, None)

def parse_playlist_index(command):
    pattern_alt = r"/歌单第([\d一二三四五六七八九十百千万零两壹贰叁肆伍陆柒捌玖拾佰仟万〇○]+)首"
    match = re.search(pattern_alt, command)
    if not match:
        return None
    index_raw = match.group(1)
    try:
        return int(index_raw)
    except ValueError:
        return chinese_numeral_to_int(index_raw)