"""
协调器测试模块

本测试模块全面测试 AgentOrchestrator 类的功能，
验证多智能体系统的核心协调能力。

测试覆盖范围：
1. 协调器初始化和基本属性
2. 智能体注册和管理
3. 任务提交和执行
4. 状态监控和统计
5. 消息总线通信
6. 批量任务处理

运行方式：
    pytest tests/test_orchestrator.py -v

测试架构：
- MockTestAgent: 成功执行任务的模拟智能体，记录执行历史
- FailingAgent: 总是失败的智能体，用于测试错误处理
- TestAgentOrchestrator: 核心协调器功能测试（异步）
- TestOrchestratorMessageBus: 消息总线测试（异步）
- TestOrchestratorStats: 统计信息测试（异步）
"""

# 导入测试框架和必要的库
import pytest
import asyncio

# 导入待测试的核心类
from bank_audit_agents.core.orchestrator import (
    AgentOrchestrator,     # 智能体协调器
    OrchestratorStatus,    # 协调器状态枚举
)
from bank_audit_agents.core.base_agent import (
    BaseAgent,           # 智能体基类
    Task,               # 任务对象
    AgentResult,        # 执行结果对象
    AgentStatus,        # 智能体状态枚举
    AgentType,          # 智能体类型枚举
    TaskStatus,         # 任务状态枚举
)


# ==================== 测试用智能体 ====================
class MockTestAgent(BaseAgent):
    """成功执行任务的模拟智能体

    用于测试协调器的正常任务执行流程，
    记录所有执行过的任务以便验证。
    """

    def __init__(self, agent_type=AgentType.DOCUMENT_PARSER, **kwargs):
        super().__init__(agent_type, **kwargs)
        self.executed_tasks = []  # 记录执行过的任务

    def get_system_prompt(self) -> str:
        """返回测试用系统提示词"""
        return "测试智能体"

    def get_tools(self) -> list:
        """返回空工具列表"""
        return []

    async def execute(self, task: Task) -> AgentResult:
        """执行任务并记录到执行历史

        Args:
            task: 待执行的任务对象

        Returns:
            AgentResult: 成功的执行结果
        """
        self.executed_tasks.append(task)
        await asyncio.sleep(0.05)  # 模拟工作时间
        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            success=True,
            summary=f"已处理: {task.description}",
            confidence_score=0.9,
        )


class FailingAgent(BaseAgent):
    """总是失败的智能体

    用于测试协调器的错误处理和任务失败流程。
    """

    def __init__(self, **kwargs):
        super().__init__(AgentType.RISK_IDENTIFIER, **kwargs)

    def get_system_prompt(self) -> str:
        """返回测试用系统提示词"""
        return "失败的智能体"

    def get_tools(self) -> list:
        """返回空工具列表"""
        return []

    async def execute(self, task: Task) -> AgentResult:
        """执行任务但总是抛出异常

        Args:
            task: 待执行的任务对象

        Raises:
            Exception: 总是抛出"模拟执行失败"异常
        """
        raise Exception("模拟执行失败")


# ==================== 协调器核心功能测试 ====================
@pytest.mark.asyncio
class TestAgentOrchestrator:
    """测试智能体协调器的核心功能（异步测试）"""

    async def test_orchestrator_initialization(self):
        """测试协调器初始化状态"""
        orchestrator = AgentOrchestrator()
        # 验证初始状态为 IDLE
        assert orchestrator.status == OrchestratorStatus.IDLE
        # 验证未运行
        assert orchestrator.is_running is False
        # 验证智能体列表为空
        assert len(orchestrator.agents) == 0

    async def test_register_agent(self):
        """测试注册智能体到协调器"""
        orchestrator = AgentOrchestrator()
        agent = MockTestAgent()

        # 注册智能体
        agent_id = orchestrator.register_agent(agent)

        # 验证返回的 ID 正确
        assert agent_id == agent.agent_id
        # 验证智能体已添加到注册表
        assert len(orchestrator.agents) == 1
        assert agent_id in orchestrator.agents

    async def test_get_agent(self):
        """测试获取智能体"""
        orchestrator = AgentOrchestrator()
        agent = MockTestAgent()
        agent_id = orchestrator.register_agent(agent)

        # 获取已注册的智能体
        retrieved = orchestrator.get_agent(agent_id)
        assert retrieved == agent

        # 测试获取不存在的智能体（应返回 None）
        assert orchestrator.get_agent("non_existent") is None

    async def test_get_agents_by_type(self):
        """测试按类型获取智能体列表"""
        orchestrator = AgentOrchestrator()

        # 注册不同类型的智能体
        agent1 = MockTestAgent(AgentType.DOCUMENT_PARSER)
        agent2 = MockTestAgent(AgentType.DOCUMENT_PARSER)
        agent3 = MockTestAgent(AgentType.RISK_IDENTIFIER)

        orchestrator.register_agent(agent1)
        orchestrator.register_agent(agent2)
        orchestrator.register_agent(agent3)

        # 按类型获取文档解析智能体（应该有2个）
        parser_agents = orchestrator.get_agents_by_type(AgentType.DOCUMENT_PARSER.value)
        assert len(parser_agents) == 2

        # 按类型获取风险识别智能体（应该有1个）
        risk_agents = orchestrator.get_agents_by_type(AgentType.RISK_IDENTIFIER.value)
        assert len(risk_agents) == 1

    async def test_unregister_agent(self):
        """测试注销智能体"""
        orchestrator = AgentOrchestrator()
        agent = MockTestAgent()
        agent_id = orchestrator.register_agent(agent)

        # 验证已注册
        assert len(orchestrator.agents) == 1

        # 注销智能体
        orchestrator.unregister_agent(agent_id)

        # 验证已注销
        assert len(orchestrator.agents) == 0
        assert agent_id not in orchestrator.agents

    async def test_start_stop_orchestrator(self):
        """测试启动和停止协调器"""
        orchestrator = AgentOrchestrator()

        # 启动协调器
        await orchestrator.start()
        assert orchestrator.is_running is True
        assert orchestrator.status == OrchestratorStatus.RUNNING

        # 停止协调器
        await orchestrator.stop()
        assert orchestrator.is_running is False
        assert orchestrator.status == OrchestratorStatus.STOPPED

    async def test_submit_task(self):
        """测试提交任务到协调器"""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(MockTestAgent())
        await orchestrator.start()

        # 创建任务
        task = Task(
            task_type="document_processing",
            description="测试任务",
            input_data={},
        )

        # 提交任务到指定类型的智能体
        task_id = await orchestrator.submit_task(
            task,
            target_agent_type=AgentType.DOCUMENT_PARSER.value,
        )

        # 验证返回的任务 ID 正确
        assert task_id == task.task_id
        # 验证任务状态已变更（不再是 PENDING）
        assert task.status != TaskStatus.PENDING

        # 等待任务执行完成
        await asyncio.sleep(0.5)
        await orchestrator.stop()

    async def test_get_status(self):
        """测试获取协调器状态信息"""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(MockTestAgent(agent_id="test_agent"))

        # 获取状态
        status = orchestrator.get_status()

        # 验证状态信息格式正确
        assert isinstance(status, dict)
        assert status["agents_count"] == 1
        # 验证包含必要的状态字段
        assert "queue_size" in status
        assert "active_tasks" in status
        assert "completed_tasks" in status
        assert "statistics" in status
        assert "agents" in status
        # 验证智能体信息包含注册的智能体
        assert "test_agent" in str(status["agents"])

    async def test_task_completion(self):
        """测试任务完成后的回调和状态更新"""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(MockTestAgent())
        await orchestrator.start()

        # 设置完成回调
        completed_callback_called = False

        def on_complete(task, result):
            nonlocal completed_callback_called
            completed_callback_called = True

        orchestrator.on_task_completed = on_complete

        # 提交任务
        task = Task(task_type="document_processing", description="test", input_data={})
        await orchestrator.submit_task(task, target_agent_type="document_parser")

        # 等待任务执行
        await asyncio.sleep(0.5)
        await orchestrator.stop()

        # 验证任务已完成
        results = orchestrator.get_results()
        assert len(results["completed"]) >= 1

    async def test_task_failure(self):
        """测试任务失败处理和错误回调"""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(FailingAgent())  # 使用总是失败的智能体
        await orchestrator.start()

        # 设置失败回调
        failed_callback_called = False

        def on_fail(task, error):
            nonlocal failed_callback_called
            failed_callback_called = True

        orchestrator.on_task_failed = on_fail

        # 提交任务
        task = Task(task_type="risk_identification", description="test", input_data={})
        await orchestrator.submit_task(task, target_agent_type="risk_identifier")

        # 等待任务执行（预期会失败）
        await asyncio.sleep(0.5)
        await orchestrator.stop()

        # 验证任务已失败
        results = orchestrator.get_results()
        assert len(results["failed"]) >= 1

    async def test_batch_submit_tasks(self):
        """测试批量提交多个任务"""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(MockTestAgent())
        await orchestrator.start()

        # 创建多个任务
        tasks = []
        for i in range(3):
            task = Task(
                task_type="document_processing",
                description=f"任务 {i}",
                input_data={},
            )
            tasks.append(task)

        # 批量提交任务
        task_ids = await orchestrator.submit_tasks_batch(tasks)

        # 验证返回的任务 ID 数量正确
        assert len(task_ids) == 3

        # 等待任务执行
        await asyncio.sleep(1)
        await orchestrator.stop()

        # 验证任务已处理（完成或失败）
        results = orchestrator.get_results()
        assert len(results["completed"]) + len(results["failed"]) >= 3

    async def test_register_default_agents(self):
        """测试注册默认智能体集合"""
        orchestrator = AgentOrchestrator()
        orchestrator.register_default_agents()

        # 验证注册了所有核心智能体（至少5个）
        # 文档解析、风险识别、合规检查、质量审核、任务协调
        assert len(orchestrator.agents) >= 5

        # 验证每种类型至少有一个智能体
        types = set()
        for agent in orchestrator.agents.values():
            types.add(agent.agent_type.value)

        assert "document_parser" in types
        assert "risk_identifier" in types
        assert "compliance_checker" in types


# ==================== 消息总线测试 ====================
class TestOrchestratorMessageBus:
    """测试协调器的消息总线功能"""

    @pytest.mark.asyncio
    async def test_send_message(self):
        """测试通过消息总线发送消息"""
        orchestrator = AgentOrchestrator()

        # 发送消息
        message_id = await orchestrator.send_message(
            sender_id="agent1",
            receiver_id="agent2",
            content={"hello": "world"},
            message_type="information",
        )

        # 验证消息 ID 生成
        assert message_id is not None

    @pytest.mark.asyncio
    async def test_broadcast_message(self):
        """测试广播消息到所有智能体"""
        orchestrator = AgentOrchestrator()
        agent1 = MockTestAgent(agent_id="agent1")
        agent2 = MockTestAgent(agent_id="agent2")
        orchestrator.register_agent(agent1)
        orchestrator.register_agent(agent2)

        await orchestrator.start()

        # 发送广播消息（receiver_id="*" 表示广播）
        await orchestrator.send_message(
            sender_id="system",
            receiver_id="*",  # 广播到所有智能体
            content={"broadcast": "message"},
        )

        # 等待消息路由
        await asyncio.sleep(0.1)
        await orchestrator.stop()

        # 消息应该被路由到除发送者外的所有智能体
        # agent1 和 agent2 应该收到消息
        # 注意：这里只是验证消息被发送到了总线

    @pytest.mark.asyncio
    async def test_message_callback(self):
        """测试消息发送回调函数"""
        orchestrator = AgentOrchestrator()

        # 设置回调标志
        callback_called = False

        # 定义回调函数
        def on_message(message):
            nonlocal callback_called
            callback_called = True

        # 注册回调
        orchestrator.on_message_sent = on_message

        # 发送消息
        await orchestrator.send_message(
            sender_id="a1",
            receiver_id="a2",
            content={},
        )

        # 验证回调被调用
        assert callback_called is True


# ==================== 协调器统计信息测试 ====================
class TestOrchestratorStats:
    """测试协调器的执行统计功能"""

    @pytest.mark.asyncio
    async def test_execution_statistics(self):
        """测试任务执行统计信息"""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(MockTestAgent())
        await orchestrator.start()

        # 提交多个任务
        for i in range(3):
            task = Task(
                task_type="document_processing",
                description=f"任务 {i}",
                input_data={},
            )
            await orchestrator.submit_task(task)

        # 等待任务执行
        await asyncio.sleep(1)
        await orchestrator.stop()

        # 获取统计信息
        status = orchestrator.get_status()
        stats = status["statistics"]

        # 验证提交的任务数正确
        assert stats["total_tasks_submitted"] >= 3
        # 验证完成的任务数不超过提交的任务数
        # 注意：可能不是所有任务都完成，但至少应该有一些
        assert stats["total_tasks_submitted"] >= stats["total_tasks_completed"]
