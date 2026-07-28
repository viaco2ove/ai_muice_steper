#!/usr/bin/env python3
"""
separate_tracks.py - 使用 demucs 分离音轨
支持人声 / 鼓组 / 贝斯 / 其他 四个音轨分离
"""

import argparse
import os
import sys
from pathlib import Path

try:
    from demucs.pretrained import get_model
    from demucs.apply import apply_model
    import torch
except ImportError:
    print("❌ 缺少 demucs，请运行: pip install demucs -i https://mirrors.aliyun.com/pypi/simple/")
    sys.exit(1)


# 默认模型
DEFAULT_MODEL = "htdemucs"
# 可用模型: htdemucs, htdemucs_ft, htdemucs_mmi, ddx7, ddx7_tiny, sdxm


def separate_audio(input_path: str, output_dir: str, model_name: str = DEFAULT_MODEL,
                    device: str = None) -> dict[str, str]:
    """
    使用 demucs 分离音频文件

    Args:
        input_path: 输入音频文件路径（支持 mp3, wav, flac, ogg 等）
        output_dir: 输出目录
        model_name: demucs 模型名称
        device: 计算设备，None 则自动选择

    Returns:
        分离结果 dict，key 为音轨名，value 为文件路径
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"使用设备: {device}")

    # 加载模型
    print(f"加载模型: {model_name}...")
    model = get_model(model_name)
    model.eval()
    if device == "cuda":
        model = model.to(device)

    # 加载音频
    print(f"加载音频: {input_path}")
    import torchaudio
    waveform, sr = torchaudio.load(input_path)
    # demucs 要求 44100Hz
    if sr != 44100:
        print(f"  重采样 {sr}Hz -> 44100Hz")
        waveform = torchaudio.functional.resample(waveform, sr, 44100)
        sr = 44100
    # 扩维: (channels, samples) -> (sources, channels, samples)
    mixture = waveform.mean(dim=0, keepdim=True).unsqueeze(0)
    if device == "cuda":
        mixture = mixture.to(device)

    # 分离
    print("正在分离音轨...")
    with torch.no_grad():
        sources = apply_model(model, mixture, device=device, progress=True)

    # sources shape: (sources, channels, samples)
    # 音轨顺序: model.sources
    track_names = list(model.sources)
    output_files = {}

    os.makedirs(output_dir, exist_ok=True)

    for i, name in enumerate(track_names):
        track_waveform = sources[0, i].cpu()
        out_path = os.path.join(output_dir, f"{name}.wav")
        torchaudio.save(out_path, track_waveform, sr)
        output_files[name] = out_path
        print(f"  ✅ {name}.wav → {out_path}")

    return output_files


def main():
    parser = argparse.ArgumentParser(
        description="使用 demucs 分离音频为人声/鼓组/贝斯/其他",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python separate_tracks.py song.mp3 -o tracks/
  python separate_tracks.py song.wav -o out/ --model htdemucs_ft
  python separate_tracks.py song.mp3 -o tracks/ --device cpu

支持格式: mp3, wav, flac, ogg, m4a 等
首次运行会自动下载模型（约 80MB）
        """
    )
    parser.add_argument("input", help="输入音频文件路径")
    parser.add_argument("-o", "--output", default="tracks", help="输出目录 (default: tracks)")
    parser.add_argument(
        "-m", "--model", default=DEFAULT_MODEL,
        choices=["htdemucs", "htdemucs_ft", "htdemucs_mmi", "sdxm", "sdxm_tiny"],
        help="demucs 模型 (default: htdemucs)"
    )
    parser.add_argument(
        "-d", "--device",
        choices=["cpu", "cuda"],
        default=None,
        help="计算设备，不指定则自动选择"
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 文件不存在: {input_path}")
        sys.exit(1)

    try:
        result = separate_audio(
            str(input_path.absolute()),
            args.output,
            model_name=args.model,
            device=args.device
        )
        print("\n✅ 分离完成!")
        print(f"输出目录: {args.output}")
    except Exception as e:
        print(f"\n❌ 分离失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
