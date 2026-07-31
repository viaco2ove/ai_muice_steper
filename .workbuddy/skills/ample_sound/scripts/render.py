"""
Ample Sound 替代方案：使用 FluidSynth 生成音频

Ample Sound VST 插件无法命令行调用，此脚本使用 FluidSynth + SoundFont 作为替代。
"""
import sys
import json
import subprocess
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# 读取 .env 配置
def load_env():
    env_path = Path(__file__).parent.parent.parent.parent.parent / '.env'
    config = {}
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    return config

def fluidsynth_available():
    """检查 FluidSynth 是否可用"""
    config = load_env()
    fluidsynth_path = config.get('fluidsynth_path', '')
    return Path(fluidsynth_path).exists() if fluidsynth_path else False

def get_soundfonts():
    """获取可用的 SoundFont 文件"""
    config = load_env()
    sfs_path = config.get('soundfonts_path', '')
    if sfs_path and Path(sfs_path).exists():
        return list(Path(sfs_path).glob('*.sf2')) + list(Path(sfs_path).glob('*.sf3'))
    return []

def main():
    print("Ample Sound VST 插件无法命令行调用")
    print()
    print("替代方案检查:")
    print("-" * 40)
    
    if fluidsynth_available():
        sfs = get_soundfonts()
        print(f"✅ FluidSynth: 可用 ({len(sfs)} 个 SoundFont)")
        for sf in sfs[:3]:
            print(f"   - {sf.name}")
    else:
        print("❌ FluidSynth: 未配置")
    
    print()
    print("可用的替代 skill:")
    print("  - fluidsynth_soundfont (如需创建)")
    print("  - musecore_render (MuseScore 渲染)")
    print("  - karplus_strong (物理建模合成)")

if __name__ == '__main__':
    main()