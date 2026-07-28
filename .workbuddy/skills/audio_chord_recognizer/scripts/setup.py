#!/usr/bin/env python3
"""
setup.py - audio_chord_recognizer 依赖一键安装脚本
使用阿里云 PyPI 镜像，国内下载速度快
"""

import subprocess
import sys
import os

# 国内可用的 PyPI 镜像
PYPI_MIRROR = "https://mirrors.aliyun.com/pypi/simple/"

# 依赖列表（按推荐顺序安装，避免版本冲突）
# crepe 依赖 setuptools wheel 先装
DEPENDENCIES = [
    "setuptools",   # crepe 需要 pkg_resources
    "wheel",
    "numpy",
    "scipy",
    "librosa",
    "mido",
    "basic-pitch",
    "demucs",
    "torch",        # 默认 CPU 版，如有 CUDA 可替换为 torch --index-url https://download.pytorch.org/whl/cu118
    "torchaudio",   # demucs 需要
    "soundfile",    # 音频加载（替代 torchaudio.load，兼容性更好）
    "decorator",    # librosa 依赖
    "audioread",    # librosa 依赖
    "einops<0.8",   # demucs 依赖（0.8+ API 不兼容）
]
# crepe 已从自动安装列表移除（需要 pkg_resources，与 Python 3.13 + setuptools 83 不兼容）
# 如需 crepe，请手动安装（需先降级 setuptools: pip install "setuptools<61"）
CREPE_OPTIONAL = [
    "crepe",        # 可选：另一套旋律识别方案，可替代 librosa.pyin
]

def run_cmd(cmd: list[str]) -> int:
    """执行命令，返回 exit code"""
    print(f"\n{'='*60}")
    print(f"> {' '.join(cmd)}")
    print('='*60)
    result = subprocess.run(cmd, shell=False)
    return result.returncode

def main():
    print("=" * 60)
    print("Audio Chord Recognizer - 依赖安装")
    print("=" * 60)

    # 检查 Python 版本
    ver = sys.version_info
    print(f"\nPython 版本: {ver.major}.{ver.minor}.{ver.micro}")
    if ver.major < 3 or (ver.major == 3 and ver.minor < 8):
        print("❌ 需要 Python 3.8+")
        sys.exit(1)
    print("✅ Python 版本满足要求")

    # 检查 pip
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], check=True, capture_output=True)
        print("✅ pip 可用")
    except subprocess.CalledProcessError:
        print("❌ pip 不可用，请先安装 pip")
        sys.exit(1)

    # 升级 pip
    print("\n[1/3] 升级 pip...")
    rc = run_cmd([sys.executable, "-m", "pip", "install", "--upgrade", "pip",
                  "-i", PYPI_MIRROR])
    if rc != 0:
        print("⚠️  pip 升级失败，继续安装...")

    # 安装依赖
    print("\n[2/3] 安装核心依赖...")
    for pkg in DEPENDENCIES:
        print(f"\n>>> 安装 {pkg}...")
        rc = run_cmd([
            sys.executable, "-m", "pip", "install", pkg,
            "-i", PYPI_MIRROR, "--quiet", "--disable-pip-version-check"
        ])
        if rc == 0:
            print(f"  ✅ {pkg} 安装成功")
        else:
            print(f"  ❌ {pkg} 安装失败 (exit {rc})，继续下一个...")

    # 验证
    print("\n[3/3] 验证已安装的包...")
    verify_list = ["numpy", "scipy", "librosa", "mido"]
    all_ok = True
    for pkg in verify_list:
        try:
            __import__(pkg)
            print(f"  ✅ {pkg}")
        except ImportError:
            print(f"  ❌ {pkg} 未找到")
            all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("✅ 安装完成！")
        print("\n快速开始:")
        print("  python scripts/full_analysis.py your_song.mp3 -o output/")
    else:
        print("⚠️  部分依赖安装失败，请检查上方错误信息")
        print("手动安装失败的包:")
        print(f"  pip install <pkg_name> -i {PYPI_MIRROR}")
    print("=" * 60)

if __name__ == "__main__":
    main()
