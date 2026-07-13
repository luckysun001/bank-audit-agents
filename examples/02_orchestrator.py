"""
示例 02: 使用协调器管理多个智能体

演示如何使用 AgentOrchestrator 协调多个智能体协作执行任务
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bank_audit_agents.core.orchestrator import AgentOrchestrator
from bank_audit_agents.core.base_agent import Task
from bank_audit_agents.agents.document_parser import DocumentParserAgent
from bank_audit_agents.agents.risk_identifier import RiskIdentifierAgent
from bank_audit_agents.utils.logger import get_logger

logger = get_logger("example_02")


async def main():
    print("=" * 60)
    print("🏦 示例 02: 使用协调器管理多个智能体")
    print("=" * 60)
    print()

    # 1. 创建协调器
    print("🎯 创建智能体协调器...")
    orchestrator = AgentOrchestrator()
    print()

    # 2. 注册智能体
    print("🤖 注册智能体...")
    doc_agent_id = orchestrator.register_agent(DocumentParserAgent())
    risk_agent_id = orchestrator.register_agent(RiskIdentifierAgent())
    print(f"   - 文档解析智能体: {doc_agent_id}")
    print(f"   - 风险识别智能体: {risk_agent_id}")
    print()

    # 3. 启动协调器
    print("🚀 启动协调器...")
    await orchestrator.start()
    print()

    # 4. 查看状态
    print("📊 系统状态:")
    status = orchestrator.get_status()
    print(f"   智能体数量: {status['agents_count']}")
    print(f"   运行状态: {status['status']}")
    print()

    # 5. 提交任务
    print("📋 提交文档解析任务...")
    task1 = Task(
        task_type="document_processing",
        description="解析信贷合同文档",
        input_data={
            "document_path": "data/sample/loan_contract.pdf",
            "document_type": "loan_contract",
        },
    )

    task2 = Task(
        task_type="risk_identification",
        description="识别文档中的风险点",
        input_data={
            "document_content": "模拟的贷款合同内容...",
            "document_type": "loan_contract",
        },
    )

    await orchestrator.submit_task(task1, target_agent_type="document_parser")
    await orchestrator.submit_task(task2, target_agent_type="risk_identifier")
    print(f"   已提交任务 1: {task1.task_id}")
    print(f"   已提交任务 2: {task2.task_id}")
    print()

    # 6. 等待任务完成
    print("⏳ 等待任务执行完成...")
    await asyncio.sleep(2)  # 给一些时间让任务执行
    await orchestrator.wait_for_completion(timeout=10)
    print()

    # 7. 获取执行结果
    print("=" * 60)
    print("📊 执行结果统计:")
    print("=" * 60)
    results = orchestrator.get_status()
    stats = results["statistics"]
    print(f"   提交任务总数: {stats['total_tasks_submitted']}")
    print(f"   完成任务数: {stats['total_tasks_completed']}")
    print(f"   失败任务数: {stats['total_tasks_failed']}")
    print(f"   消息交换次数: {stats['total_messages_exchanged']}")
    print()

    # 8. 停止协调器
    print("🛑 停止协调器...")
    await orchestrator.stop()
    print()

    print("=" * 60)
    print("✨ 示例执行完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
