#!/usr/bin/env python3
"""
full_composition.py - 从音频分析到完整编曲方案的一键生成
整合 audio_chord_recognizer + ai_chords_master
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# 添加 skills 路径
SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SKILL_DIR))


def run_audio_analysis(audio_path: str, output_dir: str) -> dict:
    """调用 audio_chord_recognizer 的全流程分析"""
    print("\n" + "=" * 60)
    print("Step 1/3: 音频分析（和弦 + 旋律识别）")
    print("=" * 60)

    # 查找 audio_chord_recognizer 的脚本
    acr_script = SKILL_DIR.parent / "audio_chord_recognizer" / "scripts" / "full_analysis.py"
    if not acr_script.exists():
        return {"error": "audio_chord_recognizer 未安装"}

    # 运行分析
    try:
        result = subprocess.run(
            [sys.executable, str(acr_script), audio_path, "-o", output_dir],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            print(f"⚠️ 音频分析有警告: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        return {"error": "音频分析超时"}
    except Exception as e:
        return {"error": f"音频分析失败: {e}"}

    # 读取旋律数据
    melody_csv = os.path.join(output_dir, "melody", "pitch.csv")
    return {
        "melody_csv": melody_csv if os.path.exists(melody_csv) else None,
        "report_md": os.path.join(output_dir, "report.md"),
    }


def generate_chord_progression(analysis_result: dict, basic_progression: list, title: str, **kwargs) -> str:
    """调用 composer 生成编曲方案"""
    print("\n" + "=" * 60)
    print("Step 2/3: 生成丰富和弦进行")
    print("=" * 60)

    from composer import generate_output, format_markdown

    result = generate_output(
        title=title,
        basic_progression=basic_progression,
        melody_csv_path=analysis_result.get("melody_csv"),
        **kwargs
    )

    output = format_markdown(result)
    return output


def main():
    parser = argparse.ArgumentParser(
        description="从音频到完整编曲方案的一键生成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基础用法（需提供音频 + 基础和弦）
  python full_composition.py --audio input.mp3 --progression "C7,C7,Em7/B,Em7/B,Em7"

  # 指定曲名和形态
  python full_composition.py --audio input.mp3 --progression "C7,C7,Em7/B,Em7/B,Em7" \\
      --title "我的沙发曲" --form bloom --tempo 65

  # 仅生成编曲（跳过音频分析）
  python full_composition.py --progression "C7,C7,Em7/B,Em7/B,Em7" --title "快速方案"
        """
    )
    parser.add_argument("--audio", help="音频文件路径（mp3/wav）")
    parser.add_argument("--progression", required=True, help="基础和弦进行，逗号分隔")
    parser.add_argument("--title", default="沙发小曲", help="歌曲名")
    parser.add_argument("--form", default="standard", choices=["standard", "bloom"], help="曲式形态")
    parser.add_argument("--enrichment", default="rich", choices=["light", "rich", "full"], help="丰富程度")
    parser.add_argument("--tempo", type=int, default=68, help="BPM")
    parser.add_argument("-o", "--output", default=None, help="输出 .md 文件路径")

    args = parser.parse_args()

    basic_progression = [c.strip() for c in args.progression.split(",") if c.strip()]
    print("=" * 60)
    print("ai_chords_master - 沙发小曲完整编曲方案生成器")
    print("=" * 60)
    print(f"基础和弦: {' → '.join(basic_progression)}")
    print(f"曲名: {args.title}")

    analysis_result = {"melody_csv": None}

    # Step 1: 音频分析（如果提供了音频）
    if args.audio:
        audio_path = Path(args.audio).expanduser()
        if not audio_path.exists():
            print(f"❌ 音频文件不存在: {audio_path}")
            sys.exit(1)

        analysis_output = str(SKILL_DIR / "audio_output")
        os.makedirs(analysis_output, exist_ok=True)

        result = run_audio_analysis(str(audio_path), analysis_output)
        if "error" in result:
            print(f"⚠️ 音频分析跳过: {result['error']}")
            print("   将基于基础和弦骨架生成编曲方案...")
        else:
            print(f"✅ 音频分析完成，旋律数据: {result.get('melody_csv')}")
            analysis_result = result
    else:
        print("ℹ️ 未提供音频，跳过音频分析，和弦进行基于骨架设计")

    # Step 2: 生成编曲方案
    composition_md = generate_chord_progression(
        analysis_result=analysis_result,
        basic_progression=basic_progression,
        title=args.title,
        enrichment=args.enrichment,
        form=args.form,
        tempo=args.tempo,
    )

    # Step 3: 保存
    output_path = args.output or str(SKILL_DIR / f"{args.title}.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(composition_md)

    print("\n" + "=" * 60)
    print("✅ 编曲方案生成完成！")
    print("=" * 60)
    print(f"\n输出文件: {output_path}")
    print(f"\n打开查看: {output_path}")

    return output_path


if __name__ == "__main__":
    main()