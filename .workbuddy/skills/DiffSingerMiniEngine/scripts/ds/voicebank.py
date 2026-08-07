# -*- coding: utf-8 -*-
"""声库层: 定位解压目录 / 加载5份配置 / 音素表 / 语言表 / 字典 / emb / 创建8个ONNX会话

配置驱动: 所有模型路径/音素表/语言表/emb 均按各组件 dsconfig.yaml 声明解析, 不写死声库。
官方契约要点(对照 OpenUTAU DiffSingerUtils/DiffSingerRenderer):
- languages: 音素带前缀(zh/a)->对应语言id; 无前缀(SP/AP)->0; padding SP->0
- emb: 每组件 speakers[0].emb 专属(4个emb数值全不同), 混喂致 f0/方差失真
- SP padding: 所有 linguistic/acoustic 输入首尾各 pad 1 个 SP token (HEAD/TAIL_FRAMES 帧)
"""
import os
import json
import yaml
import numpy as np
import onnxruntime as ort

from .config import ENV, DsConfig, VocoderConfig

try:
    _Loader = yaml.CSafeLoader
except AttributeError:
    _Loader = yaml.SafeLoader

# 官方 DiffSingerUtils: headFrames=8, tailFrames=8
HEAD_FRAMES = 8
TAIL_FRAMES = 8


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _clamp_ids(table):
    """音素id clamp到 [0, max_id-1]: embedding表行数=max_id, 个别键(如 zh/zh)映射到越界的 max_id"""
    mx = max(table.values())
    for k, v in table.items():
        if v >= mx:
            table[k] = mx - 1
    return table


def phoneme_language(ph):
    """官方 DiffSingerUtils.PhonemeLanguage: 'zh/a'->'zh', 'SP'->'' """
    return ph.split("/")[0] if "/" in ph else ""


class PhonemeTables:
    """一套音素表+语言表 (dur/pitch/variance/acoustic 各自独立, id 不可混用)"""

    def __init__(self, cfg):
        self.phonemes = _clamp_ids(_load_json(cfg.path(cfg.phonemes)))
        self.languages = _load_json(cfg.path(cfg.languages)) if cfg.languages else {}

    def token(self, ph):
        return self.phonemes.get(ph, self.phonemes.get("SP", 0))

    def lang_id(self, ph):
        """官方: GetValueOrDefault(PhonemeLanguage(ph), 0)"""
        return self.languages.get(phoneme_language(ph), 0)


class Voicebank:
    """dssinger 声库: 根(acoustic) + dsdur + dspitch + dsvariance + dsvocoder"""

    def __init__(self, root):
        self.root = root
        self.cfg_ac = DsConfig.load(os.path.join(root, "dsconfig.yaml"))
        self.cfg_dur = DsConfig.load(os.path.join(root, "dsdur", "dsconfig.yaml"))
        self.cfg_pitch = DsConfig.load(os.path.join(root, "dspitch", "dsconfig.yaml"))
        self.cfg_var = DsConfig.load(os.path.join(root, "dsvariance", "dsconfig.yaml"))
        self.cfg_voc = VocoderConfig.load(os.path.join(root, "dsvocoder", "vocoder.yaml"))

        self.tab_ac = PhonemeTables(self.cfg_ac)
        self.tab_dur = PhonemeTables(self.cfg_dur)
        self.tab_pitch = PhonemeTables(self.cfg_pitch)
        self.tab_var = PhonemeTables(self.cfg_var)

        self._load_dict()
        self._load_embs()
        self._sess = None

    @staticmethod
    def locate(zip_name=None):
        """由声库zip名定位解压目录 (OpenUTAU安装结构: singers_path同级/{stem}/{stem})"""
        sp = ENV.get("singers_path", r"D:\OpenUtau\Singers\Singers")
        if zip_name:
            stem = os.path.splitext(os.path.basename(zip_name))[0]
        elif os.path.splitext(sp)[1].lower() == ".zip":
            stem = os.path.splitext(os.path.basename(sp))[0]
        else:
            stem = "YunYe_DiffSinger_CE_26.07.16"
        bases = [os.path.dirname(sp)]
        if not os.path.splitext(sp)[1]:
            bases.append(sp)  # sp 本身是目录时, 也探测其下级
        cands = []
        for b in bases:
            for c in (os.path.join(b, stem, stem), os.path.join(b, stem)):
                if c not in cands:
                    cands.append(c)
        for c in cands:
            if os.path.exists(os.path.join(c, "dsconfig.yaml")):
                return c
        raise FileNotFoundError("voicebank not found, tried: " + "; ".join(cands))

    # ------------------------------------------------------------ 字典(g2p用)
    def _load_dict(self):
        """dsdur/dsdict-zh.yaml: symbols(元音判定) + entries(拼音->音素序列)"""
        p = os.path.join(self.cfg_dur.root, "dsdict-zh.yaml")
        with open(p, encoding="utf-8") as f:
            d = yaml.load(f, Loader=_Loader)
        self.symbol_type = {e["symbol"]: e.get("type", "") for e in d.get("symbols", [])}
        # 官方: SP/AP/EP/GS 等 type=vowel; 声母为 fricative/plosive 等非 vowel
        self.vowels = {s for s, t in self.symbol_type.items() if t == "vowel"}
        self.py2phs = {}
        for e in d.get("entries", []):
            py = e.get("grapheme", "")
            phs = e.get("phonemes", [])
            if isinstance(phs, str):
                phs = [phs]
            if py and phs and all(x in self.tab_dur.phonemes for x in phs):
                self.py2phs[py] = list(phs)

    def is_vowel(self, ph):
        return ph in self.vowels

    # ------------------------------------------------------------ emb
    def _load_embs(self):
        """每组件 speakers[0].emb (纯float32二进制流, 384维)"""
        def emb(cfg):
            name = (cfg.speakers or ["default"])[0] + ".emb"
            return np.fromfile(os.path.join(cfg.root, name), dtype=np.float32)
        self.emb_ac = emb(self.cfg_ac)
        self.emb_dur = emb(self.cfg_dur)
        self.emb_pitch = emb(self.cfg_pitch)
        self.emb_var = emb(self.cfg_var)

    # ------------------------------------------------------------ ONNX会话
    def sessions(self):
        """8会话 (arena/mem_pattern关闭: 逐段推理时arena持续累积不释放, 长曲后段必OOM)"""
        if self._sess is None:
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            opts.enable_cpu_mem_arena = False
            opts.enable_mem_pattern = False
            prov = ["CPUExecutionProvider"]

            def S(path):
                return ort.InferenceSession(path, opts, providers=prov)
            self._sess = {
                "ling_dur": S(self.cfg_dur.path(self.cfg_dur.linguistic)),
                "dur": S(self.cfg_dur.path(self.cfg_dur.dur)),
                "ling_var": S(self.cfg_var.path(self.cfg_var.linguistic)),
                "var": S(self.cfg_var.path(self.cfg_var.variance)),
                "ling_p": S(self.cfg_pitch.path(self.cfg_pitch.linguistic)),
                "pitch": S(self.cfg_pitch.path(self.cfg_pitch.pitch)),
                "ac": S(self.cfg_ac.path(self.cfg_ac.acoustic)),
                "voc": S(self.cfg_voc.path(self.cfg_voc.model)),
            }
        return self._sess

    # ------------------------------------------------------------ 验证打印
    def summary(self):
        print("voicebank: %s" % self.root)
        for name, cfg in (("acoustic", self.cfg_ac), ("dur", self.cfg_dur),
                          ("pitch", self.cfg_pitch), ("variance", self.cfg_var)):
            print("  [%s] predict_dur=%s use_expr=%s use_note_rest=%s max_depth=%.3g speakers=%s" % (
                name, cfg.predict_dur, cfg.use_expr, cfg.use_note_rest,
                cfg.max_depth, cfg.speakers))
        print("  [vocoder] sr=%d hop=%d mel_base=%s model=%s" % (
            self.cfg_voc.sample_rate, self.cfg_voc.hop_size,
            self.cfg_voc.mel_base, os.path.basename(self.cfg_voc.model)))
        print("  phonemes: ac=%d dur=%d pitch=%d var=%d | vowels=%d py2phs=%d" % (
            len(self.tab_ac.phonemes), len(self.tab_dur.phonemes),
            len(self.tab_pitch.phonemes), len(self.tab_var.phonemes),
            len(self.vowels), len(self.py2phs)))
        for name, e in (("ac", self.emb_ac), ("dur", self.emb_dur),
                        ("pitch", self.emb_pitch), ("var", self.emb_var)):
            print("  emb[%s]: dim=%d norm=%.4f" % (name, e.shape[0], float(np.linalg.norm(e))))
        for key, sess in self.sessions().items():
            ins = ", ".join("%s%s" % (i.name, i.shape) for i in sess.get_inputs())
            outs = ", ".join(o.name for o in sess.get_outputs())
            print("  [%s] in: %s -> out: %s" % (key, ins, outs))
