# -*- coding: utf-8 -*-
"""
generate_via_minimax.py - 调用 minimax music-3.0-free API 生成《走在》成品

读 .env:
  minimax_api_key=...
  default_minimax_muisc=music-3.0-free  # 默认 music-3.0-free

读 prompt_for_online_generator.md 第三节"完整歌词+控制标签"(Markdown fence 之间)
调用 API:
  POST https://api.minimaxi.com/v1/music_generation
  model=music-3.0-free
  prompt=<沙发小曲风格描述>
  lyrics=<完整歌词+标签>
  audio_setting={sample_rate:44100, bitrate:256000, format:mp3}
  output_format=url

下载 mp3 到 workspace/project/走在/song_engineer/ai-track/

错误处理:
  status_code != 0 抛异常
  HTTP 429 退避重试 3 次
  下载失败重试
"""
import os
import re
import sys
import json
import time
import shutil
import urllib.request
import urllib.error
import urllib.parse

# 读 .env(从当前目录往上找)
_env = {}
_cur = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    _c = os.path.join(_cur, ".env")
    if os.path.exists(_c):
        with open(_c, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                _env[k.strip()] = v.strip()
        break
    _cur = os.path.dirname(_cur)

API_KEY = _env.get("minimax_api_key", "")
MODEL = _env.get("default_minimax_muisc", "music-3.0-free").lower()
ENDPOINT = "https://api.minimaxi.com/v1/music_generation"
PROMPT_FILE = os.path.join("workspace", "project", "走在", "song_engineer", "prompt_for_online_generator.md")
OUT_DIR = os.path.join("workspace", "project", "走在", "song_engineer", "ai-track")

# 一段简洁的沙发小曲 prompt(放在 lyrics 之外,告诉模型风格/人声/配器)
STYLE_PROMPT = """Lo-Fi 沙发小曲 / 慵懒民谣,男声低输出呢喃,轻声细语,气声占比 40%+,真声为主,
木吉他分解和弦为主(Capodaster 3 品,实际音高 Eb),和弦 Cadd9/C7sus4/Em9/B/Em11/B/Cmaj9 沙发下行进行,
极淡合成器氛围垫音,男声合唱和声(三度平行,弱于主唱),
自然环境白噪音:前奏细雨声 + 间奏风声 + 尾奏远处日常声,
吉他 12 品自然泛音点缀,电贝斯轻低音跟根音,
BPM 68, Eb 大调, 4/4 拍, 约 3 分钟,
禁用:鼓组、重贝斯、电音、副歌爆发、情绪词外露"""


def extract_lyrics(prompt_md_path):
    """从 prompt_for_online_generator.md 第三节的 ``` ``` 围栏中提取歌词"""
    with open(prompt_md_path, encoding="utf-8") as f:
        md = f.read()
    # 找"三、完整歌词 + 控制标签"之后第一个代码块
    # 简化为:找所有 ``` 围栏,挑最长的那个
    blocks = re.findall(r"```([\s\S]*?)```", md)
    if not blocks:
        raise RuntimeError("prompt md 里没有 ``` 代码块")
    # 挑带 [Intro]/[Verse] 标签的最长块
    lyrics_block = max((b for b in blocks if "[Intro]" in b or "[Verse" in b),
                       key=len, default=None)
    if not lyrics_block:
        lyrics_block = max(blocks, key=len)
    # 去围栏标记
    lyrics = lyrics_block.strip()
    # 围栏内可能第一行是语言标记(如 ```text)
    if "\n" in lyrics and lyrics.split("\n", 1)[0].strip() in ("text", "json", ""):
        lyrics = lyrics.split("\n", 1)[1]
    return lyrics.strip()


def call_music_generation(prompt, lyrics, timeout=240):
    """调用 minimax music_generation API"""
    if not API_KEY:
        raise RuntimeError("minimax_api_key 未配置")

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "lyrics": lyrics,
        "output_format": "url",
        "audio_setting": {
            "sample_rate": 44100,
            "bitrate": 256000,
            "format": "mp3",
        },
        "aigc_watermark": False,
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw)
        except urllib.error.HTTPError as e:
            last_err = e
            body_text = e.read().decode("utf-8", errors="ignore")
            if e.code in (429, 503):  # 限流/服务暂不可用,重试
                wait = 30 * (attempt + 1)
                print(f"  [HTTP {e.code}] {body_text[:200]},等待 {wait}s 重试")
                time.sleep(wait)
                continue
            raise RuntimeError(f"HTTP {e.code}: {body_text}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            wait = 15 * (attempt + 1)
            print(f"  [网络错误] {e},等待 {wait}s 重试")
            time.sleep(wait)
            continue
    raise RuntimeError(f"API 调用失败(3 次重试用尽): {last_err}")


def download(url, dest):
    """下载 mp3 到目标路径(中文路径下用 urllib,可能 system error 改用 shutil)"""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False, dir=tempfile.gettempdir())
    tmp.close()
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            with open(tmp.name, "wb") as f:
                shutil.copyfileobj(resp, f)
        if os.path.exists(dest):
            os.remove(dest)
        shutil.copy(tmp.name, dest)
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)


def main():
    print(f"=== minimax music generation ===")
    print(f"model:     {MODEL}")
    print(f"endpoint:  {ENDPOINT}")
    print(f"prompt md: {PROMPT_FILE}")
    print()

    if not API_KEY:
        print("[错误] .env 中找不到 minimax_api_key")
        sys.exit(1)

    if not os.path.exists(PROMPT_FILE):
        print(f"[错误] 找不到 {PROMPT_FILE}")
        sys.exit(1)

    os.makedirs(OUT_DIR, exist_ok=True)

    # 提取歌词
    lyrics = extract_lyrics(PROMPT_FILE)
    print(f"歌词长度: {len(lyrics)} 字")
    print(f"歌词前 200 字: {lyrics[:200]}")
    print()

    # 调用 API
    print("正在调用 API(可能 1-3 分钟)...")
    t0 = time.time()
    resp = call_music_generation(STYLE_PROMPT, lyrics, timeout=300)
    dt = time.time() - t0

    print(f"\nAPI 响应(耗时 {dt:.1f}s):")
    print(json.dumps(resp, ensure_ascii=False, indent=2)[:2000])

    # 校验
    if "base_resp" in resp and resp["base_resp"].get("status_code", 0) != 0:
        raise RuntimeError(f"API 返回错误: {resp['base_resp']}")

    data = resp.get("data", {})
    status = data.get("status")
    if status == 1:
        print("[错误] 还在生成中(status=1),免费版同步模式应该返回 2")
        sys.exit(2)
    if status != 2:
        print(f"[警告] 未知 status={status},尝试找 audio 字段")

    # 提取 URL
    audio_url = data.get("audio") or data.get("audio_url")
    if not audio_url:
        raise RuntimeError(f"响应里没有 audio URL: {data}")

    extra = resp.get("extra_info", {})
    duration = extra.get("music_duration", "?")
    sample_rate = extra.get("music_sample_rate", "?")
    size = extra.get("music_size", "?")

    print(f"\n生成参数:")
    print(f"  时长:     {duration}s")
    print(f"  采样率:   {sample_rate}")
    print(f"  大小:     {size}")
    print(f"  URL:      {audio_url[:120]}...")

    # 下载
    fn = f"走在_minimax_{MODEL}.mp3"
    out = os.path.join(OUT_DIR, fn)
    print(f"\n正在下载到 {out} ...")
    download(audio_url, out)
    sz = os.path.getsize(out)
    print(f"下载完成: {sz/1024/1024:.2f} MB")
    print(f"\n[成品] {out}")


if __name__ == "__main__":
    main()