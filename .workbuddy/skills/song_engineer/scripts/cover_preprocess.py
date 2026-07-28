# -*- coding: utf-8 -*-
"""
cover_preprocess.py - 调用 minimax music_cover_preprocess
读 full_multitrack_fs.wav 当参考音频, 拿 cover_feature_id
"""
import os
import json
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
ENDPOINT = "https://api.minimaxi.com/v1/music_cover_preprocess"
AUDIO = "workspace/project/走在/song_engineer/track/full_multitrack_fs.wav"
OUT = "workspace/project/走在/song_engineer/ai-track/cover_preprocess.json"


def main():
    if not API_KEY:
        print("[错误] .env 缺 minimax_api_key")
        return
    if not os.path.exists(AUDIO):
        print(f"[错误] {AUDIO} 不存在")
        return

    print(f"=== music_cover_preprocess ===")
    print(f"audio: {AUDIO}")
    print(f"size: {os.path.getsize(AUDIO)/1024/1024:.2f} MB")

    # API 期望 audio_url 或 audio_base64 (JSON body)
    import base64
    audio_data = open(AUDIO, "rb").read()
    audio_b64 = base64.b64encode(audio_data).decode("ascii")
    print(f"base64 length: {len(audio_b64)/1024/1024:.2f} MB")

    payload = {
        "model": "music-cover-free",
        "audio_base64": audio_b64,
    }
    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8")
        resp_json = json.loads(raw)
        print(f"\n响应(原始):")
        print(json.dumps(resp_json, ensure_ascii=False, indent=2)[:2000])

        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(resp_json, f, ensure_ascii=False, indent=2)
        print(f"\n[保存] {OUT}")

        # 提取关键字段
        fid = resp_json.get("cover_feature_id") or resp_json.get("data", {}).get("cover_feature_id")
        dur = resp_json.get("audio_duration")
        if fid:
            print(f"\ncover_feature_id: {fid}")
            print(f"audio_duration: {dur}s")
        else:
            print(f"\n[警告] 响应里没 cover_feature_id,看上面原始 JSON")
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="ignore")
        print(f"\n[HTTP {e.code}] {body_text[:500]}")
    except Exception as e:
        print(f"\n[异常] {e}")


if __name__ == "__main__":
    main()