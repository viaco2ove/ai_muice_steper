# -*- coding: utf-8 -*-
"""
cover_two_step.py — MiniMax 两步翻唱 (music-cover) 辅助脚本

为什么需要两步（而不是 mmx music cover 一步）：
  一步 cover 直接把「带伴奏的整混音」传给 MiniMax，模型会把背景乐器声误判为主旋律，
  且 music-cover-free 会乱改声线（上一个版本就翻车成女声、编曲旋律全跑偏）。
  两步流程先提纯「纯人声干音」做前处理，拿到 cover_feature_id + ASR 歌词 + 结构时间戳，
  人工校正歌词对齐点后，再传入生成接口，结果可控得多。

两步流程：
  Step1 preprocess: 提纯纯人声干音（UVR5 / demucs / 或用户直接给干音）→ 只上传干音到
                     POST /v1/music_cover_preprocess （model=music-cover）
                     → 返回 cover_feature_id(24h有效) + formatted_lyrics(ASR歌词,带[Verse]等标签)
                       + structure_result(JSON字符串,各段类型与起止时间戳)
  Step2 generate:   用人工校正后的 lyrics + cover_feature_id + prompt 调
                     POST /v1/music_generation （model=music-cover，非 free）
                     → 同步阻塞（POST 保持连接）直到返回音频
                     → 取 data.audio_url(URL) 或 data.audio(hex/base64) 存 mp3
                     （music_cover 是同步接口，没有异步进度端点）

铁律：
  1. 只传纯人声干音，绝不传带伴奏的整混音。
  2. 用 music-cover（付费），不用 music-cover-free。
  3. cover_feature_id 24h 有效，必须人工校正歌词后才能跑 Step2。

用法：
  # Step1：直接给干音
  python cover_two_step.py preprocess --vocals <dry_vocal.wav> --out-dir <dir>
  # Step1：给整曲，自动 demucs 提纯
  python cover_two_step.py preprocess --source <song.wav> --out-dir <dir>
  # Step2：用校正后的歌词生成
  python cover_two_step.py generate --preprocess-json <dir>/cover_preprocess.json \
      --lyrics <dir>/formatted_lyrics.corrected.txt --prompt "..." --out <out.mp3>
"""
import os
import sys
import json
import time
import base64
import shutil
import argparse
import subprocess

try:
    import requests
except ImportError:
    print("[错误] 缺少 requests，请装: pip install requests")
    sys.exit(1)

# 项目根（向上找，必须同时含 .env 和 workspace 才算项目根，
# 避免被 .workbuddy/skills 下的 workspace 子目录误命中）
_CUR = os.path.dirname(os.path.abspath(__file__))


def _find_root():
    cands = [os.getcwd(), _CUR]
    for base in cands:
        r = base
        for _ in range(8):
            if os.path.exists(os.path.join(r, ".env")) and os.path.isdir(os.path.join(r, "workspace")):
                return r
            r = os.path.dirname(r)
    # fallback: 任意含 .env 的目录
    r = _CUR
    for _ in range(8):
        if os.path.exists(os.path.join(r, ".env")):
            return r
        r = os.path.dirname(r)
    return _CUR


ROOT = _find_root()

DEFAULT_BASE_URL = "https://api.minimaxi.com"  # region=cn（与 mmx config 一致）


# ==================== 配置读取 ====================
def load_env():
    env = {}
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def load_mmx_base_url():
    """从 mmx 配置读 base_url（region=cn）。"""
    cfg_paths = [
        os.path.join(os.path.expanduser("~"), ".mmx", "config.json"),
        os.path.join(ROOT, ".mmx", "config.json"),
    ]
    for cp in cfg_paths:
        if os.path.exists(cp):
            try:
                cfg = json.load(open(cp, encoding="utf-8"))
                if cfg.get("base_url"):
                    return cfg["base_url"].rstrip("/")
            except Exception:
                pass
    return DEFAULT_BASE_URL


def get_api_key():
    env = load_env()
    key = env.get("minimax_api_key") or os.environ.get("MINIMAX_API_KEY")
    if not key:
        print("[错误] 找不到 MiniMax API key（.env 的 minimax_api_key 或环境变量 MINIMAX_API_KEY）")
        sys.exit(1)
    return key


# ==================== 干音提纯（demucs，UVR5 等价物） ====================
def separate_vocals(source_path, out_dir, venv_py):
    """用 demucs 分离人声。返回 vocals 干音 wav 路径。"""
    print(f"[分离] demucs 提纯人声: {os.path.basename(source_path)}")
    sep_root = os.path.join(out_dir, "demucs_sep")
    os.makedirs(sep_root, exist_ok=True)
    cmd = [
        venv_py, "-m", "demucs", "-n", "htdemucs", "-o", sep_root,
        "--two-stems", "vocals", source_path,
    ]
    print("  $ " + " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("[错误] demucs 分离失败:\n" + (r.stderr or r.stdout)[-2000:])
        sys.exit(1)
    # demucs 输出: <sep_root>/htdemucs/<basename>/vocals.wav
    base = os.path.splitext(os.path.basename(source_path))[0]
    vocal = os.path.join(sep_root, "htdemucs", base, "vocals.wav")
    if not os.path.exists(vocal):
        # 兜底搜索
        for dp, _, fs in os.walk(sep_root):
            for f in fs:
                if f == "vocals.wav":
                    vocal = os.path.join(dp, f)
    if not os.path.exists(vocal):
        print(f"[错误] 未找到分离出的 vocals.wav（搜索 {sep_root}）")
        sys.exit(1)
    print(f"  [分离完成] {vocal}")
    return vocal


def _ensure_uploadable(path, out_dir):
    """非 mp3 或体积过大则 ffmpeg 转码为 mp3（128kbps），返回用于上传的路径。

    base64 上传时请求体约为原文件 1.33 倍，MiniMax 对单请求有上限；
    把干音压成 mp3（ASR 对 mp3 同样可靠）可避免超限。"""
    size_mb = os.path.getsize(path) / 1e6 if os.path.exists(path) else 0
    is_mp3 = path.lower().endswith(".mp3")
    if is_mp3 and size_mb <= 15:
        return path
    ff = shutil.which("ffmpeg") or "ffmpeg"
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(out_dir, base + "_upload.mp3")
    cmd = [ff, "-y", "-i", path, "-codec:a", "libmp3lame", "-b:a", "128k", out]
    print(f"[转码] {os.path.basename(path)} ({size_mb:.1f}MB) -> mp3 以压小上传体积")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("[警告] ffmpeg 转码失败，回退用原文件:\n" + (r.stderr or r.stdout or "")[-800:])
        return path
    return out


# ==================== Step1: preprocess ====================
def step_preprocess(args):
    env = load_env()
    base_url = args.base_url or load_mmx_base_url()
    api_key = get_api_key()
    venv_py = args.venv or os.path.join(ROOT, ".venv", "python.exe")

    # 1) 决定干音文件
    if args.vocals:
        vocals = args.vocals
        print(f"[Step1] 使用已提供的纯人声干音: {vocals}")
    elif args.source:
        vocals = separate_vocals(args.source, args.out_dir, venv_py)
    else:
        print("[错误] 必须给 --vocals（干音）或 --source（整曲，自动分离）")
        sys.exit(1)

    if not os.path.exists(vocals):
        print(f"[错误] 干音文件不存在: {vocals}")
        sys.exit(1)

    # 1.5) 过大或非 mp3 则 ffmpeg 转码压小（避免 base64 超 request 体限制）
    vocals = _ensure_uploadable(vocals, args.out_dir)

    # 2) base64 编码
    with open(vocals, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("ascii")
    print(f"[Step1] 干音大小: {os.path.getsize(vocals)/1e6:.1f}MB，base64 上传")

    # 3) 调 preprocess 接口
    url = f"{base_url}/v1/music_cover_preprocess"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "music-cover", "audio_base64": audio_b64}
    print(f"[Step1] POST {url}")
    resp = requests.post(url, headers=headers, json=payload, timeout=300)
    data = resp.json()
    if data.get("base_resp", {}).get("status_code", -1) != 0:
        print("[错误] preprocess 失败:\n" + json.dumps(data, ensure_ascii=False, indent=2))
        sys.exit(1)

    cover_feature_id = data.get("cover_feature_id")
    formatted_lyrics = data.get("formatted_lyrics") or ""
    structure_result = data.get("structure_result") or ""
    audio_duration = data.get("audio_duration")
    trace_id = data.get("trace_id")
    print(f"[Step1] cover_feature_id: {cover_feature_id}")
    print(f"[Step1] audio_duration: {audio_duration}s  trace_id: {trace_id}")

    # 4) 落盘
    os.makedirs(args.out_dir, exist_ok=True)
    meta = {
        "cover_feature_id": cover_feature_id,
        "audio_duration": audio_duration,
        "trace_id": trace_id,
        "vocals_file": os.path.abspath(vocals),
        "model": "music-cover",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "structure_result": structure_result,
    }
    json_path = os.path.join(args.out_dir, "cover_preprocess.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    lyr_path = os.path.join(args.out_dir, "formatted_lyrics.txt")
    with open(lyr_path, "w", encoding="utf-8") as f:
        f.write(formatted_lyrics)

    struct_path = os.path.join(args.out_dir, "structure_result.txt")
    with open(struct_path, "w", encoding="utf-8") as f:
        f.write(structure_result if isinstance(structure_result, str) else json.dumps(structure_result, ensure_ascii=False, indent=2))

    # 5) 打印供人工校正
    print("\n" + "=" * 60)
    print("【Step1 完成】请人工校正以下歌词对齐点，再跑 generate：")
    print("=" * 60)
    print("\n----- formatted_lyrics.txt（ASR 提取，需校正）-----")
    print(formatted_lyrics)
    print("\n----- structure_result（各段起止时间戳，供对照）-----")
    print(structure_result if isinstance(structure_result, str) else json.dumps(structure_result, ensure_ascii=False, indent=2))
    print("\n文件:")
    print(f"  {json_path}")
    print(f"  {lyr_path}   <- 编辑这个（校正歌词）")
    print(f"  {struct_path}")
    print("\n下一步（校正歌词后）:")
    print(f"  python cover_two_step.py generate --preprocess-json {json_path} "
          f"--lyrics {lyr_path} --prompt \"<目标风格>\" --out <out.mp3>")
    return json_path


# ==================== Step2: generate ====================
def _download(url, out):
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with requests.get(url, timeout=300, stream=True) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return out


def step_generate(args):
    env = load_env()
    base_url = args.base_url or load_mmx_base_url()
    api_key = get_api_key()

    # 读 preprocess 结果
    if args.preprocess_json:
        meta = json.load(open(args.preprocess_json, encoding="utf-8"))
        cover_feature_id = meta.get("cover_feature_id")
    else:
        cover_feature_id = args.feature_id
    if not cover_feature_id:
        print("[错误] 需要 --preprocess-json 或 --feature-id")
        sys.exit(1)

    # 读歌词
    if args.lyrics and os.path.exists(args.lyrics):
        lyrics = open(args.lyrics, encoding="utf-8").read().strip()
    elif args.lyrics:
        lyrics = args.lyrics.strip()
    else:
        print("[错误] 必须给 --lyrics（校正后的歌词文件或文本）")
        sys.exit(1)
    if not (10 <= len(lyrics) <= 1000):
        print(f"[警告] lyrics 长度 {len(lyrics)} 不在 [10,1000]，MiniMax 可能拒收")

    prompt = args.prompt
    if not (10 <= len(prompt) <= 300):
        print(f"[警告] prompt 长度 {len(prompt)} 不在 [10,300]")

    model = args.model  # 默认 music-cover
    url = f"{base_url}/v1/music_generation"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "cover_feature_id": cover_feature_id,
        "lyrics": lyrics,
        "prompt": prompt,
        "output_format": "url",   # 同步返回 data.audio_url（24h 有效），无需轮询
        "audio_setting": {
            "format": "mp3",
            "sample_rate": 44100,
            "bitrate": 256000,
            "channel": 2,
        },
    }

    # 进度记录：music_cover 是同步阻塞接口（POST 保持连接直到返回音频），
    # 没有异步进度端点，用 Heartbeat 在等待期间定期写心跳到 progress.md。
    sys.path.insert(0, _CUR)
    import progress  # 惰性导入，避免与 cover_two_step 循环依赖
    _out_dir = os.path.dirname(os.path.abspath(args.out))
    _md = os.path.join(_out_dir, "progress.md")
    _meta = os.path.join(_out_dir, "generate_meta.json")
    json.dump({
        "model": model,
        "cover_feature_id": cover_feature_id,
        "out": os.path.abspath(args.out),
        "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, open(_meta, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[Step2] POST {url}  model={model}")
    print(f"[Step2] cover_feature_id={cover_feature_id}")
    print(f"[Step2] 进度记录到: {_md}")

    with progress.Heartbeat(_md, interval=30):
        # 阻塞等待 MiniMax 生成完并返回音频（通常 1~5 分钟）
        resp = requests.post(url, headers=headers, json=payload, timeout=600)
    d = resp.json()

    # 兜底：把原始响应落盘，便于失败时排查真实结构
    _resp_dump = os.path.join(_out_dir, "generate_resp.json")
    try:
        json.dump(d, open(_resp_dump, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass

    if d.get("base_resp", {}).get("status_code", -1) != 0:
        progress.append_entry(_md, "失败", "生成接口返回错误")
        print("[错误] 生成失败:\n" + json.dumps(d, ensure_ascii=False, indent=2))
        sys.exit(1)

    data = d.get("data", {}) or {}
    # 兼容三种返回：audio_url（URL）/ audio（hex）/ audio（base64）
    audio_url = data.get("audio_url")
    audio_raw = data.get("audio")
    saved_path = None
    src_kind = None
    if audio_url and str(audio_url).startswith("http"):
        saved_path = _download(audio_url, args.out)
        src_kind = "url"
    elif audio_raw:
        s = str(audio_raw)
        if s.startswith("http"):
            saved_path = _download(s, args.out)
            src_kind = "url(audio字段)"
        else:
            # 先试 hex，再试 base64
            try:
                buf = bytes.fromhex(s)
                src_kind = "hex"
            except ValueError:
                try:
                    buf = base64.b64decode(s, validate=True)
                    src_kind = "base64"
                except Exception:
                    buf = None
            if buf:
                out = os.path.abspath(args.out)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with open(out, "wb") as f:
                    f.write(buf)
                saved_path = out
    if saved_path:
        progress.append_entry(_md, "完成",
                              f"已保存({src_kind}) {os.path.basename(saved_path)} ({os.path.getsize(saved_path)/1e6:.2f}MB)")
        print(f"[Step2] 已保存: {saved_path}  ({src_kind}, {os.path.getsize(saved_path)/1e6:.2f}MB)")
        return saved_path
    else:
        progress.append_entry(_md, "失败", "响应无 audio_url / audio 字段")
        print("[错误] 响应中找不到音频，结构:\n" + json.dumps(d, ensure_ascii=False, indent=2)[:2000])
        sys.exit(1)


# ==================== CLI ====================
def main():
    ap = argparse.ArgumentParser(description="MiniMax 两步翻唱 (music-cover)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("preprocess", help="Step1 前处理：提纯干音+提取歌词/结构")
    pp.add_argument("--vocals", help="纯人声干音 wav/mp3（已提纯则直接给）")
    pp.add_argument("--source", help="整曲音频，自动用 demucs 提纯人声")
    pp.add_argument("--out-dir", required=True, help="输出目录（存 preprocess 结果）")
    pp.add_argument("--venv", help="含 demucs 的 python（默认 根/.venv/python.exe）")
    pp.add_argument("--base-url", help="MiniMax base url（默认读 mmx config）")
    pp.set_defaults(func=step_preprocess)

    gn = sub.add_parser("generate", help="Step2 生成：cover_feature_id + 修正歌词 + prompt")
    gn.add_argument("--preprocess-json", help="Step1 产出的 cover_preprocess.json")
    gn.add_argument("--feature-id", help="或直接给 cover_feature_id")
    gn.add_argument("--lyrics", required=True, help="校正后的歌词文件或文本")
    gn.add_argument("--prompt", required=True, help="目标翻唱风格（10-300字）")
    gn.add_argument("--model", default="music-cover", help="模型，默认 music-cover（非 free）")
    gn.add_argument("--out", required=True, help="输出 mp3 路径")
    gn.add_argument("--poll-timeout", type=int, default=1200, help="轮询超时秒")
    gn.add_argument("--base-url", help="MiniMax base url")
    gn.set_defaults(func=step_generate)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
