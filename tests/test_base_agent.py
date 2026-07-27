"""
智能体基类测试模块

本测试模块全面测试 BaseAgent 类及其相关组件（Task、AgentMessage、AgentResult），
验证多智能体系统的核心基础功能。

测试覆盖范围：
1. 智能体初始化和基本属性
2. 任务对象的生命周期管理
3. 智能体消息传递机制
4. 智能体执行流程和回调
5. 智能体记忆功能
6. 智能体状态管理

运行方式：
    pytest tests/test_base_agent.py -v

测试架构：
- MockAgent: 测试用模拟智能体，实现了最小必要接口
- TestBaseAgent: 测试智能体基本功能
- TestTask: 测试任务对象
- TestAgentMessage: 测试消息对象
- TestAgentExecution: 测试智能体执行（异步）
- TestAgentCommunication: 测试智能体通信
- TestAgentMemory: 测试智能体记忆功能
- TestAgentStatus: 测试智能体状态管理
"""

# 导入测试框架和必要的库
import pytest
import asyncio

# 导入待测试的核心类
from bank_audit_agents.core.base_agent import (
    BaseAgent,           # 智能体基类
    Task,               # 任务对象
    AgentResult,        # 执行结果对象
    AgentMessage,       # 消息对象
    AgentStatus,        # 智能体状态枚举
    TaskStatus,         # 任务状态枚举
    AgentType,          # 智能体类型枚举
)


# ==================== 测试用模拟智能体 ====================
class MockAgent(BaseAgent):
    """测试用的模拟智能体

    这是一个最小实现的智能体，用于测试 BaseAgent 的各种功能。
    实现了 get_system_prompt()、get_tools() 和 execute() 三个抽象方法。
    """

    def __init__(self, agent_id=None):
        """初始化模拟智能体"""
        super().__init__(AgentType.DOCUMENT_PARSER, agent_id)

    def get_system_prompt(self) -> str:
        """返回测试用系统提示词"""
        return "你是一个测试智能体"

    def get_tools(self) -> list:
        """返回测试用工具列表"""
        return ["test_tool"]

    async def execute(self, task: Task) -> AgentResult:
        """执行测试任务

        模拟实际执行过程，延迟 0.1 秒后返回成功结果。

        Args:
            task: 待执行的任务对象

        Returns:
            AgentResult: 执行结果，包含成功标记、摘要、发现和置信度
        """
        await asyncio.sleep(0.1)  # 模拟工作耗时
        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type.value,
            success=True,
            summary="测试任务完成",
            findings=[{"key": "value"}],
            confidence_score=0.95,
        )


# ==================== 智能体基类测试 ====================
class TestBaseAgent:
    """测试智能体基类的基本功能"""

    def test_agent_initialization(self):
        """测试智能体初始化（指定 ID）"""
        agent = MockAgent(agent_id="test_agent_001")
        # 验证 ID 设置正确
        assert agent.agent_id == "test_agent_001"
        # 验证类型设置正确
        assert agent.agent_type == AgentType.DOCUMENT_PARSER
        # 验证初始状态为 IDLE
        assert agent.status == AgentStatus.IDLE

    def test_agent_without_id(self):
        """测试不指定 ID 时自动生成"""
        agent = MockAgent()
        # 验证自动生成了 ID
        assert agent.agent_id is not None
        # 验证 ID 包含类型标识符
        assert "document_parser" in agent.agent_id

    def test_system_prompt(self):
        """测试系统提示词获取"""
        agent = MockAgent()
        prompt = agent.get_system_prompt()
        # 验证返回值是字符串
        assert isinstance(prompt, str)
        # 验证字符串非空
        assert len(prompt) > 0

    def test_tools(self):
        """测试工具列表获取"""
        agent = MockAgent()
        tools = agent.get_tools()
        # 验证返回值是列表
        assert isinstance(tools, list)
        # 验证包含预期工具
        assert "test_tool" in tools


# ==================== 任务对象测试 ====================
class TestTask:
    """测试任务对象的生命周期管理"""

    def test_task_creation(self):
        """测试任务创建和基本属性"""
        task = Task(
            task_type="test_task",
            description="测试任务",
            input_data={"key": "value"},
        )
        # 验证任务 ID 自动生成
        assert task.task_id is not None
        # 验证任务类型设置正确
        assert task.task_type == "test_task"
        # 验证任务描述设置正确
        assert task.description == "测试任务"
        # 验证初始状态为 PENDING
        assert task.status == TaskStatus.PENDING

    def test_task_start(self):
        """测试任务开始执行"""
        task = Task(task_type="test", description="test")
        task.start()
        # 验证状态变更为 IN_PROGRESS
        assert task.status == TaskStatus.IN_PROGRESS
        # 验证开始时间已记录
        assert task.started_at is not None

    def test_task_complete(self):
        """测试任务成功完成"""
        task = Task(task_type="test", description="test")
        task.start()
        task.complete({"result": "success"})
        # 验证状态变更为 COMPLETED
        assert task.status == TaskStatus.COMPLETED
        # 验证完成时间已记录
        assert task.completed_at is not None
        # 验证输出数据已保存
        assert task.output_data == {"result": "success"}

    def test_task_fail(self):
        """测试任务失败"""
        task = Task(task_type="test", description="test")
        task.start()
        task.fail("something went wrong")
        # 验证状态变更为 FAILED
        assert task.status == TaskStatus.FAILED
        # 验证错误信息已保存
        assert task.error_message == "something went wrong"

    def test_task_duration(self):
        """测试任务执行时间计算"""
        import time
        task = Task(task_type="test", description="test")
        task.start()
        time.sleep(0.1)  # 模拟执行耗时
        task.complete({})
        # 验证执行时间计算正确（至少 0.1 秒）
        assert task.duration_seconds >= 0.1


# ==================== 智能体消息测试 ====================
class TestAgentMessage:
    """测试智能体消息对象"""

    def test_message_creation(self):
        """测试消息创建和基本属性"""
        message = AgentMessage(
            sender_id="agent_1",
            receiver_id="agent_2",
            message_type="information",
            content={"key": "value"},
        )
        # 验证消息 ID 自动生成
        assert message.message_id is not None
        # 验证发送者 ID 设置正确
        assert message.sender_id == "agent_1"
        # 验证接收者 ID 设置正确
        assert message.receiver_id == "agent_2"
        # 验证消息内容设置正确
        assert message.content == {"key": "value"}

    def test_message_to_dict(self):
        """测试消息转换为字典（用于序列化传输）"""
        message = AgentMessage(
            sender_id="agent_1",
            receiver_id="agent_2",
            content={"data": "test"},
        )
        msg_dict = message.to_dict()
        # 验证返回值是字典
        assert isinstance(msg_dict, dict)
        # 验证包含消息 ID
        assert "message_id" in msg_dict
        # 验证发送者 ID 正确
        assert msg_dict["sender_id"] == "agent_1"
        # 验证内容正确
        assert msg_dict["content"]["data"] == "test"


# ==================== 智能体执行测试（异步） ====================
@pytest.mark.asyncio
class TestAgentExecution:
    """测试智能体异步执行流程"""

    async def test_run_task_success(self):
        """测试成功执行任务"""
        agent = MockAgent()
        task = Task(task_type="test", description="测试任务", input_data={})

        # 执行任务
        result = await agent.run(task)

        # 验证执行结果
        assert result.success is True
        assert result.agent_id == agent.agent_id
        assert result.confidence_score == 0.95
        assert len(result.findings) == 1
        # 验证智能体状态变更为 COMPLETED
        assert agent.status == AgentStatus.COMPLETED

    async def test_task_callback(self):
        """测试任务完成回调函数"""
        agent = MockAgent()
        task = Task(task_type="test", description="test", input_data={})

        # 设置回调捕获变量
        callback_called = False
        captured_task = None
        captured_result = None

        # 定义回调函数
        def on_complete(task_obj, result_obj):
            nonlocal callback_called, captured_task, captured_result
            callback_called = True
            captured_task = task_obj
            captured_result = result_obj

        # 注册回调
        agent.on_task_complete = on_complete
        # 执行任务
        await agent.run(task)

        # 验证回调被调用
        assert callback_called is True
        # 验证捕获的任务对象正确
        assert captured_task == task
        # 验证捕获的结果对象非空
        assert captured_result is not None


# ==================== 智能体通信测试 ====================
class TestAgentCommunication:
    """测试智能体消息传递机制"""

    def test_send_message(self):
        """测试发送消息到发件箱"""
        agent1 = MockAgent(agent_id="agent1")
        # 发送消息
        message_id = agent1.send_message(
            receiver_id="agent2",
            content={"hello": "world"},
            message_type="information",
        )
        # 验证消息 ID 生成
        assert message_id is not None
        # 验证消息已添加到发件箱
        assert len(agent1.outbox) == 1

    def test_receive_message(self):
        """测试接收消息到收件箱"""
        agent = MockAgent(agent_id="agent1")
        # 创建消息
        message = AgentMessage(
            sender_id="agent2",
            receiver_id="agent1",
            content={"test": "data"},
        )
        # 接收消息
        agent.receive_message(message)
        # 验证消息已添加到收件箱
        assert len(agent.inbox) == 1

    def test_get_unread_messages(self):
        """测试获取并清空未读消息"""
        agent = MockAgent(agent_id="agent1")

        # 接收3条消息
        for i in range(3):
            agent.receive_message(AgentMessage(
                sender_id=f"sender_{i}",
                receiver_id="agent1",
                content={},
            ))

        # 验证收件箱中有3条消息
        assert len(agent.inbox) == 3

        # 获取未读消息（同时清空收件箱）
        messages = agent.get_unread_messages()
        # 验证返回了3条消息
        assert len(messages) == 3
        # 验证收件箱已被清空
        assert len(agent.inbox) == 0


# ==================== 智能体记忆功能测试 ====================
class TestAgentMemory:
    """测试智能体知识存储和对话历史功能"""

    def test_add_knowledge(self):
        """测试添加和获取知识"""
        agent = MockAgent()
        # 添加简单知识
        agent.add_knowledge("key1", "value1")
        # 添加嵌套知识
        agent.add_knowledge("key2", {"nested": "data"})

        # 验证知识存储正确
        assert agent.get_knowledge("key1") == "value1"
        assert agent.get_knowledge("key2") == {"nested": "data"}

    def test_get_knowledge_default(self):
        """测试获取不存在的知识时返回默认值"""
        agent = MockAgent()
        # 获取不存在的知识，指定默认值
        value = agent.get_knowledge("non_existent", "default_value")
        # 验证返回了默认值
        assert value == "default_value"

    def test_conversation_history(self):
        """测试对话历史记录和截断机制"""
        agent = MockAgent()

        # 定义模拟消息类
        class MockMessage:
            pass

        # 添加5条消息
        for i in range(5):
            agent.add_to_conversation(MockMessage())

        # 验证历史记录有5条
        assert len(agent.conversation_history) == 5

        # 再添加120条消息（共125条）
        for i in range(120):
            agent.add_to_conversation(MockMessage())

        # 验证历史记录被截断为100条（只保留最近的）
        assert len(agent.conversation_history) == 100


# ==================== 智能体状态测试 ====================
class TestAgentStatus:
    """测试智能体状态管理和状态信息获取"""

    def test_get_status_info(self):
        """测试获取智能体状态信息"""
        agent = MockAgent(agent_id="test_agent")

        # 获取状态信息
        status = agent.get_status_info()

        # 验证状态信息格式正确
        assert isinstance(status, dict)
        assert status["agent_id"] == "test_agent"
        assert status["agent_type"] == "document_parser"
        assert status["status"] == "idle"
        # 验证包含必要的统计字段
        assert "total_tasks_executed" in status
        assert "inbox_count" in status

    def test_reset_agent(self):
        """测试重置智能体状态"""
        agent = MockAgent()

        # 修改智能体状态（模拟运行后状态）
        agent.status = AgentStatus.RUNNING
        agent.send_message("other", {})
        agent.receive_message(AgentMessage(sender_id="other", receiver_id="agent", content={}))
        agent.add_knowledge("test", "value")

        # 执行重置
        agent.reset()

        # 验证状态已重置为 IDLE
        assert agent.status == AgentStatus.IDLE
        # 验证收件箱已清空
        assert len(agent.inbox) == 0
        # 验证发件箱已清空
        assert len(agent.outbox) == 0
        # 注意：根据设计，knowledge 不会被重置（保留长期记忆）
