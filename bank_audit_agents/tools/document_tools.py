"""
文档解析工具（纯标准库实现）

定位：不是完整的 PDF / 扫描件解析（那需要 OCR 和专业库，属于 TODO），
而是**从已经取到文本之后的结构化抽取**——金额、比率、日期、当事主体、条款分段，
这些是审计文档核对中最常复用、也最容易写出 bug 的部分。

所有工具都注册到默认工具注册表，Agent 可通过 ``get_tools()`` 声明后调用。
"""

import re
from typing import Any, Dict, List

from bank_audit_agents.tools.base import tool

__all__ = [
    "extract_amounts",
    "extract_percentages",
    "extract_dates",
    "extract_parties",
    "split_sections",
    "summarize_document",
    "AMOUNT_UNIT_FACTORS",
]

# 金额单位换算到「元」
AMOUNT_UNIT_FACTORS: Dict[str, float] = {
    "元": 1.0,
    "万元": 1e4,
    "百万元": 1e6,
    "千万元": 1e7,
    "亿元": 1e8,
}

_AMOUNT_PATTERN = re.compile(
    r"(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*"
    r"(亿元|千万元|百万元|万元|元)"
)

_PERCENT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*[％%]")

_DATE_PATTERNS = [
    # 2024年3月15日 / 2024 年 3 月 15 日
    re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
    # 2024-03-15 / 2024/03/15
    re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})"),
    # 2024年3月（缺日）
    re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月(?!\s*\d)"),
]

_PARTY_PATTERN = re.compile(
    r"(甲方|乙方|丙方|借款人|贷款人|授信申请人|保证人|抵押人|出质人|债务人|债权人)"
    r"\s*[:：]?\s*([^\s，,。;；：:\n]{2,40})"
)

_SECTION_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:"
    r"第[一二三四五六七八九十百零〇\d]+条"
    r"|[一二三四五六七八九十]+[、．.]"
    r"|\d+(?:[、．.])"
    r"|[（(]\d+[)）]"
    r")"
)


def _to_float(raw: str) -> float:
    return float(raw.replace(",", ""))


@tool(
    name="extract_amounts",
    description="从文本中抽取金额，支持元/万元/亿元等单位，并换算为以元为基准的数值",
    category="document",
    parameters={"text": "待抽取的文本"},
)
def extract_amounts(text: str) -> List[Dict[str, Any]]:
    """抽取文本中的金额

    Returns:
        每项包含 raw（原文）、amount（按单位记的数值）、unit（单位）、
        value（换算成元）、position（字符下标）
    """
    results: List[Dict[str, Any]] = []
    for match in _AMOUNT_PATTERN.finditer(text):
        raw_number, unit = match.group(1), match.group(2)
        try:
            amount = _to_float(raw_number)
        except ValueError:  # pragma: no cover - 正则已保证可解析
            continue
        factor = AMOUNT_UNIT_FACTORS.get(unit, 1.0)
        results.append(
            {
                "raw": match.group(0).strip(),
                "amount": amount,
                "unit": unit,
                "value": amount * factor,
                "position": match.start(),
            }
        )
    return results


@tool(
    name="extract_percentages",
    description="抽取文本中的百分比数值（支持全角 ％ 与半角 %）",
    category="document",
    parameters={"text": "待抽取的文本"},
)
def extract_percentages(text: str) -> List[Dict[str, Any]]:
    """抽取百分比，返回 value（数字，如 12.5 表示 12.5%）与原文"""
    results: List[Dict[str, Any]] = []
    for match in _PERCENT_PATTERN.finditer(text):
        try:
            value = float(match.group(1))
        except ValueError:  # pragma: no cover
            continue
        results.append(
            {
                "raw": match.group(0).strip(),
                "value": value,
                "position": match.start(),
            }
        )
    return results


@tool(
    name="extract_dates",
    description="抽取文本中的日期，统一输出 YYYY-MM-DD 格式（缺日时输出 YYYY-MM）",
    category="document",
    parameters={"text": "待抽取的文本"},
)
def extract_dates(text: str) -> List[Dict[str, Any]]:
    """抽取日期并归一化"""
    results: List[Dict[str, Any]] = []
    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3)) if match.lastindex and match.lastindex >= 3 else None
            if not (1 <= month <= 12):
                continue
            if day is not None and not (1 <= day <= 31):
                continue
            normalized = f"{year:04d}-{month:02d}" + (f"-{day:02d}" if day else "")
            results.append(
                {
                    "raw": match.group(0).strip(),
                    "normalized": normalized,
                    "year": year,
                    "month": month,
                    "day": day,
                    "position": match.start(),
                }
            )
    # 按出现位置排序并去重（同一段文字可能被多个模式命中）
    seen = set()
    unique: List[Dict[str, Any]] = []
    for item in sorted(results, key=lambda x: x["position"]):
        if item["normalized"] in seen:
            continue
        seen.add(item["normalized"])
        unique.append(item)
    return unique


@tool(
    name="extract_parties",
    description="抽取合同/协议中的当事主体（甲方、乙方、借款人、保证人等）",
    category="document",
    parameters={"text": "待抽取的文本"},
)
def extract_parties(text: str) -> List[Dict[str, Any]]:
    """抽取当事主体，返回角色与名称"""
    results: List[Dict[str, Any]] = []
    for match in _PARTY_PATTERN.finditer(text):
        role, name = match.group(1), match.group(2).strip()
        # 去掉名称尾部常见的标点
        name = re.sub(r"[（(].*$", "", name).strip()
        if not name:
            continue
        results.append({"role": role, "name": name, "position": match.start()})
    return results


@tool(
    name="split_sections",
    description="按条款编号切分文档（第X条 / 一、 / 1. / （1）），返回分段列表",
    category="document",
    parameters={"text": "待切分的文本"},
)
def split_sections(text: str) -> List[Dict[str, Any]]:
    """按条款编号切分文档"""
    marks = [m.start() for m in _SECTION_PATTERN.finditer(text)]
    if not marks:
        stripped = text.strip()
        return [{"index": 0, "content": stripped}] if stripped else []

    sections: List[Dict[str, Any]] = []
    # 编号之前的引导段落（如标题）单独成段
    if marks[0] > 0 and text[: marks[0]].strip():
        sections.append({"index": 0, "content": text[: marks[0]].strip()})

    for i, start in enumerate(marks):
        end = marks[i + 1] if i + 1 < len(marks) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append({"index": len(sections), "content": content})
    return sections


@tool(
    name="summarize_document",
    description="对文档做一次综合抽取：金额、比率、日期、当事主体与条款分段统计",
    category="document",
    parameters={"text": "待分析的文本"},
)
def summarize_document(text: str) -> Dict[str, Any]:
    """综合抽取，返回可直接进入审计上下文的结构化摘要"""
    amounts = extract_amounts(text)
    percentages = extract_percentages(text)
    dates = extract_dates(text)
    parties = extract_parties(text)
    sections = split_sections(text)

    total_amount = sum(a["value"] for a in amounts)
    return {
        "length": len(text),
        "section_count": len(sections),
        "amount_count": len(amounts),
        "total_amount_yuan": total_amount,
        "max_amount_yuan": max((a["value"] for a in amounts), default=0.0),
        "percentages": [p["value"] for p in percentages],
        "dates": [d["normalized"] for d in dates],
        "parties": [{"role": p["role"], "name": p["name"]} for p in parties],
        "amounts": amounts,
    }
