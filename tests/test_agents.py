"""5 类业务 Agent 的行为测试。

此前只有 `base_agent` 与 `orchestrator` 有测试，业务 Agent 完全靠人工验证。
这里用 FakeLLM 注入（不发真实请求）覆盖三条主线：

1. 参数缺失 -> 明确失败（success=False + error），而不是抛异常
2. LLM 返回合规结果 -> 结果被正确解析并写入 findings / metadata
3. LLM 不可用或返回异常格式 -> 回退到各 Agent 的 mock 数据，任务仍成功
"""

import pytest

from bank_audit_agents.agents.compliance_checker import ComplianceCheckerAgent
from bank_audit_agents.agents.document_parser import DocumentParserAgent
from bank_audit_agents.agents.quality_and_coordinator import (
    QualityAuditorAgent,
    TaskCoordinatorAgent,
)
from bank_audit_agents.agents.report_writer import ReportWriterAgent
from bank_audit_agents.agents.risk_identifier import RiskIdentifierAgent
from bank_audit_agents.core.base_agent import Task


def make_task(**input_data) -> Task:
    return Task(task_type="test", description="单元测试任务", input_data=input_data)


# ---------------------------------------------------------------------------
# 文档解析智能体
# ---------------------------------------------------------------------------


async def test_document_parser_requires_path(fake_llm):
    agent = DocumentParserAgent()
    result = await agent.execute(make_task())

    assert result.success is False
    assert "document_path" in (result.error or "")


async def test_document_parser_reads_text_file(fake_llm, tmp_path):
    doc = tmp_path / "contract.txt"
    doc.write_text("借款金额：人民币 500 万元。借款人：某某科技有限公司。", encoding="utf-8")

    fake_llm.result = {"findings": [{"field": "loan_amount", "value": "5000000",
                                     "value_type": "currency", "confidence": 0.9,
                                     "location": "第1段"}]}

    agent = DocumentParserAgent()
    result = await agent.execute(make_task(document_path=str(doc)))

    assert result.success is True
    assert result.metadata["extraction"]["method"] == "plain_text"
    # 文档正文确实被送进了提示词（而不是只有路径占位串）
    assert "500 万元" in fake_llm.calls[0]["user_prompt"]


async def test_document_parser_reports_unreadable_document(fake_llm, tmp_path):
    """不支持的格式：任务仍完成，但 extraction 必须留下失败原因"""
    bad = tmp_path / "scan.bin"
    bad.write_bytes(b"\x00\x01\x02")

    fake_llm.use_fallback = True
    agent = DocumentParserAgent()
    result = await agent.execute(make_task(document_path=str(bad)))

    assert result.success is True
    extraction = result.metadata["extraction"]
    assert extraction["method"] == "failed"
    assert "不支持" in extraction["error"]


async def test_document_parser_falls_back_on_bad_llm_output(fake_llm, tmp_path):
    """LLM 返回无法解析的内容时回退到 mock，不应抛异常"""
    doc = tmp_path / "c.txt"
    doc.write_text("内容", encoding="utf-8")

    fake_llm.result = "这不是 JSON"

    agent = DocumentParserAgent()
    result = await agent.execute(make_task(document_path=str(doc)))

    assert result.success is True
    assert len(result.findings) > 0  # 回退到 _get_mock_findings()


async def test_document_parser_tools_are_resolvable(fake_llm):
    """get_tools 必须是已注册工具名，否则 resolve_tools 会用不上"""
    agent = DocumentParserAgent()
    resolved = [t.name for t in agent.resolve_tools()]

    assert resolved == agent.get_tools()
    assert "extract_document_text" in resolved


# ---------------------------------------------------------------------------
# 风险识别智能体
# ---------------------------------------------------------------------------


async def test_risk_identifier_requires_content(fake_llm):
    agent = RiskIdentifierAgent()
    result = await agent.execute(make_task())

    assert result.success is False
    assert "document_content" in (result.error or "")


async def test_risk_identifier_counts_levels(fake_llm):
    fake_llm.result = {
        "risks": [
            {"risk_id": "R1", "description": "集中度超标", "category": "credit",
             "level": "high", "likelihood": 0.8},
            {"risk_id": "R2", "description": "资料缺失", "category": "aml",
             "level": "low", "likelihood": 0.2},
            {"risk_id": "R3", "description": "未评级", "category": "other"},
        ]
    }

    agent = RiskIdentifierAgent()
    result = await agent.execute(
        make_task(document_content="某客户贷款集中度超监管上限", document_type="credit")
    )

    assert result.success is True
    assert result.metadata["total_risks"] == 3
    assert result.metadata["high_count"] == 1
    assert result.metadata["low_count"] == 1
    # 缺 level 字段的风险被补默认值，而不是让后续 KeyError
    assert all("level" in r for r in result.findings)


async def test_risk_identifier_falls_back_when_llm_errors(fake_llm):
    fake_llm.use_fallback = True
    agent = RiskIdentifierAgent()
    result = await agent.execute(make_task(document_content="任意内容"))

    assert result.success is True
    assert len(result.findings) > 0


# ---------------------------------------------------------------------------
# 合规检查智能体
# ---------------------------------------------------------------------------


async def test_compliance_checker_requires_content(fake_llm):
    agent = ComplianceCheckerAgent()
    result = await agent.execute(make_task())

    assert result.success is False


async def test_compliance_checker_returns_violations(fake_llm):
    fake_llm.result = {
        "violations": [
            {"violation_id": "V1", "category": "信贷", "framework": "流动资金贷款管理办法",
             "article": "第九条", "description": "未核实用途", "severity": "较重"},
        ]
    }

    agent = ComplianceCheckerAgent()
    result = await agent.execute(
        make_task(audit_content="贷款用途未核实", business_type="credit")
    )

    assert result.success is True
    assert len(result.findings) == 1
    assert result.findings[0]["violation_id"] == "V1"


async def test_compliance_checker_llm_error_falls_back(fake_llm):
    fake_llm.raise_exc = RuntimeError("LLM 超时")
    agent = ComplianceCheckerAgent()
    result = await agent.execute(make_task(audit_content="内容"))

    assert result.success is True
    assert len(result.findings) > 0


# ---------------------------------------------------------------------------
# 报告撰写智能体
# ---------------------------------------------------------------------------


async def test_report_writer_generates_markdown(fake_llm):
    fake_llm.result = {"recommendations": ["加强贷后管理", "补充尽调材料"]}

    agent = ReportWriterAgent()
    result = await agent.execute(
        make_task(
            findings=[
                {"category": "信贷管理", "risk_level": "high", "title": "集中度超标",
                 "description": "单一客户集中度超过监管上限"},
                {"category": "反洗钱", "risk_level": "medium", "title": "资料不全",
                 "description": "客户身份资料缺失"},
            ],
            audit_context={"audited_entity": "某分行"},
        )
    )

    assert result.success is True
    report = result.output_data["report_content"]
    assert "集中度超标" in report
    assert result.output_data["findings_count"] == 2
    assert result.output_data["report_format"] == "markdown"
    assert 0 <= result.output_data["compliance_score"] <= 100


async def test_report_writer_handles_empty_findings(fake_llm):
    fake_llm.use_fallback = True
    agent = ReportWriterAgent()
    result = await agent.execute(make_task(findings=[]))

    assert result.success is True
    assert result.output_data["findings_count"] == 0


async def test_report_writer_reports_failure_instead_of_raising(fake_llm):
    """输入结构非法时应返回失败结果，而不是让异常穿透到编排层"""
    fake_llm.use_fallback = True
    agent = ReportWriterAgent()
    result = await agent.execute(make_task(findings="not-a-list"))

    assert result.success is False
    assert result.error


# ---------------------------------------------------------------------------
# 质量审计智能体
# ---------------------------------------------------------------------------


async def test_quality_auditor_uses_llm_scores(fake_llm):
    fake_llm.result = {
        "scores": {"accuracy": 92.0, "completeness": 60.0},
        "issues": [{"issue_id": "Q1", "level": "major", "category": "完整性",
                    "description": "缺少证据", "suggestion": "补充底稿"}],
    }

    agent = QualityAuditorAgent()
    result = await agent.execute(
        make_task(content={"summary": "报告内容"}, source_agent="report_writer")
    )

    assert result.success is True
    # 分数落在 output_data（metadata 留给链路追踪类信息）
    assert result.output_data["detailed_scores"]["accuracy"] == 92.0
    assert result.output_data["overall_score"] > 0


async def test_quality_auditor_rule_based_fallback(fake_llm):
    fake_llm.use_fallback = True
    agent = QualityAuditorAgent()
    result = await agent.execute(make_task(content={"summary": "报告内容"}))

    assert result.success is True
    assert set(result.output_data["detailed_scores"]) == {
        "completeness", "accuracy", "consistency", "clarity", "compliance"
    }
    assert result.output_data["pass_threshold"] is True


# ---------------------------------------------------------------------------
# 任务协调智能体（纯规则，不依赖 LLM）
# ---------------------------------------------------------------------------


async def test_task_coordinator_decomposes_project(fake_llm):
    agent = TaskCoordinatorAgent()
    result = await agent.execute(
        make_task(project_requirements={"workflow_type": "credit_audit", "priority": "high"})
    )

    assert result.success is True
    assert len(result.findings) > 0  # 执行计划
    assert "子任务" in result.summary


@pytest.mark.parametrize("workflow_type", ["credit_audit", "compliance_audit", "financial_audit"])
async def test_task_coordinator_handles_all_workflows(fake_llm, workflow_type):
    agent = TaskCoordinatorAgent()
    result = await agent.execute(
        make_task(project_requirements={"workflow_type": workflow_type})
    )
    assert result.success is True
