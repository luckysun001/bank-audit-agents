"""
示例 01: 快速入门 - 使用单个智能体

演示如何使用单个智能体完成简单的文档解析任务
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bank_audit_agents.agents.document_parser import DocumentParserAgent
from bank_audit_agents.core.base_agent import Task
from bank_audit_agents.utils.logger import get_logger

logger = get_logger("example_01")


async def main():
    print("=" * 60)
    print("🏦 示例 01: 使用文档解析智能体")
    print("=" * 60)
    print()

    # 1. 创建智能体
    print("🤖 创建文档解析智能体...")
    agent = DocumentParserAgent()
    print(f"   智能体 ID: {agent.agent_id}")
    print(f"   智能体类型: {agent.agent_type.value}")
    print()

    # 2. 创建任务
    print("📋 创建解析任务...")
    task = Task(
        task_type="document_parsing",
        description="解析信贷合同文档",
        input_data={
            "document_path": "data/sample/loan_contract.pdf",
            "document_type": "loan_contract",
            "extraction_requirements": ["借款人", "贷款金额", "期限", "利率", "担保方式"],
        },
    )
    print(f"   任务 ID: {task.task_id}")
    print(f"   任务描述: {task.description}")
    print()

    # 3. 执行任务
    print("⚡ 执行任务...")
    result = await agent.run(task)
    print()

    # 4. 显示结果
    print("=" * 60)
    print("📊 执行结果:")
    print("=" * 60)
    print(f"✅ 成功: {result.success}")
    print(f"📝 摘要: {result.summary}")
    print(f"🎯 置信度: {result.confidence_score:.2%}")
    print(f"⏱️  耗时: {result.execution_time_seconds:.2f} 秒")
    print()

    if result.findings:
        print("🔍 提取的信息:")
        for finding in result.findings[:5]:
            print(f"   - {finding.get('field', '未知')}: {finding.get('value', 'N/A')}")

    print()
    print("=" * 60)
    print("✨ 示例执行完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
