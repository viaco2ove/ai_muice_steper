"""md_parser.py - 轨道/工程 MD 解析与序列化（前后端共用逻辑，后端版）"""
import re


def parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta


def split_sections(md: str) -> dict:
    """按 ## 标题切片，返回 {title: body}"""
    sections = {}
    current = None
    buf = []
    for line in md.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = m.group(1).strip()
            buf = []
        else:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def parse_table(table_text: str) -> list:
    """解析 markdown 表格 -> list[dict]"""
    rows = []
    lines = [l for l in table_text.splitlines() if l.strip().startswith("|")]
    if len(lines) < 2:
        return rows
    headers = [c.strip() for c in lines[0].strip("|").split("|")]
    for line in lines[2:]:  # 跳过分隔行
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


def parse_track_md(md: str) -> dict:
    """解析单轨 MD -> 结构化 dict"""
    data = {"sections": {}, "info": {}, "chords": [], "notes_ref": ""}
    sections = split_sections(md)
    data["sections"] = sections
    # 轨道信息表
    if "轨道信息" in sections:
        for row in parse_table(sections["轨道信息"]):
            data["info"][row.get("字段", "")] = row.get("值", "")
    # 和弦进行
    if "和弦进行" in sections:
        data["chords"] = parse_table(sections["和弦进行"])
    return data


def serialize_track_md(data: dict) -> str:
    """结构化 dict -> MD（round-trip 友好，保留 sections 文本）"""
    # 简化：直接用 sections 文本拼装，info 表单独重建
    parts = []
    if data.get("info"):
        parts.append("## 轨道信息")
        parts.append("| 字段 | 值 |")
        parts.append("|------|-----|")
        for k, v in data["info"].items():
            parts.append(f"| {k} | {v} |")
        parts.append("")
    # 其余 section 原样回写
    for title, body in data.get("sections", {}).items():
        if title == "轨道信息":
            continue
        parts.append(f"## {title}")
        parts.append(body)
        parts.append("")
    return "\n".join(parts).strip() + "\n"


def parse_project_md(md: str) -> dict:
    """解析全局 project.md / song_engineer.md -> 结构化"""
    data = {"sections": split_sections(md)}
    if "基础信息" in data["sections"]:
        data["basic"] = {}
        for row in parse_table(data["sections"]["基础信息"]):
            data["basic"][row.get("字段", row.get("项目", ""))] = row.get("值", row.get("内容", ""))
    if "段落结构总览" in data["sections"]:
        data["sections_table"] = parse_table(data["sections"]["段落结构总览"])
    return data