# -*- coding: utf-8 -*-
"""
cover_generate.py - 用 cover_feature_id 调 music-cover-free 生成新版本

读 cover_preprocess.json 拿 cover_feature_id
读 主唱.prompt.md + lyrics.md
调 music_generation model=music-cover-free
下载 mp3 到 ai-track/
"""
import os
import sys
import json
import time
import shutil
import tempfile
import urllib.request
import urllib.error

# 读 .env
_env = {}
_cur = os.getcwd()
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
ENDPOINT = "https://api.minimaxi.com/v1/music_generation"
PREP_JSON = "workspace/project/走在/song_engineer/ai-track/cover_preprocess.json"
PROMPT = "workspace/project/走在/song_engineer/ai-track/主唱.prompt.md"
LYRICS = "workspace/project/走在/song_engineer/ai-track/lyrics.md"
OUT_DIR = "workspace/project/走在/song_engineer/ai-track"


def call(body, timeout=400):
    if not API_KEY:
        raise RuntimeError("minimax_api_key 未配置")
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=raw,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            body_text = e.read().decode("utf-8", errors="ignore")
            if e.code in (429, 503):
                wait = 30 * (attempt + 1)
                print(f"  [HTTP {e.code}] wait {wait}s")
                time.sleep(wait)
                continue
            raise RuntimeError(f"HTTP {e.code}: {body_text}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            wait = 15 * (attempt + 1)
            print(f"  [网络错误] wait {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"API 失败: {last}")


def download(url, dest):
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
    if not os.path.exists(PREP_JSON):
        print(f"[错误] 缺 {PREP_JSON},先跑 cover_preprocess.py")
        sys.exit(1)
    if not API_KEY:
        print("[错误] .env 缺 minimax_api_key")
        sys.exit(1)

    prep = json.load(open(PREP_JSON, encoding="utf-8"))
    fid = prep.get("cover_feature_id")
    if not fid:
        print(f"[错误] {PREP_JSON} 里没 cover_feature_id")
        sys.exit(1)

    prompt_text = open(PROMPT, encoding="utf-8").read().strip()
    lyrics_text = open(LYRICS, encoding="utf-8").read().strip()

    print(f"=== music-cover-free generation ===")
    print(f"cover_feature_id: {fid}")
    print(f"prompt chars:     {len(prompt_text)}")
    print(f"lyrics chars:     {len(lyrics_text)}")

    body = {
        "model": "music-cover-free",
        "prompt": prompt_text,
        "lyrics": lyrics_text,
        "cover_feature_id": fid,
        "output_format": "url",
        "audio_setting": {
            "sample_rate": 44100,
            "bitrate": 256000,
            "format": "mp3"
        },
        "aigc_watermark": False,
    }

    print("\n调 API (预计 2-3 分钟)...")
    t0 = time.time()
    resp = call(body, timeout=400)
    dt = time.time() - t0
    print(f"\n响应(耗时 {dt:.1f}s):")
    print(json.dumps(resp, ensure_ascii=False, indent=2)[:1500])

    if "base_resp" in resp and resp["base_resp"].get("status_code", 0) != 0:
        raise RuntimeError(f"API 错误: {resp['base_resp']}")

    data = resp.get("data", {})
    audio_url = data.get("audio") or data.get("audio_url")
    if not audio_url:
        raise RuntimeError(f"无 audio URL: {data}")

    extra = resp.get("extra_info", {})
    duration_ms = extra.get("music_duration", "?")
    size = extra.get("music_size", "?")
    print(f"\n时长: {duration_ms}ms ({duration_ms/1000 if isinstance(duration_ms,(int,float)) else '?'}s)")
    print(f"大小: {size} bytes")
    print(f"trace: {resp.get('trace_id')}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    fn = f"走在_主唱_cover_free_{ts}.mp3"
    out = os.path.join(OUT_DIR, fn)
    print(f"\n下载到 {out} ...")
    download(audio_url, out)
    sz = os.path.getsize(out)
    print(f"下载完成: {sz/1024/1024:.2f} MB")
    print(f"\n[成品] {out}")


if __name__ == "__main__":
    main()