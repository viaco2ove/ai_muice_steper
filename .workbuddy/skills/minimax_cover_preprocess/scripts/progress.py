#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
progress.py — MiniMax 翻唱生成进度记录器

重要事实（已实测纠正）：
  MiniMax 的 music_cover / music_generation 是**同步阻塞接口**：
  POST /v1/music_generation 会一直保持连接，直到音频生成完，
  直接把 data.audio_url（或 data.audio 的 hex）返回在响应里。
  **不存在**异步查询端点（query_async_task 对音乐返回 404）。
  因此没有"百分比进度"可拉取——进度只能是「提交 → 等待心跳(已耗时) → 完成/失败」。

本模块提供：
  - append_entry / log_event：往 progress.md 追加一行记录（Markdown 表格）
  - Heartbeat：上下文管理器，进入时记「提交」，开一个后台线程每 interval 秒
    写一条「生成中（已等待 N 分）」心跳；退出时停线程。让同步长阻塞不再黑屏。

用法：
  python progress.py once --note "手动记录一条"
  （主要被 cover_two_step.py 的 generate 以 Heartbeat 方式调用）
"""
import os
import sys
import time
import threading

# 复用 cover_two_step 的环境/鉴权加载（同目录）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cover_two_step import load_env, get_api_key, load_mmx_base_url  # noqa: E402


# -------------------- Markdown 写入 --------------------
def _ensure_header(md_path):
    if os.path.exists(md_path):
        return
    os.makedirs(os.path.dirname(os.path.abspath(md_path)), exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 翻唱生成进度\n\n")
        f.write("> 由 `progress.py` 记录。MiniMax music_cover 为同步阻塞接口，")
        f.write("无异步进度百分比，此处按「提交→等待心跳→完成/失败」记录。\n\n")
        f.write("| 时间 | 状态 | 备注 |\n")
        f.write("|---|---|---|\n")


def append_entry(md_path, status_cn, note=""):
    """追加一行进度记录并立刻 flush。"""
    _ensure_header(md_path)
    t = time.strftime("%H:%M:%S")
    line = f"| {t} | {status_cn} | {note} |\n"
    with open(md_path, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
    return line


def log_event(md_path, status_cn, note=""):
    return append_entry(md_path, status_cn, note)


# -------------------- 心跳（同步长阻塞的可视化） --------------------
class Heartbeat:
    """上下文管理器：包住一次同步阻塞的 POST，期间定期写心跳。

    with progress.Heartbeat(md_path, interval=30):
        resp = requests.post(...)   # 阻塞数分钟
    # 退出时自动停心跳；由调用方在拿到响应后写「完成/失败」
    """

    def __init__(self, md_path, interval=30):
        self.md = md_path
        self.interval = interval
        self.start = time.time()
        self._stop = threading.Event()
        self._thread = None

    def _run(self):
        while not self._stop.wait(self.interval):
            elapsed = int(time.time() - self.start)
            mm = elapsed // 60
            ss = elapsed % 60
            append_entry(self.md, "生成中", f"已等待 {mm}分{ss}秒（同步接口，无百分比）")

    def __enter__(self):
        append_entry(self.md, "提交", "已提交生成请求，等待 MiniMax 返回音频（同步接口）")
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop.set()
        if self._thread:
            self._thread.join(self.interval + 2)
        if exc_type is not None:
            append_entry(self.md, "失败", f"异常: {exc_val}")
        return False  # 不吞异常


# -------------------- CLI --------------------
def main():
    import argparse
    ap = argparse.ArgumentParser(description="MiniMax 翻唱生成进度记录器")
    sub = ap.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("once", help="手动追加一条记录")
    o.add_argument("--out-md", required=True)
    o.add_argument("--status", default="备注", help="状态中文，如 完成/失败/生成中")
    o.add_argument("--note", default="")

    args = ap.parse_args()
    if args.cmd == "once":
        line = append_entry(args.out_md, args.status, args.note)
        print(line.strip())


if __name__ == "__main__":
    main()
