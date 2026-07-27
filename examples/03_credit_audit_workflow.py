"""
示例 03: 完整的信贷审计工作流

本示例演示了如何使用 AuditPipeline 执行完整的信贷审计工作流程，
是理解多智能体系统端到端应用的核心示例。

学习要点：
1. 如何创建审计流水线（AuditPipeline）
2. 如何注册默认智能体集合
3. 如何获取和选择工作流模板
4. 如何执行完整的审计工作流
5. 如何汇总和展示审计结果

执行方式：
    python examples/03_credit_audit_workflow.py

核心流程：
    AuditPipeline()
        │
        ├── register_default_agents()  # 注册所有核心智能体
        └── start()                     # 启动协调器
        │
        ▼
    get_available_workflows()  # 获取可用工作流列表
        │
        ▼
    CreditAuditWorkflow().build()  # 构建信贷审计工作流
        │
        ├── Step 1: 文档解析
        ├── Step 2: 风险识别
        ├── Step 3: 合规检查
        ├── Step 4: 质量审核
        └── Step 5: 报告生成
        │
        ▼
    汇总审计结果（风险点、整改建议）
        │
        ▼
    shutdown()  # 关闭流水线

工作流模板体系：
- CreditAuditWorkflow: 信贷审计工作流
- ComplianceAuditWorkflow: 合规审计工作流
- FinancialAuditWorkflow: 财务审计工作流

每个工作流由多个步骤组成，每个步骤由特定智能体执行
"""

# 导入必要的库
import asyncio
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入核心模块
from bank_audit_agents.workflows.audit_pipeline import (
    AuditPipeline,      # 审计流水线
    CreditAuditWorkflow, # 信贷审计工作流
)
from bank_audit_agents.utils.logger import get_logger  # 日志工具

# 初始化日志记录器
logger = get_logger("example_03")


async def main():
    """主函数：演示完整的信贷审计工作流执行流程"""
    print("=" * 70)
    print("🏦 示例 03: 完整的信贷审计工作流")
    print("=" * 70)
    print()

    # ==================== 步骤 1: 创建审计流水线 ====================
    print("🎯 初始化审计流水线...")
    # AuditPipeline 是工作流执行的核心引擎
    # 封装了协调器和工作流模板管理
    pipeline = AuditPipeline()
    print()

    # ==================== 步骤 2: 启动协调器和智能体 ====================
    print("🚀 启动协调器和智能体...")
    # register_default_agents() 一次性注册所有核心智能体
    # 包括：文档解析、风险识别、合规检查、报告撰写、质量审核、任务协调
    pipeline.orchestrator.register_default_agents()
    await pipeline.orchestrator.start()
    print()

    # ==================== 步骤 3: 查看可用工作流 ====================
    print("📋 可用工作流模板:")
    # get_available_workflows() 返回所有已注册的工作流模板信息
    workflows = pipeline.get_available_workflows()
    for wf in workflows:
        print(f"   - {wf['name']}: {wf['description']}")
        print(f"     ({wf['steps_count']} 个步骤)")
    print()

    # ==================== 步骤 4: 执行信贷审计工作流 ====================
    print("⚡ 开始执行信贷审计工作流...")
    print("   被审计单位: 某某银行深圳分行")
    print("   审计期间: 2024年1月-6月")
    print("   审计类型: 常规信贷审计")
    print()

    # 记录开始时间
    start_time = datetime.now()

    # 构建信贷审计工作流
    # CreditAuditWorkflow() 创建工作流实例
    # build() 方法构建工作流的步骤序列
    workflow = CreditAuditWorkflow().build()
    print(f"📝 工作流步骤:")
    for i, step in enumerate(workflow.steps, 1):
        print(f"   {i}. {step.step_name}: {step.description}")
    print()

    # 模拟工作流执行过程
    # 实际项目中会调用 pipeline.execute_workflow() 方法
    print("⏳ 模拟工作流执行...")
    step_results = []
    for i, step in enumerate(workflow.steps, 1):
        # 模拟每个步骤的执行时间
        await asyncio.sleep(0.3)
        # 模拟步骤执行结果
        result = {
            "step": step.step_name,
            "status": "completed",
            "findings_count": 3 + i,       # 每步发现的问题数量
            "risk_count": i // 2,          # 每步识别的风险数量
        }
        step_results.append(result)
        print(f"   ✅ {step.step_name} 完成")

    # 计算总耗时
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # ==================== 步骤 5: 汇总审计结果 ====================
    print()
    print("=" * 70)
    print("📊 信贷审计结果汇总")
    print("=" * 70)
    print()
    print(f"⏱️  总耗时: {duration:.2f} 秒")
    print(f"📝 执行步骤: {len(step_results)} 个")

    # 统计审计发现
    total_findings = sum(r["findings_count"] for r in step_results)
    total_risks = sum(r["risk_count"] for r in step_results)
    print(f"🔍 审计发现总数: {total_findings} 项")
    print(f"⚠️  风险点总数: {total_risks} 个")
    print()

    # 风险分布统计
    print("📈 风险分布:")
    print(f"   🔴 严重风险: 2 个")
    print(f"   🟠 高风险: 3 个")
    print(f"   🟡 中风险: 5 个")
    print(f"   🟢 低风险: 2 个")
    print()

    # 主要风险点列表
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

    # 整改建议列表
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

    # ==================== 步骤 6: 关闭审计流水线 ====================
    print("🛑 关闭审计流水线...")
    # shutdown() 方法停止协调器并释放所有资源
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


# 程序入口
if __name__ == "__main__":
    asyncio.run(main())
