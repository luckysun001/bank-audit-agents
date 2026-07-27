"""
智能体基类和核心抽象模块 - 多智能体系统的基石

本模块定义了银行审计多智能体平台的核心数据结构和抽象基类，是整个系统的基础架构层。

核心组件说明:
    1. AgentStatus: 智能体生命周期状态枚举
    2. TaskStatus: 任务执行状态枚举
    3. AgentMessage: 智能体间通信消息封装
    4. Task: 任务对象，承载执行单元
    5. AgentResult: 智能体执行结果封装
    6. BaseAgent: 智能体抽象基类，所有具体智能体的父类

设计理念:
    - 状态机模式: 智能体和任务都采用状态机管理生命周期
    - 消息队列: 智能体间通过 inbox/outbox 异步通信
    - 回调机制: 支持任务生命周期事件的响应处理
    - 内存管理: 内置对话历史和知识库管理
    - 可扩展设计: 抽象方法允许子类实现具体业务逻辑
"""

import uuid
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Union, Tuple
from enum import Enum
from dataclasses import dataclass, field, asdict

from bank_audit_agents.config.settings import Settings, AgentType, get_settings
from bank_audit_agents.utils.logger import get_logger

# 获取模块级日志记录器，用于基类的日志输出
logger = get_logger(__name__)


class AgentStatus(str, Enum):
    """
    智能体生命周期状态枚举

    状态流转说明:
        IDLE → RUNNING → COMPLETED
                    ↓
                 FAILED/TIMEOUT
                    ↓
                 WAITING (可选)

    状态含义:
        IDLE:       空闲状态，等待任务分配
        RUNNING:    正在执行任务中
        WAITING:    等待外部条件（如消息响应）
        COMPLETED:  任务执行完成
        FAILED:     任务执行失败
        TIMEOUT:    任务执行超时
    """
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class TaskStatus(str, Enum):
    """
    任务执行状态枚举

    状态流转说明:
        PENDING → ASSIGNED → IN_PROGRESS → COMPLETED
                            ↓
                         FAILED/CANCELLED/TIMEOUT

    状态含义:
        PENDING:    任务已创建，等待分配
        ASSIGNED:   任务已分配给智能体
        IN_PROGRESS: 任务正在执行中
        COMPLETED:  任务执行完成
        FAILED:     任务执行失败
        CANCELLED:  任务被取消
        TIMEOUT:    任务执行超时
    """
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


# 回调函数类型别名定义，用于类型提示和代码可读性
TaskCallback = Callable[["Task"], None]
TaskResultCallback = Callable[["Task", "AgentResult"], None]
TaskErrorCallback = Callable[["Task", Exception], None]
MessageCallback = Callable[["AgentMessage"], None]


@dataclass
class AgentMessage:
    """
    智能体间通信消息封装类

    用于实现智能体间的异步消息传递，支持多种消息类型。
    消息格式遵循统一的结构，便于序列化和路由。

    属性说明:
        message_id:     消息唯一标识（自动生成 UUID）
        sender_id:      发送者智能体 ID
        receiver_id:    接收者智能体 ID（支持广播 "*"）
        message_type:   消息类型（information/request/response/command/error）
        content:        消息内容（结构化字典）
        timestamp:      消息发送时间
        references:     引用的消息 ID（用于请求-响应关联）
        metadata:       元数据（附加信息）
    """
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    receiver_id: str = ""
    message_type: str = "information"
    content: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    references: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        将消息对象转换为字典，用于序列化传输

        Returns:
            Dict[str, Any]: 序列化后的消息字典
        """
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "message_type": self.message_type,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "references": self.references,
            "metadata": self.metadata,
        }

    @classmethod
    def create_request(
        cls,
        sender_id: str,
        receiver_id: str,
        request_type: str,
        payload: Dict[str, Any],
    ) -> "AgentMessage":
        """
        创建请求消息的便捷工厂方法

        Args:
            sender_id:      请求发送者 ID
            receiver_id:    请求接收者 ID
            request_type:   请求类型（如 "query", "action", "info"）
            payload:        请求负载数据

        Returns:
            AgentMessage: 构造好的请求消息对象
        """
        return cls(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type="request",
            content={
                "request_type": request_type,
                "payload": payload,
            },
        )

    @classmethod
    def create_response(
        cls,
        sender_id: str,
        receiver_id: str,
        request_id: str,
        payload: Dict[str, Any],
        success: bool = True,
        error: Optional[str] = None,
    ) -> "AgentMessage":
        """
        创建响应消息的便捷工厂方法

        Args:
            sender_id:  响应发送者 ID（通常是被请求的智能体）
            receiver_id: 响应接收者 ID（通常是发起请求的智能体）
            request_id: 关联的请求消息 ID
            payload:    响应负载数据
            success:    请求是否成功
            error:      错误信息（仅当 success=False 时使用）

        Returns:
            AgentMessage: 构造好的响应消息对象
        """
        return cls(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type="response",
            content={
                "request_id": request_id,
                "success": success,
                "payload": payload,
                "error": error,
            },
            references=[request_id],
        )

    def validate(self) -> Tuple[bool, List[str]]:
        """
        验证消息完整性和有效性

        检查必要字段是否存在，消息类型是否合法。

        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误信息列表)
        """
        errors = []
        if not self.sender_id:
            errors.append("sender_id 不能为空")
        if not self.receiver_id:
            errors.append("receiver_id 不能为空")
        if self.message_type not in ["information", "request", "response", "command", "error"]:
            errors.append(f"无效的 message_type: {self.message_type}")
        return len(errors) == 0, errors


@dataclass
class Task:
    """
    任务对象 - 智能体执行的基本单元

    每个任务承载一个独立的审计工作单元，包含任务类型、描述、输入数据等信息。
    支持优先级调度、超时控制、重试机制和任务依赖管理。

    属性说明:
        task_id:        任务唯一标识（自动生成 UUID）
        task_type:      任务类型（如 "document_parsing", "risk_identification"）
        description:    任务描述
        assigned_agent: 已分配的智能体 ID（分配后填充）
        status:         任务当前状态（TaskStatus 枚举）
        priority:       优先级（1-10，10最高）
        input_data:     输入数据字典
        output_data:    输出数据字典（执行完成后填充）
        created_at:     创建时间
        started_at:     开始执行时间
        completed_at:   完成时间
        error_message:  错误消息（失败时填充）
        parent_task_id: 父任务 ID（用于任务层级管理）
        subtasks:       子任务 ID 列表
        metadata:       元数据
        timeout_seconds: 超时时间（秒），默认 300 秒（5分钟）
        max_retries:    最大重试次数，默认 3 次
        retry_count:    当前重试次数
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str = ""
    description: str = ""
    assigned_agent: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    parent_task_id: Optional[str] = None
    subtasks: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 300
    max_retries: int = 3
    retry_count: int = 0

    def start(self) -> None:
        """
        标记任务开始执行

        将任务状态从 PENDING 或 ASSIGNED 转换为 IN_PROGRESS，
        并记录开始时间。
        """
        if self.status not in [TaskStatus.PENDING, TaskStatus.ASSIGNED]:
            logger.warning(f"任务 {self.task_id} 状态为 {self.status}，无法开始")
            return
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now()

    def complete(self, output_data: Optional[Dict[str, Any]] = None) -> None:
        """
        标记任务执行完成

        Args:
            output_data: 任务执行输出数据（可选）
        """
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        if output_data is not None:
            self.output_data = output_data

    def fail(self, error_message: str) -> None:
        """
        标记任务执行失败

        Args:
            error_message: 失败原因描述
        """
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.error_message = error_message

    def cancel(self, reason: str = "cancelled by user") -> None:
        """
        取消任务

        Args:
            reason: 取消原因，默认为 "cancelled by user"
        """
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now()
        self.error_message = reason

    def can_retry(self) -> bool:
        """
        判断任务是否可以重试

        Returns:
            bool: 如果重试次数未超过最大值且任务状态为 FAILED，则返回 True
        """
        return self.retry_count < self.max_retries and self.status == TaskStatus.FAILED

    def mark_for_retry(self) -> None:
        """
        标记任务为重试状态

        将任务状态重置为 PENDING，增加重试计数，清除错误消息。
        """
        if self.can_retry():
            self.retry_count += 1
            self.status = TaskStatus.PENDING
            self.error_message = None
            logger.info(f"任务 {self.task_id} 准备第 {self.retry_count} 次重试")

    @property
    def duration_seconds(self) -> float:
        """
        获取任务执行时长（秒）

        Returns:
            float: 执行时长，如果任务未完成则返回 0
        """
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    @property
    def is_finished(self) -> bool:
        """
        判断任务是否已结束

        结束状态包括：COMPLETED、FAILED、CANCELLED、TIMEOUT

        Returns:
            bool: 任务是否已结束
        """
        return self.status in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.TIMEOUT,
        ]

    @property
    def is_runnable(self) -> bool:
        """
        判断任务是否可以执行

        可执行状态包括：PENDING、ASSIGNED

        Returns:
            bool: 任务是否可执行
        """
        return self.status in [TaskStatus.PENDING, TaskStatus.ASSIGNED]

    def to_dict(self) -> Dict[str, Any]:
        """
        将任务对象转换为字典，用于序列化和状态展示

        Returns:
            Dict[str, Any]: 任务状态摘要字典
        """
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
        }

    def validate(self) -> Tuple[bool, List[str]]:
        """
        验证任务完整性

        检查必要字段是否存在，优先级是否在合法范围内。

        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误信息列表)
        """
        errors = []
        if not self.task_type:
            errors.append("task_type 不能为空")
        if not self.description:
            errors.append("description 不能为空")
        if self.priority < 1 or self.priority > 10:
            errors.append(f"priority 必须在 1-10 之间，当前值: {self.priority}")
        return len(errors) == 0, errors

    def __lt__(self, other: "Task") -> bool:
        """
        支持 PriorityQueue 中的任务比较

        Python 的 PriorityQueue 默认使用小于号比较，
        这里通过任务 ID 进行比较以确保稳定性。

        Args:
            other: 另一个任务对象

        Returns:
            bool: 当前任务是否小于另一个任务
        """
        return self.task_id < other.task_id


@dataclass
class AgentResult:
    """
    智能体执行结果封装类

    用于统一封装智能体执行任务后的输出，包含成功状态、摘要、发现项、建议等。

    属性说明:
        agent_id:               执行任务的智能体 ID
        agent_type:             智能体类型
        success:                执行是否成功
        summary:                执行结果摘要
        findings:               发现项列表（结构化数据）
        recommendations:        建议列表
        output_data:            结构化输出数据
        metadata:               元数据
        error:                  错误信息（失败时填充）
        execution_time_seconds: 执行时长（秒）
        confidence_score:       置信度评分（0-1）
        warnings:               警告信息列表
    """
    agent_id: str
    agent_type: str
    success: bool
    summary: str = ""
    findings: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    output_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    confidence_score: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def add_finding(self, finding: Dict[str, Any]) -> None:
        """
        添加发现项

        Args:
            finding: 发现项字典，包含描述、风险等级等信息
        """
        self.findings.append(finding)

    def add_recommendation(self, recommendation: str) -> None:
        """
        添加建议

        Args:
            recommendation: 建议文本
        """
        self.recommendations.append(recommendation)

    def add_warning(self, warning: str) -> None:
        """
        添加警告信息

        Args:
            warning: 警告文本
        """
        self.warnings.append(warning)

    def merge(self, other: "AgentResult") -> None:
        """
        合并另一个结果对象

        将另一个 AgentResult 的发现项、建议、警告等合并到当前对象。
        置信度取两者中的最小值（保守策略）。

        Args:
            other: 另一个 AgentResult 对象
        """
        self.findings.extend(other.findings)
        self.recommendations.extend(other.recommendations)
        self.warnings.extend(other.warnings)
        self.output_data.update(other.output_data)
        self.metadata.update(other.metadata)
        self.confidence_score = min(self.confidence_score, other.confidence_score)

    def to_dict(self) -> Dict[str, Any]:
        """
        将结果对象转换为字典，用于序列化和展示

        Returns:
            Dict[str, Any]: 结果摘要字典
        """
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "success": self.success,
            "summary": self.summary,
            "findings_count": len(self.findings),
            "findings": self.findings,
            "recommendations_count": len(self.recommendations),
            "recommendations": self.recommendations,
            "output_data": self.output_data,
            "error": self.error,
            "execution_time_seconds": self.execution_time_seconds,
            "confidence_score": self.confidence_score,
            "warnings": self.warnings,
            "has_warnings": len(self.warnings) > 0,
        }


class BaseAgent(ABC):
    """
    审计智能体抽象基类

    所有具体审计智能体（文档解析、风险识别、合规检查等）都继承自此基类。
    提供智能体的通用功能：状态管理、任务执行、消息通信、内存管理等。

    子类必须实现的抽象方法:
        - get_system_prompt(): 获取智能体的系统提示词
        - get_tools(): 获取智能体可用的工具列表
        - execute(task): 执行具体任务的核心逻辑

    核心特性:
        1. 状态机管理: 通过 AgentStatus 管理智能体生命周期
        2. 任务执行: 提供 run() 方法封装任务执行流程
        3. 消息队列: 内置 inbox/outbox 支持异步消息传递
        4. 回调机制: 支持任务生命周期事件的响应处理
        5. 内存管理: 对话历史和知识库管理
        6. 统计监控: 执行统计和健康检查
    """

    def __init__(
        self,
        agent_type: AgentType,
        agent_id: Optional[str] = None,
        settings: Optional[Settings] = None,
    ):
        """
        初始化智能体

        Args:
            agent_type:     智能体类型（AgentType 枚举）
            agent_id:       智能体 ID（可选，不提供则自动生成）
            settings:       配置对象（可选，不提供则使用全局配置）
        """
        # 智能体身份标识
        self.agent_type = agent_type
        self.agent_id = agent_id or f"{agent_type.value}_{uuid.uuid4().hex[:8]}"
        self.settings = settings or get_settings()

        # 智能体状态管理
        self.status = AgentStatus.IDLE
        self.current_task: Optional[Task] = None

        # 消息队列（用于智能体间异步通信）
        self.inbox: List[AgentMessage] = []
        self.outbox: List[AgentMessage] = []

        # 执行统计（用于监控和评估）
        self.total_tasks_executed = 0
        self.total_execution_time = 0.0
        self.total_tasks_failed = 0

        # 内存和上下文（用于保持对话状态和积累知识）
        self.conversation_history: List[Any] = []
        self.knowledge_context: Dict[str, Any] = {}

        # 回调函数（用于事件响应）
        self.on_task_start: Optional[TaskCallback] = None
        self.on_task_complete: Optional[TaskResultCallback] = None
        self.on_task_fail: Optional[TaskErrorCallback] = None
        self.on_message_sent: Optional[MessageCallback] = None
        self.on_message_received: Optional[MessageCallback] = None

        logger.info(f"✅ 智能体初始化完成: {self.agent_id} ({agent_type.value})")

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        获取智能体的系统提示词

        系统提示词定义了智能体的角色、职责和行为规范，
        是 LLM 驱动智能体的核心配置。

        Returns:
            str: 系统提示词文本
        """
        pass

    @abstractmethod
    def get_tools(self) -> List[Any]:
        """
        获取智能体可用的工具列表

        返回智能体可以调用的外部工具名称或对象列表，
        用于增强智能体的能力（如文档解析、数据库查询等）。

        Returns:
            List[Any]: 工具列表
        """
        pass

    @abstractmethod
    async def execute(self, task: Task) -> AgentResult:
        """
        执行任务的核心方法

        所有子类必须实现此方法，包含具体的业务逻辑。

        Args:
            task: 要执行的任务对象

        Returns:
            AgentResult: 执行结果
        """
        pass

    async def run(self, task: Task) -> AgentResult:
        """
        运行任务（带状态管理和错误处理的包装方法）

        这是任务执行的入口方法，封装了完整的执行流程：
        1. 验证任务合法性
        2. 更新智能体和任务状态
        3. 触发开始回调
        4. 执行具体任务逻辑
        5. 更新执行统计
        6. 触发完成/失败回调
        7. 返回执行结果

        Args:
            task: 要执行的任务

        Returns:
            AgentResult: 执行结果
        """
        start_time = time.time()
        self.current_task = task
        self.status = AgentStatus.RUNNING

        logger.info(f"🚀 智能体开始执行任务: {self.agent_id}, 任务: {task.task_id}")

        # 验证任务合法性
        is_valid, errors = task.validate()
        if not is_valid:
            error_msg = f"任务验证失败: {', '.join(errors)}"
            logger.error(f"❌ {error_msg}")
            task.fail(error_msg)
            self.status = AgentStatus.FAILED
            return AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type.value,
                success=False,
                summary=error_msg,
                error=error_msg,
                execution_time_seconds=time.time() - start_time,
            )

        # 触发任务开始回调
        if self.on_task_start:
            try:
                self.on_task_start(task)
            except Exception as e:
                logger.warning(f"on_task_start 回调执行失败: {e}")

        try:
            # 标记任务开始执行
            task.start()

            # 调用子类实现的具体任务逻辑
            result = await self.execute(task)

            # 记录执行时间
            execution_time = time.time() - start_time
            result.execution_time_seconds = execution_time
            self.total_execution_time += execution_time
            self.total_tasks_executed += 1

            # 标记任务完成
            task.complete(result.output_data)

            logger.info(
                f"✅ 任务完成: {self.agent_id}, 任务: {task.task_id}, "
                f"耗时: {execution_time:.2f}秒, 置信度: {result.confidence_score:.2f}"
            )

            # 触发任务完成回调
            if self.on_task_complete:
                try:
                    self.on_task_complete(task, result)
                except Exception as e:
                    logger.warning(f"on_task_complete 回调执行失败: {e}")

            # 更新智能体状态为完成
            self.status = AgentStatus.COMPLETED
            return result

        except Exception as e:
            # 任务执行异常处理
            execution_time = time.time() - start_time
            self.total_tasks_failed += 1
            error_msg = str(e)

            logger.error(
                f"❌ 任务执行失败: {self.agent_id}, 任务: {task.task_id}, "
                f"错误: {error_msg}, 耗时: {execution_time:.2f}秒"
            )

            # 标记任务失败
            task.fail(error_msg)

            # 构建错误结果
            error_result = AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type.value,
                success=False,
                summary=f"任务执行失败: {error_msg}",
                error=error_msg,
                execution_time_seconds=execution_time,
            )

            # 触发任务失败回调
            if self.on_task_fail:
                try:
                    self.on_task_fail(task, e)
                except Exception as callback_error:
                    logger.warning(f"on_task_fail 回调执行失败: {callback_error}")

            # 更新智能体状态为失败
            self.status = AgentStatus.FAILED
            return error_result

    def send_message(
        self,
        receiver_id: str,
        content: Dict[str, Any],
        message_type: str = "information",
    ) -> str:
        """
        向其他智能体发送消息

        将消息添加到 outbox，由协调器负责路由传递。

        Args:
            receiver_id: 接收者智能体 ID（支持广播 "*"）
            content:     消息内容字典
            message_type: 消息类型（information/request/response/command/error）

        Returns:
            str: 消息 ID
        """
        # 构造消息对象
        message = AgentMessage(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            message_type=message_type,
            content=content,
        )

        # 验证消息有效性
        is_valid, errors = message.validate()
        if not is_valid:
            logger.warning(f"消息验证失败: {errors}")

        # 添加到发件箱
        self.outbox.append(message)

        logger.debug(f"📤 智能体发送消息: {self.agent_id} -> {receiver_id}, 类型: {message_type}")

        # 触发消息发送回调
        if self.on_message_sent:
            try:
                self.on_message_sent(message)
            except Exception as e:
                logger.warning(f"on_message_sent 回调执行失败: {e}")

        return message.message_id

    def receive_message(self, message: AgentMessage) -> None:
        """
        接收消息

        将接收到的消息添加到 inbox，等待智能体处理。

        Args:
            message: 收到的消息对象
        """
        self.inbox.append(message)

        logger.debug(f"📥 智能体收到消息: {self.agent_id} <- {message.sender_id}, 类型: {message.message_type}")

        # 触发消息接收回调
        if self.on_message_received:
            try:
                self.on_message_received(message)
            except Exception as e:
                logger.warning(f"on_message_received 回调执行失败: {e}")

    def get_unread_messages(self) -> List[AgentMessage]:
        """
        获取所有未读消息（并清空收件箱）

        Returns:
            List[AgentMessage]: 未读消息列表
        """
        messages = self.inbox.copy()
        self.inbox.clear()
        return messages

    def get_latest_message(self) -> Optional[AgentMessage]:
        """
        获取最新的一条消息（不移除）

        Returns:
            Optional[AgentMessage]: 最新消息，如果没有则返回 None
        """
        return self.inbox[-1] if self.inbox else None

    def add_to_conversation(self, message: Any) -> None:
        """
        添加对话历史记录

        用于保持多轮对话的上下文，支持智能体的记忆功能。
        默认保留最近 100 条消息。

        Args:
            message: 对话内容（可以是字符串或结构化数据）
        """
        self.conversation_history.append(message)
        # 保留最近 100 条消息，防止内存溢出
        if len(self.conversation_history) > 100:
            self.conversation_history = self.conversation_history[-100:]

    def clear_conversation(self) -> None:
        """
        清空对话历史

        重置对话上下文，用于开始新的对话。
        """
        self.conversation_history.clear()
        logger.info(f"🧹 智能体 {self.agent_id} 对话历史已清空")

    def add_knowledge(self, key: str, value: Any) -> None:
        """
        添加知识库内容

        用于存储和检索智能体在执行过程中积累的知识。

        Args:
            key:   知识键名
            value: 知识内容
        """
        self.knowledge_context[key] = value

    def add_knowledge_batch(self, knowledge: Dict[str, Any]) -> None:
        """
        批量添加知识

        Args:
            knowledge: 知识字典
        """
        self.knowledge_context.update(knowledge)

    def get_knowledge(self, key: str, default: Any = None) -> Any:
        """
        获取知识库内容

        Args:
            key:      知识键名
            default:  默认值（当键不存在时返回）

        Returns:
            Any: 知识内容
        """
        return self.knowledge_context.get(key, default)

    def remove_knowledge(self, key: str) -> None:
        """
        移除知识库内容

        Args:
            key: 知识键名
        """
        self.knowledge_context.pop(key, None)

    def clear_knowledge(self) -> None:
        """
        清空知识库

        删除所有积累的知识，用于重置智能体状态。
        """
        self.knowledge_context.clear()
        logger.info(f"🧹 智能体 {self.agent_id} 知识库已清空")

    def get_status_info(self) -> Dict[str, Any]:
        """
        获取智能体状态信息

        返回包含状态、统计数据、消息队列等的综合状态信息。

        Returns:
            Dict[str, Any]: 状态信息字典
        """
        # 计算平均执行时间
        avg_time = (
            self.total_execution_time / self.total_tasks_executed
            if self.total_tasks_executed > 0
            else 0
        )
        # 计算成功率
        success_rate = (
            self.total_tasks_executed / (self.total_tasks_executed + self.total_tasks_failed)
            if (self.total_tasks_executed + self.total_tasks_failed) > 0
            else 1.0
        )

        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "status": self.status.value,
            "total_tasks_executed": self.total_tasks_executed,
            "inbox_count": len(self.inbox),
            "current_task_id": self.current_task.task_id if self.current_task else None,
            "statistics": {
                "total_tasks_executed": self.total_tasks_executed,
                "total_tasks_failed": self.total_tasks_failed,
                "total_execution_time": round(self.total_execution_time, 2),
                "average_execution_time": round(avg_time, 2),
                "success_rate": round(success_rate, 2),
            },
            "message_queues": {
                "inbox_count": len(self.inbox),
                "outbox_count": len(self.outbox),
            },
            "memory": {
                "conversation_history_length": len(self.conversation_history),
                "knowledge_entries": len(self.knowledge_context),
            },
        }

    def reset(self) -> None:
        """
        重置智能体状态

        将智能体恢复到初始状态，但保留知识库内容。

        重置内容:
            - 状态重置为 IDLE
            - 当前任务置为 None
            - 清空消息队列
            - 清空对话历史
            - 保留知识库
        """
        self.status = AgentStatus.IDLE
        self.current_task = None
        self.inbox.clear()
        self.outbox.clear()
        self.conversation_history.clear()
        logger.info(f"🔄 智能体已重置: {self.agent_id}")

    def health_check(self) -> Tuple[bool, Dict[str, Any]]:
        """
        健康检查

        检查智能体的运行状态，识别潜在问题。

        检查项:
            - 当前状态是否正常
            - 是否有长时间运行的任务（超过 10 分钟）

        Returns:
            Tuple[bool, Dict[str, Any]]: (是否健康, 详细信息)
        """
        is_healthy = True
        details = {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "is_idle": self.status == AgentStatus.IDLE,
            "has_pending_messages": len(self.inbox) > 0,
        }

        # 检查是否有长时间运行的任务
        if self.status == AgentStatus.RUNNING and self.current_task:
            running_time = (datetime.now() - self.current_task.started_at).total_seconds()
            details["running_time_seconds"] = running_time
            if running_time > 600:  # 超过 10 分钟
                is_healthy = False
                details["warning"] = "任务执行时间过长"

        return is_healthy, details

    def __str__(self) -> str:
        """
        返回智能体的字符串表示

        Returns:
            str: 智能体描述字符串
        """
        return f"<BaseAgent id={self.agent_id} type={self.agent_type.value} status={self.status.value}>"

    def __repr__(self) -> str:
        """
        返回智能体的正式表示

        Returns:
            str: 智能体的正式描述字符串
        """
        return self.__str__()