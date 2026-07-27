"""
示例 02: 使用协调器管理多个智能体

本示例演示了如何使用 AgentOrchestrator 协调多个智能体协作执行任务，
是理解多智能体系统核心架构的关键示例。

学习要点：
1. 如何创建 AgentOrchestrator 协调器
2. 如何注册多个智能体到协调器
3. 如何启动和停止协调器
4. 如何通过协调器提交任务
5. 如何获取系统状态和执行统计

执行方式：
    python examples/02_orchestrator.py

核心流程：
    AgentOrchestrator()
        │
        ├── register_agent(DocumentParserAgent)
        └── register_agent(RiskIdentifierAgent)
        │
        ▼
    orchestrator.start()  # 启动消息队列和工作协程
        │
        ├── submit_task(task1, target="document_parser")
        └── submit_task(task2, target="risk_identifier")
        │
        ▼
    orchestrator.get_status()  # 获取执行统计
        │
        ▼
    orchestrator.stop()  # 停止协调器

架构设计：
- 协调器负责维护智能体注册表和任务队列
- 任务通过消息队列异步分发到目标智能体
- 支持按智能体类型路由任务
- 提供统一的状态监控和统计接口
"""

# 导入必要的库
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入核心模块
from bank_audit_agents.core.orchestrator import AgentOrchestrator           # 智能体协调器
from bank_audit_agents.core.base_agent import Task                          # 任务对象
from bank_audit_agents.agents.document_parser import DocumentParserAgent    # 文档解析智能体
from bank_audit_agents.agents.risk_identifier import RiskIdentifierAgent    # 风险识别智能体
from bank_audit_agents.utils.logger import get_logger                        # 日志工具

# 初始化日志记录器
logger = get_logger("example_02")


async def main():
    """主函数：演示协调器管理多个智能体的流程"""
    print("=" * 60)
    print("🏦 示例 02: 使用协调器管理多个智能体")
    print("=" * 60)
    print()

    # ==================== 步骤 1: 创建协调器 ====================
    print("🎯 创建智能体协调器...")
    # AgentOrchestrator 是多智能体系统的核心协调组件
    # 负责管理智能体注册、任务分发、消息路由和状态监控
    orchestrator = AgentOrchestrator()
    print()

    # ==================== 步骤 2: 注册智能体 ====================
    print("🤖 注册智能体...")
    # 将智能体注册到协调器中
    # register_agent() 返回智能体的唯一 ID
    doc_agent_id = orchestrator.register_agent(DocumentParserAgent())
    risk_agent_id = orchestrator.register_agent(RiskIdentifierAgent())
    print(f"   - 文档解析智能体: {doc_agent_id}")
    print(f"   - 风险识别智能体: {risk_agent_id}")
    print()

    # ==================== 步骤 3: 启动协调器 ====================
    print("🚀 启动协调器...")
    # start() 方法启动消息队列和工作协程
    # 协调器进入运行状态后才能接收和处理任务
    await orchestrator.start()
    print()

    # ==================== 步骤 4: 查看系统状态 ====================
    print("📊 系统状态:")
    # get_status() 返回系统的完整状态信息
    # 包括智能体数量、运行状态、任务队列等
    status = orchestrator.get_status()
    print(f"   智能体数量: {status['agents_count']}")
    print(f"   运行状态: {status['status']}")
    print()

    # ==================== 步骤 5: 提交任务 ====================
    print("📋 提交文档解析任务...")

    # 创建第一个任务：文档解析
    task1 = Task(
        task_type="document_processing",
        description="解析信贷合同文档",
        input_data={
            "document_path": "data/sample/loan_contract.pdf",
            "document_type": "loan_contract",
        },
    )

    # 创建第二个任务：风险识别
    task2 = Task(
        task_type="risk_identification",
        description="识别文档中的风险点",
        input_data={
            "document_content": "模拟的贷款合同内容...",
            "document_type": "loan_contract",
        },
    )

    # 通过协调器提交任务
    # target_agent_type 参数指定任务发送给哪种类型的智能体
    await orchestrator.submit_task(task1, target_agent_type="document_parser")
    await orchestrator.submit_task(task2, target_agent_type="risk_identifier")
    print(f"   已提交任务 1: {task1.task_id}")
    print(f"   已提交任务 2: {task2.task_id}")
    print()

    # ==================== 步骤 6: 等待任务完成 ====================
    print("⏳ 等待任务执行完成...")
    # 给一些时间让任务在后台执行
    await asyncio.sleep(2)
    # wait_for_completion() 阻塞等待所有任务完成
    await orchestrator.wait_for_completion(timeout=10)
    print()

    # ==================== 步骤 7: 获取执行结果 ====================
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

    # ==================== 步骤 8: 停止协调器 ====================
    print("🛑 停止协调器...")
    # stop() 方法停止消息队列和工作协程
    # 释放所有资源
    await orchestrator.stop()
    print()

    print("=" * 60)
    print("✨ 示例执行完成！")
    print("=" * 60)


# 程序入口
if __name__ == "__main__":
    asyncio.run(main())
