"""
智能体基类测试
"""

import pytest
import asyncio

from bank_audit_agents.core.base_agent import (
    BaseAgent,
    Task,
    AgentResult,
    AgentMessage,
    AgentStatus,
    TaskStatus,
    AgentType,
)


class MockAgent(BaseAgent):
    """测试用的模拟智能体"""

    def __init__(self, agent_id=None):
        super().__init__(AgentType.DOCUMENT_PARSER, agent_id)

    def get_system_prompt(self) -> str:
        return "你是一个测试智能体"

    def get_tools(self) -> list:
        return ["test_tool"]

    async def execute(self, task: Task) -> AgentResult:
        await asyncio.sleep(0.1)
        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            success=True,
            summary="测试任务完成",
            findings=[{"key": "value"}],
            confidence_score=0.95,
        )


class TestBaseAgent:
    """测试智能体基类"""

    def test_agent_initialization(self):
        """测试智能体初始化"""
        agent = MockAgent(agent_id="test_agent_001")
        assert agent.agent_id == "test_agent_001"
        assert agent.agent_type == AgentType.DOCUMENT_PARSER
        assert agent.status == AgentStatus.IDLE

    def test_agent_without_id(self):
        """测试不指定 ID 时自动生成"""
        agent = MockAgent()
        assert agent.agent_id is not None
        assert "document_parser" in agent.agent_id

    def test_system_prompt(self):
        """测试系统提示词"""
        agent = MockAgent()
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_tools(self):
        """测试工具列表"""
        agent = MockAgent()
        tools = agent.get_tools()
        assert isinstance(tools, list)
        assert "test_tool" in tools


class TestTask:
    """测试任务对象"""

    def test_task_creation(self):
        """测试任务创建"""
        task = Task(
            task_type="test_task",
            description="测试任务",
            input_data={"key": "value"},
        )
        assert task.task_id is not None
        assert task.task_type == "test_task"
        assert task.description == "测试任务"
        assert task.status == TaskStatus.PENDING

    def test_task_start(self):
        """测试任务开始"""
        task = Task(task_type="test", description="test")
        task.start()
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.started_at is not None

    def test_task_complete(self):
        """测试任务完成"""
        task = Task(task_type="test", description="test")
        task.start()
        task.complete({"result": "success"})
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        assert task.output_data == {"result": "success"}

    def test_task_fail(self):
        """测试任务失败"""
        task = Task(task_type="test", description="test")
        task.start()
        task.fail("something went wrong")
        assert task.status == TaskStatus.FAILED
        assert task.error_message == "something went wrong"

    def test_task_duration(self):
        """测试任务执行时间计算"""
        import time
        task = Task(task_type="test", description="test")
        task.start()
        time.sleep(0.1)
        task.complete({})
        assert task.duration_seconds >= 0.1


class TestAgentMessage:
    """测试智能体消息"""

    def test_message_creation(self):
        """测试消息创建"""
        message = AgentMessage(
            sender_id="agent_1",
            receiver_id="agent_2",
            message_type="information",
            content={"key": "value"},
        )
        assert message.message_id is not None
        assert message.sender_id == "agent_1"
        assert message.receiver_id == "agent_2"
        assert message.content == {"key": "value"}

    def test_message_to_dict(self):
        """测试消息转换为字典"""
        message = AgentMessage(
            sender_id="agent_1",
            receiver_id="agent_2",
            content={"data": "test"},
        )
        msg_dict = message.to_dict()
        assert isinstance(msg_dict, dict)
        assert "message_id" in msg_dict
        assert msg_dict["sender_id"] == "agent_1"
        assert msg_dict["content"]["data"] == "test"


@pytest.mark.asyncio
class TestAgentExecution:
    """测试智能体执行"""

    async def test_run_task_success(self):
        """测试成功执行任务"""
        agent = MockAgent()
        task = Task(task_type="test", description="测试任务", input_data={})

        result = await agent.run(task)

        assert result.success is True
        assert result.agent_id == agent.agent_id
        assert result.confidence_score == 0.95
        assert len(result.findings) == 1
        assert agent.status == AgentStatus.COMPLETED

    async def test_task_callback(self):
        """测试任务回调函数"""
        agent = MockAgent()
        task = Task(task_type="test", description="test", input_data={})

        callback_called = False
        captured_task = None
        captured_result = None

        def on_complete(task_obj, result_obj):
            nonlocal callback_called, captured_task, captured_result
            callback_called = True
            captured_task = task_obj
            captured_result = result_obj

        agent.on_task_complete = on_complete
        await agent.run(task)

        assert callback_called is True
        assert captured_task == task
        assert captured_result is not None


class TestAgentCommunication:
    """测试智能体通信"""

    def test_send_message(self):
        """测试发送消息"""
        agent1 = MockAgent(agent_id="agent1")
        message_id = agent1.send_message(
            receiver_id="agent2",
            content={"hello": "world"},
            message_type="information",
        )
        assert message_id is not None
        assert len(agent1.outbox) == 1

    def test_receive_message(self):
        """测试接收消息"""
        agent = MockAgent(agent_id="agent1")
        message = AgentMessage(
            sender_id="agent2",
            receiver_id="agent1",
            content={"test": "data"},
        )
        agent.receive_message(message)
        assert len(agent.inbox) == 1

    def test_get_unread_messages(self):
        """测试获取未读消息"""
        agent = MockAgent(agent_id="agent1")

        # 接收3条消息
        for i in range(3):
            agent.receive_message(AgentMessage(
                sender_id=f"sender_{i}",
                receiver_id="agent1",
                content={},
            ))

        assert len(agent.inbox) == 3

        # 获取未读消息
        messages = agent.get_unread_messages()
        assert len(messages) == 3
        assert len(agent.inbox) == 0  # 收件箱应被清空


class TestAgentMemory:
    """测试智能体记忆功能"""

    def test_add_knowledge(self):
        """测试添加知识"""
        agent = MockAgent()
        agent.add_knowledge("key1", "value1")
        agent.add_knowledge("key2", {"nested": "data"})

        assert agent.get_knowledge("key1") == "value1"
        assert agent.get_knowledge("key2") == {"nested": "data"}

    def test_get_knowledge_default(self):
        """测试获取不存在的知识时返回默认值"""
        agent = MockAgent()
        value = agent.get_knowledge("non_existent", "default_value")
        assert value == "default_value"

    def test_conversation_history(self):
        """测试对话历史记录"""
        agent = MockAgent()

        # 模拟添加消息（使用简单对象）
        class MockMessage:
            pass

        for i in range(5):
            agent.add_to_conversation(MockMessage())

        assert len(agent.conversation_history) == 5

        # 测试历史记录截断（超过100条时）
        for i in range(120):
            agent.add_to_conversation(MockMessage())

        assert len(agent.conversation_history) == 100  # 应该保留最近100条


class TestAgentStatus:
    """测试智能体状态信息"""

    def test_get_status_info(self):
        """测试获取状态信息"""
        agent = MockAgent(agent_id="test_agent")

        status = agent.get_status_info()

        assert isinstance(status, dict)
        assert status["agent_id"] == "test_agent"
        assert status["agent_type"] == "document_parser"
        assert status["status"] == "idle"
        assert "total_tasks_executed" in status
        assert "inbox_count" in status

    def test_reset_agent(self):
        """测试重置智能体状态"""
        agent = MockAgent()

        # 修改状态
        agent.status = AgentStatus.RUNNING
        agent.send_message("other", {})
        agent.receive_message(AgentMessage(sender_id="other", receiver_id="agent", content={}))
        agent.add_knowledge("test", "value")

        # 重置
        agent.reset()

        assert agent.status == AgentStatus.IDLE
        assert len(agent.inbox) == 0
        assert len(agent.outbox) == 0
        # 注意：knowledge 不会被重置（设计如此）
