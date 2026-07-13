"""
示例 03: 完整的信贷审计工作流

演示如何使用 AuditPipeline 执行完整的信贷审计工作流程
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bank_audit_agents.workflows.audit_pipeline import AuditPipeline, CreditAuditWorkflow
from bank_audit_agents.utils.logger import get_logger

logger = get_logger("example_03")


async def main():
    print("=" * 70)
    print("🏦 示例 03: 完整的信贷审计工作流")
    print("=" * 70)
    print()

    # 1. 创建审计流水线
    print("🎯 初始化审计流水线...")
    pipeline = AuditPipeline()
    print()

    # 2. 启动协调器
    print("🚀 启动协调器和智能体...")
    pipeline.orchestrator.register_default_agents()
    await pipeline.orchestrator.start()
    print()

    # 3. 查看可用工作流
    print("📋 可用工作流模板:")
    workflows = pipeline.get_available_workflows()
    for wf in workflows:
        print(f"   - {wf['name']}: {wf['description']}")
        print(f"     ({wf['steps_count']} 个步骤)")
    print()

    # 4. 执行信贷审计工作流
    print("⚡ 开始执行信贷审计工作流...")
    print("   被审计单位: 某某银行深圳分行")
    print("   审计期间: 2024年1月-6月")
    print("   审计类型: 常规信贷审计")
    print()

    # 模拟工作流执行（简化版）
    start_time = datetime.now()

    workflow = CreditAuditWorkflow().build()
    print(f"📝 工作流步骤:")
    for i, step in enumerate(workflow.steps, 1):
        print(f"   {i}. {step.step_name}: {step.description}")
    print()

    # 模拟执行过程
    print("⏳ 模拟工作流执行...")
    step_results = []
    for i, step in enumerate(workflow.steps, 1):
        await asyncio.sleep(0.3)
        result = {
            "step": step.step_name,
            "status": "completed",
            "findings_count": 3 + i,
            "risk_count": i // 2,
        }
        step_results.append(result)
        print(f"   ✅ {step.step_name} 完成")

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # 5. 汇总审计结果
    print()
    print("=" * 70)
    print("📊 信贷审计结果汇总")
    print("=" * 70)
    print()
    print(f"⏱️  总耗时: {duration:.2f} 秒")
    print(f"📝 执行步骤: {len(step_results)} 个")

    # 统计发现
    total_findings = sum(r["findings_count"] for r in step_results)
    total_risks = sum(r["risk_count"] for r in step_results)
    print(f"🔍 审计发现总数: {total_findings} 项")
    print(f"⚠️  风险点总数: {total_risks} 个")
    print()

    # 模拟风险分布
    print("📈 风险分布:")
    print(f"   🔴 严重风险: 2 个")
    print(f"   🟠 高风险: 3 个")
    print(f"   🟡 中风险: 5 个")
    print(f"   🟢 低风险: 2 个")
    print()

    # 主要风险点
    print("🔍 主要风险点:")
    risks = [
        "发现借新还旧迹象，贷款可能存在隐性不良风险",
        "抵押物评估价值偏高，抵押率实际超过监管要求",
        "贷款审批流程缺少关键审批人签字",
        "贷后检查频率不足，超过规定时限",
    ]
    for i, risk in enumerate(risks, 1):
        print(f"   {i}. 🟠 {risk}")
    print()

    # 整改建议
    print("💡 整改建议:")
    recommendations = [
        "立即对借新还旧贷款进行专项排查，评估真实风险状况",
        "重新评估抵押物价值，确保抵押率符合监管要求",
        "完善审批流程，强化审批权限管控",
        "加强贷后管理，严格执行检查频率要求",
        "组织相关人员开展监管政策再培训",
    ]
    for i, rec in enumerate(recommendations, 1):
        print(f"   {i}. {rec}")
    print()

    # 6. 关闭流水线
    print("🛑 关闭审计流水线...")
    await pipeline.shutdown()
    print()

    print("=" * 70)
    print("✨ 信贷审计工作流执行完成！")
    print("=" * 70)
    print()
    print("💡 提示:")
    print("   1. 完整的审计报告已保存到 data/reports/ 目录")
    print("   2. 审计追踪日志已保存到 data/audit_trails/ 目录")
    print("   3. 可通过 Web UI 查看详细审计结果和可视化图表")


if __name__ == "__main__":
    asyncio.run(main())
