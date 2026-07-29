#!/usr/bin/env python3
"""
OpenUTAU 歌词转音素脚本
将中文歌词转换为 OpenUTAU 可用的 CV/VC Phonemes
"""

import sys
import argparse
import json
import re
import os

# 确保 UTF-8 输出
sys.stdout.reconfigure(encoding="utf-8")

# 拼音-音素映射表（简化版，覆盖常用字）
PINYIN_PHONEME_MAP = {
    # 声母
    "b": "b", "p": "p", "m": "m", "f": "f",
    "d": "d", "t": "t", "n": "n", "l": "l",
    "g": "g", "k": "k", "h": "h",
    "j": "j", "q": "q", "x": "x",
    "zh": "zh", "ch": "ch", "sh": "sh", "r": "r",
    "z": "z", "c": "c", "s": "s",
    "y": "y", "w": "w",

    # 韵母
    "a": "a", "o": "o", "e": "e", "i": "i", "u": "u",
    "v": "v", "ü": "v",

    # 复元音
    "ai": "ai", "ei": "ei", "ao": "ao", "ou": "ou",
    "ia": "ia", "ie": "ie", "ua": "ua", "uo": "uo", "üe": "ve",

    # 鼻音
    "an": "an", "en": "en", "ang": "aN", "eng": "eN", "ing": "iN",

    # 特殊韵母
    "er": "er", "ian": "ian", "iang": "iaN", "iao": "iao",
    "iong": "ioN", "uao": "uao", "uai": "uai",
    "uan": "uan", "uen": "uen", "ong": "oN", "uang": "uaN",
}

# 常用汉字拼音表（简化版，覆盖"走在"歌曲用字）
CHAR_PINYIN_MAP = {
    # 主歌A 歌词
    "门": "men", "虚": "xu", "掩": "yan", "着": "zhe",
    "风": "feng", "掀": "xian", "了": "le", "快": "kuai", "递": "di",
    "鞋": "xie", "尖": "jian", "沾": "zhan", "雨": "yu",
    "空": "kong", "调": "diao", "数": "shu", "到": "dao", "七": "qi",
    "没": "mei", "起": "qi", "身": "shen", "窝": "wo", "在": "zai",
    "花": "hua", "海": "hai", "沙": "sha", "发": "fa", "陷": "xian",
    "杯": "bei", "底": "di", "淡": "dan", "去": "qu",

    # 主歌B 歌词
    "拖": "tuo", "鞋": "xie", "半": "ban", "掉": "diao",
    "踩": "cai", "过": "guo", "泥": "ni", "和": "he", "水": "shui",
    "冷": "leng", "柜": "gui", "蓝": "lan", "买": "mai", "回": "hui",
    "人": "ren", "留": "liu", "意": "yi", "体": "ti", "动": "dong",
    "灵": "ling", "魂": "hun", "走": "zou", "过": "guo",

    # 间奏
    "嗯": "en", "它": "ta", "又": "you", "像": "xiang", "都": "dou", "走": "zou",

    # 副歌
    "圈": "quan", "投": "tou", "屏": "ping", "卡": "ka", "截": "jie",
    "消": "xiao", "息": "xi", "弹": "dan", "出": "chu", "名": "ming",
    "字": "zi", "很": "hen", "熟": "shu", "悉": "xi",
    "有": "you", "碰": "peng", "肩": "jian", "晃": "huang", "窗": "chuang",
    "帘": "lian", "细": "xi", "线": "xian", "反": "fan", "复": "fu",

    # 主歌A' 歌词
    "地": "de", "铁": "tie", "报": "bao", "站": "zhan",
    "靠": "kao", "门": "men", "打": "da", "哈": "ha", "欠": "qian",
    "手": "shou", "里": "li", "攥": "zuan", "皱": "zhou", "小": "xiao",
    "票": "piao", "目": "mu", "的": "de", "忘": "wang", "填": "tian",
    "第": "di", "三": "san", "弦": "xian", "还": "hai", "响": "xiang",
    "已": "yi", "别": "bie", "地": "di",

    # 副歌2 + 尾奏
    "光": "guang", "线": "xian", "吹": "chui", "散": "san",
    "飘": "piao", "脚": "jiao", "麻": "ma", "水": "shui", "凉": "liang",
    "算": "suan", "啦": "la", "啊": "a",
}


def get_pinyin_syllables(pinyin: str) -> tuple:
    """拆分拼音为声母+韵母"""
    for i in range(len(pinyin), 0, -1):
        prefix = pinyin[:i]
        suffix = pinyin[i:]
        if prefix in PINYIN_PHONEME_MAP and suffix in PINYIN_PHONEME_MAP:
            return prefix, suffix
    # 默认：声母可能为空（如 "a", "o" 等韵母开头）
    return "", pinyin


def lyrics_to_cvphonemes(lyrics: str) -> list:
    """将歌词转换为 CV Phonemes"""
    results = []

    # 移除标点符号，按字分割
    chars = re.findall(r'[一-鿿]+', lyrics)
    all_chars = []
    for chunk in chars:
        all_chars.extend(list(chunk))

    for char in all_chars:
        if char in CHAR_PINYIN_MAP:
            pinyin = CHAR_PINYIN_MAP[char]
            initial, final = get_pinyin_syllables(pinyin)

            if initial:
                # CV 格式: 声母+韵母
                cv_phoneme = f"{initial}+{final}"
            else:
                # 纯韵母（零声母）
                cv_phoneme = final

            results.append({
                "char": char,
                "pinyin": pinyin,
                "initial": initial,
                "final": final,
                "cv": cv_phoneme,
                "vc": f"{final}+{initial}" if initial else f"{final}+{final}",
            })
        else:
            # 未知汉字，标记
            results.append({
                "char": char,
                "pinyin": "?",
                "initial": "?",
                "final": "?",
                "cv": "?",
                "vc": "?",
            })

    return results


def format_cv_output(results: list) -> str:
    """格式化输出 CV Phonemes"""
    lines = []
    for r in results:
        lines.append(f"{r['char']:4s} {r['cv']}")
    return "\n".join(lines)


def format_vc_output(results: list) -> str:
    """格式化输出 VC Phonemes"""
    lines = []
    for r in results:
        lines.append(f"{r['char']:4s} {r['vc']}")
    return "\n".join(lines)


def format_full_output(results: list) -> str:
    """完整格式输出"""
    lines = ["字符  拼音    声母  韵母   CV            VC"]
    lines.append("-" * 50)
    for r in results:
        lines.append(
            f"{r['char']:4s} {r['pinyin']:8s} {r['initial'] or '-':4s} {r['final']:6s} "
            f"{r['cv']:12s} {r['vc']}"
        )
    return "\n".join(lines)


def generate_ustx_lyrics(results: list) -> str:
    """生成 OpenUTAU 可用的歌词字符串（用于 ust/ustx）"""
    # OpenUTAU 的 lyric 字段直接用音素或汉字
    lyrics = []
    for r in results:
        # 使用 CV 音素格式
        lyrics.append(r['cv'])
    return " ".join(lyrics)


def main():
    parser = argparse.ArgumentParser(description="歌词转 OpenUTAU 音素")
    parser.add_argument("-lyrics", type=str, help="歌词文本")
    parser.add_argument("-file", type=str, help="歌词文件路径")
    parser.add_argument("-output", type=str, help="输出文件路径")
    parser.add_argument("-mode", choices=["cv", "vc", "full"], default="full",
                        help="输出模式: cv(仅CV音素) / vc(仅VC音素) / full(完整信息)")
    parser.add_argument("-lang", type=str, default="zh", help="语言: zh/cn=中文")

    args = parser.parse_args()

    # 读取歌词
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            lyrics = f.read()
    elif args.lyrics:
        lyrics = args.lyrics
    else:
        print("请提供 -lyrics 或 -file 参数")
        sys.exit(1)

    # 转换
    results = lyrics_to_cvphonemes(lyrics)

    # 输出
    if args.mode == "cv":
        output = format_cv_output(results)
    elif args.mode == "vc":
        output = format_vc_output(results)
    else:
        output = format_full_output(results)

    # 添加 ust 格式歌词
    ust_lyrics = generate_ustx_lyrics(results)

    full_output = f"""{output}

---
OpenUTAU ust/ustx 格式歌词:
{ust_lyrics}
"""

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(full_output)
        print(f"已输出到: {args.output}")
    else:
        print(full_output)


if __name__ == "__main__":
    main()
