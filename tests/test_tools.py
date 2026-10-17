"""
工具层测试：注册表 + 文档抽取工具 + Agent 工具方法
"""

import pytest

from bank_audit_agents.core.base_agent import AgentResult, AgentType, BaseAgent, Task
from bank_audit_agents.tools import (
    ToolRegistry,
    ToolSpec,
    extract_amounts,
    extract_dates,
    extract_parties,
    extract_percentages,
    get_default_registry,
    split_sections,
    summarize_document,
)


# ---------------- ToolRegistry ----------------


def _dummy_tool(value=1):
    def _fn(x: int = 1):
        return x * value

    return _fn


def test_registry_register_and_get():
    registry = ToolRegistry()
    spec = ToolSpec("dummy", "测试工具", _dummy_tool(), category="test")
    registry.register(spec)
    assert registry.get("dummy") is spec
    assert registry.has("dummy")
    assert "dummy" in registry


def test_registry_rejects_duplicate_without_override():
    registry = ToolRegistry()
    registry.register(ToolSpec("dup", "d", _dummy_tool()))
    with pytest.raises(ValueError, match="工具已注册"):
        registry.register(ToolSpec("dup", "d", _dummy_tool()))


def test_registry_override_allows_replacement():
    registry = ToolRegistry()
    registry.register(ToolSpec("dup", "d", _dummy_tool(1)))
    registry.register(ToolSpec("dup", "d2", _dummy_tool(2)), override=True)
    assert registry.get("dup").description == "d2"


def test_registry_call_success_and_failure():
    registry = ToolRegistry()

    def good(x: int = 2):
        return x + 1

    def bad():
        raise RuntimeError("解析失败")

    registry.register(ToolSpec("good", "正常工具", good))
    registry.register(ToolSpec("bad", "会失败的工具", bad))

    ok = registry.call("good", x=2)
    assert ok.success is True
    assert ok.output == 3

    failed = registry.call("bad")
    assert failed.success is False
    assert "解析失败" in failed.error


def test_registry_call_missing_tool_returns_failure_not_exception():
    registry = ToolRegistry()
    result = registry.call("not_exist")
    assert result.success is False
    assert "工具未注册" in result.error


def test_registry_resolve_skips_unregistered_names():
    registry = ToolRegistry()
    registry.register(ToolSpec("a", "A", _dummy_tool()))
    resolved = registry.resolve(["a", "b"])
    assert [t.name for t in resolved] == ["a"]


def test_registry_list_and_names_filter_by_category():
    registry = ToolRegistry()
    registry.register(ToolSpec("x", "X", _dummy_tool(), category="doc"))
    registry.register(ToolSpec("y", "Y", _dummy_tool(), category="rules"))
    assert registry.names("doc") == ["x"]
    assert len(registry) == 2


def test_default_registry_contains_builtin_tools():
    registry = get_default_registry()
    names = registry.names()
    # 文档工具
    assert "extract_amounts" in names
    assert "summarize_document" in names
    # 规则工具
    assert "audit_rule_check" in names
    assert "rule_library_lookup" in names


# ---------------- 金额抽取 ----------------


def test_extract_amounts_converts_units_to_yuan():
    text = "贷款金额 1.5亿元，保证金 2,000万元，手续费 300元。"
    amounts = extract_amounts(text)
    values = {a["unit"]: a["value"] for a in amounts}
    assert values["亿元"] == pytest.approx(1.5e8)
    assert values["万元"] == pytest.approx(2_000e4)
    assert values["元"] == pytest.approx(300.0)


def test_extract_amounts_handles_thousand_separator():
    amounts = extract_amounts("合计 12,345,678 元")
    assert amounts[0]["amount"] == pytest.approx(12345678.0)


def test_extract_amounts_returns_empty_when_nothing_found():
    assert extract_amounts("本文件不包含任何金额信息") == []


def test_extract_amounts_records_position_and_raw():
    amounts = extract_amounts("本金 100万元")
    assert amounts[0]["raw"] == "100万元"
    assert amounts[0]["position"] >= 0


# ---------------- 比率与日期 ----------------


def test_extract_percentages_supports_fullwidth():
    text = "不良率 5.5%，拨备覆盖率 150％"
    values = [p["value"] for p in extract_percentages(text)]
    assert values == pytest.approx([5.5, 150.0])


def test_extract_dates_normalizes_multiple_formats():
    text = "签署于2024年3月15日，到期日 2025/12/31，另有 2023年8月。"
    dates = extract_dates(text)
    normalized = [d["normalized"] for d in dates]
    assert "2024-03-15" in normalized
    assert "2025-12-31" in normalized
    assert "2023-08" in normalized


def test_extract_dates_rejects_invalid_month():
    assert extract_dates("2024年13月5日") == []


# ---------------- 主体与分段 ----------------


def test_extract_parties_identifies_roles():
    text = "甲方：某某银行股份有限公司\n乙方：张三\n保证人：李四"
    parties = extract_parties(text)
    roles = {p["role"] for p in parties}
    assert roles == {"甲方", "乙方", "保证人"}
    names = {p["name"] for p in parties}
    assert "某某银行股份有限公司" in names
    assert "张三" in names


def test_split_sections_by_article_number():
    text = "第一条 总则\n第二条 贷款金额\n第三条 还款方式"
    sections = split_sections(text)
    assert len(sections) == 3
    assert sections[0]["content"].startswith("第一条")


def test_split_sections_returns_single_block_without_numbering():
    sections = split_sections("这是一段没有编号的说明文字。")
    assert len(sections) == 1


# ---------------- 综合摘要 ----------------


def test_summarize_document_aggregates_everything():
    text = """
    借款合同
    甲方：某某银行股份有限公司
    第一条 贷款金额为 5,000万元。
    第二条 年利率 4.35%，期限至 2026年6月30日。
    """
    summary = summarize_document(text)
    assert summary["amount_count"] >= 1
    assert summary["total_amount_yuan"] == pytest.approx(5_000e4)
    assert 4.35 in summary["percentages"]
    assert "2026-06-30" in summary["dates"]
    assert any(p["role"] == "甲方" for p in summary["parties"])
    assert summary["section_count"] >= 2


def test_summarize_document_on_empty_text():
    summary = summarize_document("")
    assert summary["amount_count"] == 0
    assert summary["total_amount_yuan"] == 0


# ---------------- Agent 与工具层的衔接 ----------------


class ToolUsingAgent(BaseAgent):
    """覆盖 get_tools 声明自己关心的工具"""

    def __init__(self, agent_id=None):
        super().__init__(AgentType.DOCUMENT_PARSER, agent_id)

    def get_system_prompt(self) -> str:
        return "测试智能体"

    def get_tools(self):
        return ["summarize_document", "audit_rule_check", "not_implemented_tool"]

    async def execute(self, task: Task) -> AgentResult:
        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            success=True,
            summary="ok",
        )


class DefaultToolsAgent(BaseAgent):
    """不覆盖 get_tools，走基类默认实现"""

    def __init__(self, agent_id=None):
        super().__init__(AgentType.DOCUMENT_PARSER, agent_id)

    def get_system_prompt(self) -> str:
        return "测试智能体"

    async def execute(self, task: Task) -> AgentResult:
        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            success=True,
            summary="ok",
        )


def test_agent_default_tools_come_from_registry():
    agent = DefaultToolsAgent()
    names = agent.get_tools()
    assert isinstance(names, list)
    assert "extract_amounts" in names


def test_agent_resolve_tools_skips_unimplemented_names():
    agent = ToolUsingAgent()
    resolved = agent.resolve_tools()
    names = [t.name for t in resolved]
    # 真实存在的两个被解析，不存在的被跳过而非报错
    assert names == ["summarize_document", "audit_rule_check"]


def test_agent_call_tool_works_end_to_end():
    agent = ToolUsingAgent()
    result = agent.call_tool("extract_amounts", text="贷款 100万元")
    assert result.success is True
    assert result.output[0]["value"] == pytest.approx(1_000_000.0)


def test_agent_call_unknown_tool_returns_failure():
    agent = ToolUsingAgent()
    result = agent.call_tool("definitely_missing")
    assert result.success is False


def test_agent_describe_tools_returns_serializable_dicts():
    agent = ToolUsingAgent()
    described = agent.describe_tools()
    assert described
    assert all("name" in d and "description" in d for d in described)
