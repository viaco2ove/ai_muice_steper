# -*- coding: utf-8 -*-
"""g2p: 汉字 -> 音素序列 (pypinyin 取拼音 -> dsdict-zh.yaml entries 查音素)

只负责单字查询; slur('-') 韵母继承需要前字上下文, 在 plan 层处理。
返回音素字符串(如 "zh/b"), token id 由 voicebank.PhonemeTables 按组件各自映射。
"""
try:
    from pypinyin import pinyin, Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

# 视为休止的歌词占位符
REST_CHARS = ("R", "sp", "sil", "", "X", "…", "ҭ")


class G2P:
    def __init__(self, vb):
        self.vb = vb

    def lyric_phones(self, ch):
        """单字 -> [ph_str, ...] (1~2个: 声母+韵母); 休止/未知字 -> ["SP"]"""
        if ch in REST_CHARS or not HAS_PYPINYIN:
            return ["SP"]
        try:
            r = pinyin(ch, style=Style.NORMAL)
            py = r[0][0] if r and r[0] else None
        except Exception:
            py = None
        if py and py in self.vb.py2phs:
            return list(self.vb.py2phs[py])
        return ["SP"]

    def slur_phones(self, prev_seq):
        """'-' 拖腔: 只继承前字韵母(最后一个音素); 前字是R时调用方应保证不传SP污染序列"""
        if prev_seq:
            return [prev_seq[-1]]
        return ["SP"]
