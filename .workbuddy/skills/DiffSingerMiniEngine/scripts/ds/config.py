# -*- coding: utf-8 -*-
"""配置层: .env / dsconfig.yaml / vocoder.yaml 解析

复刻 OpenUTAU DsConfig/DsVocoderConfig 的字段与默认值语义:
- max_depth: use_continuous_acceleration 为 true 时直接用, 否则 /1000
- use_variable_depth: 与 use_shallow_diffusion 合并(任一声明即生效)
- mel_base: "10" 或 "e"; acoustic 与 vocoder 不一致时渲染端乘 ln10/log10(e) 转换
"""
import os
import yaml
from dataclasses import dataclass
from typing import List, Optional


def load_env():
    """工作区根 .env -> dict (singers_path / diff_singer_mini_engine_assets 等)"""
    env = {}
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), *([".."] * 5)))
    p = os.path.join(root, ".env")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


ENV = load_env()


@dataclass
class DsConfig:
    """dsconfig.yaml (每个模型组件目录各一份: 根/dsdur/dspitch/dsvariance)"""
    root: str = ""                         # 配置文件所在目录(相对路径解析基准)
    phonemes: str = "phonemes.txt"
    languages: Optional[str] = None
    acoustic: Optional[str] = None
    vocoder: Optional[str] = None
    speakers: Optional[List[str]] = None
    hidden_size: int = 256
    use_key_shift_embed: bool = False
    use_speed_embed: bool = False
    use_energy_embed: bool = False
    use_breathiness_embed: bool = False
    use_voicing_embed: bool = False
    use_tension_embed: bool = False
    use_continuous_acceleration: bool = False
    use_lang_id: bool = False
    use_variable_depth: bool = False
    max_depth_raw: float = 1.0
    dur: Optional[str] = None
    linguistic: Optional[str] = None
    pitch: Optional[str] = None
    variance: Optional[str] = None
    predict_dur: bool = True
    predict_energy: bool = True
    predict_breathiness: bool = True
    predict_voicing: bool = False
    predict_tension: bool = False
    use_expr: bool = False
    use_note_rest: bool = False
    sample_rate: int = 44100
    hop_size: int = 512
    win_size: int = 2048
    fft_size: int = 2048
    num_mel_bins: int = 128
    mel_fmin: float = 40.0
    mel_fmax: float = 16000.0
    mel_base: str = "10"
    mel_scale: str = "slaney"

    @property
    def max_depth(self):
        """官方语义: 连续加速模型直接用原始值, 否则 /1000"""
        return self.max_depth_raw if self.use_continuous_acceleration else self.max_depth_raw / 1000.0

    @property
    def frame_ms(self):
        return 1000.0 * self.hop_size / self.sample_rate

    @property
    def fps(self):
        return self.sample_rate / float(self.hop_size)

    def path(self, rel):
        """相对路径字段 -> 绝对路径(相对本配置目录解析)"""
        return os.path.normpath(os.path.join(self.root, rel)) if rel else None

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        cfg = cls(root=os.path.dirname(path))
        for k, v in d.items():
            if k in ("use_variable_depth", "use_shallow_diffusion"):
                if v is not None:
                    cfg.use_variable_depth = bool(v)
            elif k == "max_depth":
                cfg.max_depth_raw = float(v)
            elif k == "augmentation_args":
                continue
            elif hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg


@dataclass
class VocoderConfig:
    """dsvocoder/vocoder.yaml"""
    root: str = ""
    name: str = ""
    model: str = ""
    sample_rate: int = 44100
    hop_size: int = 512
    win_size: int = 2048
    fft_size: int = 2048
    num_mel_bins: int = 128
    mel_fmin: float = 40.0
    mel_fmax: float = 16000.0
    mel_base: str = "10"
    mel_scale: str = "slaney"
    pitch_controllable: bool = True

    @property
    def frame_ms(self):
        return 1000.0 * self.hop_size / self.sample_rate

    def path(self, rel):
        return os.path.normpath(os.path.join(self.root, rel)) if rel else None

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        cfg = cls(root=os.path.dirname(path))
        for k, v in d.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg
