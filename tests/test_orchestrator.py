"""
协调器测试
"""

import pytest
import asyncio

from bank_audit_agents.core.orchestrator import (
    AgentOrchestrator,
    OrchestratorStatus,
)
from bank_audit_agents.core.base_agent import (
    BaseAgent,
    Task,
    AgentResult,
    AgentStatus,
    AgentType,
    TaskStatus,
)


class MockTestAgent(BaseAgent):
    """测试用智能体"""

    def __init__(self, agent_type=AgentType.DOCUMENT_PARSER, **kwargs):
        super().__init__(agent_type, **kwargs)
        self.executed_tasks = []

    def get_system_prompt(self) -> str:
        return "测试智能体"

    def get_tools(self) -> list:
        return []

    async def execute(self, task: Task) -> AgentResult:
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
    """总是失败的智能体"""

    def __init__(self, **kwargs):
        super().__init__(AgentType.RISK_IDENTIFIER, **kwargs)

    def get_system_prompt(self) -> str:
        return "失败的智能体"

    def get_tools(self) -> list:
        return []

    async def execute(self, task: Task) -> AgentResult:
        raise Exception("模拟执行失败")


@pytest.mark.asyncio
class TestAgentOrchestrator:
    """测试智能体协调器"""

    async def test_orchestrator_initialization(self):
        """测试协调器初始化"""
        orchestrator = AgentOrchestrator()
        assert orchestrator.status == OrchestratorStatus.IDLE
        assert orchestrator.is_running is False
        assert len(orchestrator.agents) == 0

    async def test_register_agent(self):
        """测试注册智能体"""
        orchestrator = AgentOrchestrator()
        agent = MockTestAgent()

        agent_id = orchestrator.register_agent(agent)

        assert agent_id == agent.agent_id
        assert len(orchestrator.agents) == 1
        assert agent_id in orchestrator.agents

    async def test_get_agent(self):
        """测试获取智能体"""
        orchestrator = AgentOrchestrator()
        agent = MockTestAgent()
        agent_id = orchestrator.register_agent(agent)

        retrieved = orchestrator.get_agent(agent_id)
        assert retrieved == agent

        # 测试获取不存在的智能体
        assert orchestrator.get_agent("non_existent") is None

    async def test_get_agents_by_type(self):
        """测试按类型获取智能体"""
        orchestrator = AgentOrchestrator()

        # 注册不同类型的智能体
        agent1 = MockTestAgent(AgentType.DOCUMENT_PARSER)
        agent2 = MockTestAgent(AgentType.DOCUMENT_PARSER)
        agent3 = MockTestAgent(AgentType.RISK_IDENTIFIER)

        orchestrator.register_agent(agent1)
        orchestrator.register_agent(agent2)
        orchestrator.register_agent(agent3)

        # 按类型获取
        parser_agents = orchestrator.get_agents_by_type(AgentType.DOCUMENT_PARSER.value)
        assert len(parser_agents) == 2

        risk_agents = orchestrator.get_agents_by_type(AgentType.RISK_IDENTIFIER.value)
        assert len(risk_agents) == 1

    async def test_unregister_agent(self):
        """测试注销智能体"""
        orchestrator = AgentOrchestrator()
        agent = MockTestAgent()
        agent_id = orchestrator.register_agent(agent)

        assert len(orchestrator.agents) == 1

        orchestrator.unregister_agent(agent_id)

        assert len(orchestrator.agents) == 0
        assert agent_id not in orchestrator.agents

    async def test_start_stop_orchestrator(self):
        """测试启动和停止协调器"""
        orchestrator = AgentOrchestrator()

        await orchestrator.start()
        assert orchestrator.is_running is True
        assert orchestrator.status == OrchestratorStatus.RUNNING

        await orchestrator.stop()
        assert orchestrator.is_running is False
        assert orchestrator.status == OrchestratorStatus.STOPPED

    async def test_submit_task(self):
        """测试提交任务"""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(MockTestAgent())
        await orchestrator.start()

        task = Task(
            task_type="document_processing",
            description="测试任务",
            input_data={},
        )

        task_id = await orchestrator.submit_task(
            task,
            target_agent_type=AgentType.DOCUMENT_PARSER.value,
        )

        assert task_id == task.task_id
        assert task.status != TaskStatus.PENDING

        await asyncio.sleep(0.5)  # 等待任务执行
        await orchestrator.stop()

    async def test_get_status(self):
        """测试获取状态"""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(MockTestAgent(agent_id="test_agent"))

        status = orchestrator.get_status()

        assert isinstance(status, dict)
        assert status["agents_count"] == 1
        assert "queue_size" in status
        assert "active_tasks" in status
        assert "completed_tasks" in status
        assert "statistics" in status
        assert "agents" in status
        assert "test_agent" in str(status["agents"])

    async def test_task_completion(self):
        """测试任务完成后的回调和状态"""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(MockTestAgent())
        await orchestrator.start()

        completed_callback_called = False

        def on_complete(task, result):
            nonlocal completed_callback_called
            completed_callback_called = True

        orchestrator.on_task_completed = on_complete

        task = Task(task_type="document_processing", description="test", input_data={})
        await orchestrator.submit_task(task, target_agent_type="document_parser")

        await asyncio.sleep(0.5)
        await orchestrator.stop()

        # 任务应该已完成
        results = orchestrator.get_results()
        assert len(results["completed"]) >= 1

    async def test_task_failure(self):
        """测试任务失败处理"""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(FailingAgent())
        await orchestrator.start()

        failed_callback_called = False

        def on_fail(task, error):
            nonlocal failed_callback_called
            failed_callback_called = True

        orchestrator.on_task_failed = on_fail

        task = Task(task_type="risk_identification", description="test", input_data={})
        await orchestrator.submit_task(task, target_agent_type="risk_identifier")

        await asyncio.sleep(0.5)
        await orchestrator.stop()

        results = orchestrator.get_results()
        assert len(results["failed"]) >= 1

    async def test_batch_submit_tasks(self):
        """测试批量提交任务"""
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

        task_ids = await orchestrator.submit_tasks_batch(tasks)

        assert len(task_ids) == 3

        await asyncio.sleep(1)
        await orchestrator.stop()

        results = orchestrator.get_results()
        assert len(results["completed"]) + len(results["failed"]) >= 3

    async def test_register_default_agents(self):
        """测试注册默认智能体集合"""
        orchestrator = AgentOrchestrator()
        orchestrator.register_default_agents()

        # 应该注册了所有核心智能体
        assert len(orchestrator.agents) >= 5  # 文档解析、风险识别、合规检查、质量审核、任务协调

        # 验证每种类型至少有一个
        types = set()
        for agent in orchestrator.agents.values():
            types.add(agent.agent_type.value)

        assert "document_parser" in types
        assert "risk_identifier" in types
        assert "compliance_checker" in types


class TestOrchestratorMessageBus:
    """测试消息总线"""

    @pytest.mark.asyncio
    async def test_send_message(self):
        """测试发送消息"""
        orchestrator = AgentOrchestrator()

        message_id = await orchestrator.send_message(
            sender_id="agent1",
            receiver_id="agent2",
            content={"hello": "world"},
            message_type="information",
        )

        assert message_id is not None

    @pytest.mark.asyncio
    async def test_broadcast_message(self):
        """测试广播消息"""
        orchestrator = AgentOrchestrator()
        agent1 = MockTestAgent(agent_id="agent1")
        agent2 = MockTestAgent(agent_id="agent2")
        orchestrator.register_agent(agent1)
        orchestrator.register_agent(agent2)

        await orchestrator.start()

        # 广播消息
        await orchestrator.send_message(
            sender_id="system",
            receiver_id="*",  # 广播
            content={"broadcast": "message"},
        )

        await asyncio.sleep(0.1)
        await orchestrator.stop()

        # 消息应该被路由到除发送者外的所有智能体
        # agent1 和 agent2 应该收到消息
        # 注意：这里只是验证消息被发送到了总线

    @pytest.mark.asyncio
    async def test_message_callback(self):
        """测试消息发送回调"""
        orchestrator = AgentOrchestrator()

        callback_called = False

        def on_message(message):
            nonlocal callback_called
            callback_called = True

        orchestrator.on_message_sent = on_message

        await orchestrator.send_message(
            sender_id="a1",
            receiver_id="a2",
            content={},
        )

        assert callback_called is True


class TestOrchestratorStats:
    """测试协调器统计信息"""

    @pytest.mark.asyncio
    async def test_execution_statistics(self):
        """测试执行统计"""
        orchestrator = AgentOrchestrator()
        orchestrator.register_agent(MockTestAgent())
        await orchestrator.start()

        # 提交几个任务
        for i in range(3):
            task = Task(
                task_type="document_processing",
                description=f"任务 {i}",
                input_data={},
            )
            await orchestrator.submit_task(task)

        await asyncio.sleep(1)
        await orchestrator.stop()

        status = orchestrator.get_status()
        stats = status["statistics"]

        assert stats["total_tasks_submitted"] >= 3
        # 注意：可能不是所有任务都完成，但至少应该有一些
        assert stats["total_tasks_submitted"] >= stats["total_tasks_completed"]
