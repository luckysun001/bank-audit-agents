"""
示例 01: 快速入门 - 使用单个智能体

本示例演示了如何使用单个智能体完成简单的文档解析任务，
是理解多智能体系统的基础入门示例。

学习要点：
1. 如何导入和实例化智能体
2. 如何创建任务对象
3. 如何调用智能体执行任务
4. 如何处理和解析执行结果

执行方式：
    python examples/01_single_agent.py

核心流程：
    DocumentParserAgent()
        │
        ▼
    Task(input_data)
        │
        ▼
    agent.run(task)
        │
        ▼
    AgentResult (success, summary, findings, confidence_score)
"""

# 导入必要的库
import asyncio  # 异步编程支持
import sys      # 系统路径操作
import os       # 文件路径操作

# 将项目根目录添加到 Python 路径，确保可以导入项目模块
# 这是因为示例文件位于 examples/ 目录下，需要向上两级找到项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入核心模块
from bank_audit_agents.agents.document_parser import DocumentParserAgent  # 文档解析智能体
from bank_audit_agents.core.base_agent import Task                        # 任务对象
from bank_audit_agents.utils.logger import get_logger                      # 日志工具

# 初始化日志记录器
logger = get_logger("example_01")


async def main():
    """主函数：演示单个智能体的使用流程"""
    # 打印标题
    print("=" * 60)
    print("🏦 示例 01: 使用文档解析智能体")
    print("=" * 60)
    print()

    # ==================== 步骤 1: 创建智能体 ====================
    print("🤖 创建文档解析智能体...")
    # 创建文档解析智能体实例
    # 智能体会自动生成唯一的 agent_id
    agent = DocumentParserAgent()
    print(f"   智能体 ID: {agent.agent_id}")
    print(f"   智能体类型: {agent.agent_type.value}")
    print()

    # ==================== 步骤 2: 创建任务 ====================
    print("📋 创建解析任务...")
    # Task 对象是智能体执行的基本单位
    # 包含任务类型、描述和输入数据
    task = Task(
        task_type="document_parsing",  # 任务类型，决定智能体如何处理
        description="解析信贷合同文档",  # 任务描述，便于日志和监控
        input_data={
            "document_path": "data/sample/loan_contract.pdf",  # 待解析文档路径
            "document_type": "loan_contract",                  # 文档类型
            "extraction_requirements": ["借款人", "贷款金额", "期限", "利率", "担保方式"],
        },
    )
    print(f"   任务 ID: {task.task_id}")
    print(f"   任务描述: {task.description}")
    print()

    # ==================== 步骤 3: 执行任务 ====================
    print("⚡ 执行任务...")
    # 调用智能体的 run() 方法执行任务
    # 这是一个异步方法，需要使用 await
    result = await agent.run(task)
    print()

    # ==================== 步骤 4: 显示结果 ====================
    print("=" * 60)
    print("📊 执行结果:")
    print("=" * 60)
    # AgentResult 对象包含执行结果的所有信息
    print(f"✅ 成功: {result.success}")
    print(f"📝 摘要: {result.summary}")
    print(f"🎯 置信度: {result.confidence_score:.2%}")
    print(f"⏱️  耗时: {result.execution_time_seconds:.2f} 秒")
    print()

    # 如果有提取到的信息，显示前5条
    if result.findings:
        print("🔍 提取的信息:")
        for finding in result.findings[:5]:
            print(f"   - {finding.get('field', '未知')}: {finding.get('value', 'N/A')}")

    print()
    print("=" * 60)
    print("✨ 示例执行完成！")
    print("=" * 60)


# 程序入口
if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())
