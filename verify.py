#!/usr/bin/env python3
"""
银行审计多智能体平台 - 系统验证脚本

运行此脚本验证所有模块是否正确安装和导入，确保系统环境配置正确。

验证流程：
1. 验证 Python 版本（需要 >= 3.10）
2. 验证核心模块导入
3. 验证智能体实例化
4. 验证核心功能（Task、AgentResult）
5. 验证协调器
6. 验证工作流模板

运行方式：
    python verify.py

设计目的：
- 帮助开发者快速验证环境配置
- 在部署前检查所有依赖是否正确安装
- 提供清晰的错误信息定位问题
- 作为 CI/CD 流程的验证步骤
"""

# 导入必要的库
import sys
import asyncio
from datetime import datetime

# ==================== 打印标题 ====================
print("=" * 70)
print("🏦 银行审计多智能体平台 - 系统验证")
print("=" * 70)
print(f"⏰  执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# ==================== 步骤 1: 验证 Python 版本 ====================
print("📋 第 1 步: 验证 Python 版本")
python_version = sys.version_info
print(f"   Python 版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
# 检查 Python 版本是否符合要求（>= 3.10）
if python_version >= (3, 10):
    print("   ✅ Python 版本符合要求 (>= 3.10)")
else:
    print("   ❌ Python 版本过低，需要 3.10+")
print()

# ==================== 步骤 2: 验证核心模块导入 ====================
print("📋 第 2 步: 验证核心模块导入")

# 定义需要验证的模块列表（模块名称, 模块路径）
modules_to_test = [
    ("配置模块", "bank_audit_agents.config.settings"),
    ("日志模块", "bank_audit_agents.utils.logger"),
    ("基类模块", "bank_audit_agents.core.base_agent"),
    ("协调器模块", "bank_audit_agents.core.orchestrator"),
    ("文档解析智能体", "bank_audit_agents.agents.document_parser"),
    ("风险识别智能体", "bank_audit_agents.agents.risk_identifier"),
    ("合规检查智能体", "bank_audit_agents.agents.compliance_checker"),
    ("报告撰写智能体", "bank_audit_agents.agents.report_writer"),
    ("质量和协调智能体", "bank_audit_agents.agents.quality_and_coordinator"),
    ("工作流模块", "bank_audit_agents.workflows.audit_pipeline"),
]

success_count = 0
fail_count = 0

# 逐个验证模块导入
for name, module_path in modules_to_test:
    try:
        __import__(module_path)  # 尝试导入模块
        print(f"   ✅ {name}")
        success_count += 1
    except Exception as e:
        print(f"   ❌ {name}: {str(e)}")
        fail_count += 1

print(f"\n   导入结果: {success_count} 成功, {fail_count} 失败")
print()

# ==================== 步骤 3: 验证智能体实例化 ====================
print("📋 第 3 步: 验证智能体实例化")

try:
    # 导入所有智能体类
    from bank_audit_agents.agents import (
        DocumentParserAgent,      # 文档解析智能体
        RiskIdentifierAgent,      # 风险识别智能体
        ComplianceCheckerAgent,   # 合规检查智能体
        ReportWriterAgent,        # 报告撰写智能体
        QualityAuditorAgent,      # 质量审核智能体
        TaskCoordinatorAgent,     # 任务协调智能体
    )

    # 定义智能体类列表
    agent_classes = [
        ("文档解析智能体", DocumentParserAgent),
        ("风险识别智能体", RiskIdentifierAgent),
        ("合规检查智能体", ComplianceCheckerAgent),
        ("报告撰写智能体", ReportWriterAgent),
        ("质量审核智能体", QualityAuditorAgent),
        ("任务协调智能体", TaskCoordinatorAgent),
    ]

    agent_instances = []
    # 逐个实例化智能体
    for name, agent_class in agent_classes:
        try:
            agent = agent_class()  # 创建智能体实例
            agent_instances.append(agent)
            print(f"   ✅ {name}: {agent.agent_id}")
        except Exception as e:
            print(f"   ❌ {name}: {str(e)}")

    print(f"\n   成功实例化 {len(agent_instances)} 个智能体")

except Exception as e:
    print(f"   ❌ 智能体导入失败: {str(e)}")
print()

# ==================== 步骤 4: 验证核心功能 ====================
print("📋 第 4 步: 验证核心功能")

try:
    from bank_audit_agents.core.base_agent import Task, AgentResult, TaskStatus

    # 测试任务对象创建
    task = Task(
        task_type="test",
        description="测试任务",
        input_data={"test": "data"},
    )
    print(f"   ✅ 任务创建成功: {task.task_id}")

    # 测试任务状态变更流程
    task.start()
    assert task.status == TaskStatus.IN_PROGRESS
    task.complete({"result": "ok"})
    assert task.status == TaskStatus.COMPLETED
    print(f"   ✅ 任务状态变更正常")

    # 测试执行结果对象创建
    result = AgentResult(
        agent_id="test-agent",
        agent_type="test",
        success=True,
        summary="测试成功",
        confidence_score=0.95,
    )
    print(f"   ✅ AgentResult 创建成功, 置信度: {result.confidence_score}")

except Exception as e:
    print(f"   ❌ 核心功能验证失败: {str(e)}")
print()

# ==================== 步骤 5: 验证协调器 ====================
print("📋 第 5 步: 验证协调器")

try:
    from bank_audit_agents.core.orchestrator import AgentOrchestrator

    # 创建协调器实例
    orchestrator = AgentOrchestrator()

    # 注册智能体到协调器
    orchestrator.register_agent(DocumentParserAgent())
    orchestrator.register_agent(RiskIdentifierAgent())

    # 获取协调器状态
    status = orchestrator.get_status()
    print(f"   ✅ 协调器创建成功")
    print(f"   ✅ 已注册智能体: {status['agents']['total_count']} 个")

except Exception as e:
    print(f"   ❌ 协调器验证失败: {str(e)}")
print()

# ==================== 步骤 6: 验证工作流模板 ====================
print("📋 第 6 步: 验证工作流模板")

try:
    from bank_audit_agents.workflows.audit_pipeline import (
        CreditAuditWorkflow,        # 信贷审计工作流
        ComplianceAuditWorkflow,    # 合规审计工作流
        FinancialAuditWorkflow,     # 财务审计工作流
    )

    # 定义工作流类列表
    workflows = [
        ("信贷审计工作流", CreditAuditWorkflow),
        ("合规审计工作流", ComplianceAuditWorkflow),
        ("财务审计工作流", FinancialAuditWorkflow),
    ]

    # 逐个构建工作流并验证
    for name, wf_class in workflows:
        wf = wf_class().build()  # 构建工作流
        print(f"   ✅ {name}: {len(wf.steps)} 个步骤")

except Exception as e:
    print(f"   ❌ 工作流验证失败: {str(e)}")
print()

# ==================== 验证总结 ====================
print("=" * 70)
print("📊 验证总结")
print("=" * 70)
print()

# 根据验证结果给出不同的提示
if fail_count == 0:
    print("✅ 所有模块验证通过！")
    print()
    print("🚀 系统已准备就绪，可以执行以下操作:")
    print()
    print("   1. 启动 Web UI:")
    print("      streamlit run bank_audit_agents/ui/dashboard.py")
    print()
    print("   2. 运行示例:")
    print("      python examples/01_single_agent.py")
    print("      python examples/02_orchestrator.py")
    print("      python examples/03_credit_audit_workflow.py")
    print()
    print("   3. 运行测试:")
    print("      pytest tests/")
    print()
else:
    print(f"⚠️  发现 {fail_count} 个模块导入失败")
    print("请检查依赖是否已安装: poetry install")
    print()

print("=" * 70)
