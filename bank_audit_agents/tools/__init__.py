"""
工具层

- :mod:`base`           工具抽象与注册表
- :mod:`rules`          审计规则引擎（内置常用监管指标规则）
- :mod:`document_tools` 文档结构化抽取（金额 / 比率 / 日期 / 主体 / 条款）
"""

from bank_audit_agents.tools.base import (
    ToolResult,
    ToolRegistry,
    ToolSpec,
    get_default_registry,
    reset_default_registry,
    tool,
)
from bank_audit_agents.tools.rules import (
    DEFAULT_RULES,
    AuditRule,
    RuleCategory,
    RuleEngine,
    RuleFinding,
    RuleSeverity,
    build_default_engine,
)
from bank_audit_agents.tools.document_tools import (
    extract_amounts,
    extract_dates,
    extract_parties,
    extract_percentages,
    split_sections,
    summarize_document,
)

__all__ = [
    # 工具抽象
    "ToolResult",
    "ToolRegistry",
    "ToolSpec",
    "get_default_registry",
    "reset_default_registry",
    "tool",
    # 规则引擎
    "AuditRule",
    "RuleCategory",
    "RuleEngine",
    "RuleFinding",
    "RuleSeverity",
    "DEFAULT_RULES",
    "build_default_engine",
    # 文档工具
    "extract_amounts",
    "extract_percentages",
    "extract_dates",
    "extract_parties",
    "split_sections",
    "summarize_document",
]
