"""审计工作流测试。

覆盖两个层面：
1. 模板结构（步骤、依赖、输入映射是否自洽）
2. 端到端执行（编排器 + FakeLLM），验证依赖传递与结果聚合

第二条是重点：工作流此前**完全没有测试**，而它的步骤依赖、
``register_default_agents`` 的覆盖面、输入映射只有真跑才能验证。
"""

import pytest

from bank_audit_agents.core.orchestrator import AgentOrchestrator
from bank_audit_agents.workflows.audit_pipeline import (
    ComplianceAuditWorkflow,
    CreditAuditWorkflow,
    FinancialAuditWorkflow,
    WorkflowExecutor,
    WorkflowStatus,
)

ALL_WORKFLOWS = [CreditAuditWorkflow, ComplianceAuditWorkflow, FinancialAuditWorkflow]


# ---------------------------------------------------------------------------
# 模板结构
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("factory", ALL_WORKFLOWS, ids=lambda f: f.__name__)
def test_workflow_build_returns_steps(factory):
    workflow = factory().build()

    assert workflow.steps, "工作流不应为空"
    assert any(step.depends_on == [] for step in workflow.steps), "必须有一个起始步骤"
    # step_id 唯一
    ids = [s.step_id for s in workflow.steps]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("factory", ALL_WORKFLOWS, ids=lambda f: f.__name__)
def test_workflow_dependencies_exist(factory):
    """依赖指向的步骤必须存在，否则执行时会静默拿不到上游输出"""
    workflow = factory().build()
    known = {s.step_id for s in workflow.steps}

    for step in workflow.steps:
        for dep in step.depends_on:
            assert dep in known, f"{step.step_id} 依赖了不存在的步骤 {dep}"


def test_credit_workflow_maps_report_inputs():
    workflow = CreditAuditWorkflow().build()
    report_step = workflow.get_step("report_generation")

    assert report_step is not None
    # 报告生成必须拿到上游的风险与合规结果
    assert "risk_identification.findings" in report_step.input_mapping.values()
    assert "compliance_check.findings" in report_step.input_mapping.values()


def test_workflow_to_dict_is_serializable():
    import json

    data = CreditAuditWorkflow().build().to_dict()
    json.dumps(data, ensure_ascii=False)  # 不应抛异常
    assert data["name"] == "信贷审计工作流"


# ---------------------------------------------------------------------------
# 端到端执行
# ---------------------------------------------------------------------------


def _make_orchestrator(fake_llm):
    """注册默认智能体（LLM 全部走 mock 回退），并启动编排器"""
    orchestrator = AgentOrchestrator()
    orchestrator.register_default_agents()
    return orchestrator


async def test_default_agents_cover_all_workflow_agents(fake_llm):
    """每种工作流步骤声明的 target_agent_type 都必须有对应智能体。

    曾出现过 `register_default_agents` 漏注册 report_writer，
    而信贷工作流第 4 步正需要它 —— 这个用例就是防止该问题复发。
    """
    fake_llm.use_fallback = True
    orchestrator = _make_orchestrator(fake_llm)

    needed = set()
    for factory in ALL_WORKFLOWS:
        for step in factory().build().steps:
            needed.add(step.target_agent_type)

    missing = [t for t in needed if not orchestrator.get_agents_by_type(t)]
    assert not missing, f"默认智能体缺少以下类型: {missing}"


@pytest.mark.slow
async def test_credit_workflow_end_to_end(fake_llm, tmp_path):
    """完整跑一遍信贷审计工作流（LLM 走 mock 回退）"""
    fake_llm.use_fallback = True

    doc = tmp_path / "loan.txt"
    doc.write_text("借款人：某某科技有限公司。贷款金额：人民币 500 万元。", encoding="utf-8")

    orchestrator = _make_orchestrator(fake_llm)
    await orchestrator.start()
    try:
        executor = WorkflowExecutor(orchestrator)
        result = await executor.execute(
            CreditAuditWorkflow().build(),
            input_data={"document_path": str(doc), "document_type": "loan_contract"},
        )
    finally:
        await orchestrator.stop()

    assert result.success is True, f"工作流失败: {result.error_message}"
    assert result.status == WorkflowStatus.COMPLETED
    assert set(result.step_results) >= {
        "document_parsing",
        "risk_identification",
        "compliance_check",
        "report_generation",
        "quality_audit",
    }
    assert result.aggregated_findings, "应聚合出各步骤的发现项"
    assert result.final_report, "应产出最终报告"


@pytest.mark.slow
async def test_workflow_failure_is_captured_not_raised(fake_llm):
    """步骤执行失败时，工作流返回 FAILED 结果而不是把异常抛给调用方"""
    fake_llm.use_fallback = True

    orchestrator = _make_orchestrator(fake_llm)
    await orchestrator.start()
    try:
        executor = WorkflowExecutor(orchestrator)
        # 缺少 document_path，文档解析智能体会判定失败（该步骤 required=True）
        result = await executor.execute(
            CreditAuditWorkflow().build(), input_data={"document_type": "unknown"}
        )
    finally:
        await orchestrator.stop()

    assert result.success is False
    assert result.status == WorkflowStatus.FAILED
    assert result.error_message
    assert result.end_time is not None  # 失败也要记录结束时间，便于统计耗时
